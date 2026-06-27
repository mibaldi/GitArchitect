"""File-backed narrative cache.

Stores each report as a JSON file named by its key under a cache directory, so
re-scanning an unchanged codebase reuses the previous AI narrative instead of
calling (and paying for) the model again.
"""

from __future__ import annotations

import json
from pathlib import Path

from codebase_architect.domain.model.ai import TokenUsage
from codebase_architect.domain.model.feature import Feature, FeatureSource
from codebase_architect.domain.model.narrative import NarrativeReport
from codebase_architect.domain.ports.narrative_cache import NarrativeCache


class FileNarrativeCache(NarrativeCache):
    """Persists narrative reports as JSON keyed by a content hash."""

    def __init__(self, cache_dir: Path) -> None:
        self._dir = cache_dir

    def _path(self, key: str) -> Path:
        return self._dir / f"{key}.json"

    def get(self, key: str) -> NarrativeReport | None:
        path = self._path(key)
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return _from_dict(data)

    def put(self, key: str, report: NarrativeReport) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        self._path(key).write_text(json.dumps(_to_dict(report)), encoding="utf-8")


def _to_dict(report: NarrativeReport) -> dict[str, object]:
    return {
        "overview": report.overview,
        "features": [
            {
                "name": f.name,
                "description": f.description,
                "related": list(f.related),
                "source": f.source.value,
            }
            for f in report.features
        ],
        "flows": report.flows,
        "usage": {
            "input_tokens": report.usage.input_tokens,
            "output_tokens": report.usage.output_tokens,
        },
    }


def _from_dict(data: dict[str, object]) -> NarrativeReport:
    features_raw = data.get("features", [])
    features_list = features_raw if isinstance(features_raw, list) else []
    features = [
        Feature(
            name=str(f.get("name", "")),
            description=str(f.get("description", "")),
            related=tuple(str(r) for r in _as_list(f.get("related"))),
            source=FeatureSource(str(f.get("source", FeatureSource.AI.value))),
        )
        for f in features_list
        if isinstance(f, dict)
    ]
    flows_raw = data.get("flows", {})
    flows = {str(k): str(v) for k, v in flows_raw.items()} if isinstance(flows_raw, dict) else {}
    usage_raw = data.get("usage", {})
    usage = TokenUsage()
    if isinstance(usage_raw, dict):
        usage = TokenUsage(
            input_tokens=int(usage_raw.get("input_tokens", 0)),
            output_tokens=int(usage_raw.get("output_tokens", 0)),
        )
    return NarrativeReport(
        overview=str(data.get("overview", "")),
        features=features,
        flows=flows,
        usage=usage,
    )


def _as_list(value: object) -> list[object]:
    return value if isinstance(value, list) else []
