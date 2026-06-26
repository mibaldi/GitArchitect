"""Use case: build the static CodeModel for an imported workspace."""

from __future__ import annotations

from codebase_architect.domain.model.code import Language, ParsedFile
from codebase_architect.domain.model.code_model import CodeModel
from codebase_architect.domain.model.workspace import Workspace
from codebase_architect.domain.ports.analysis import (
    CodeParser,
    LanguageDetector,
    ManifestDetector,
)
from codebase_architect.shared.logging import get_logger

logger = get_logger(__name__)

# Skip files larger than this when parsing (likely generated/vendored blobs).
_MAX_PARSE_BYTES = 2_000_000


class BuildCodeModelUseCase:
    """Detects languages, parses supported files and scans manifests."""

    def __init__(
        self,
        language_detector: LanguageDetector,
        parser: CodeParser,
        manifest_detector: ManifestDetector,
    ) -> None:
        self._detector = language_detector
        self._parser = parser
        self._manifests = manifest_detector

    def execute(self, workspace: Workspace) -> CodeModel:
        model = CodeModel()

        for path in workspace.iter_files():
            rel = workspace.relative(path)
            language = self._detector.detect(rel)
            if language is Language.UNKNOWN:
                model.other_file_count += 1
                continue
            try:
                content = path.read_bytes()
            except OSError:
                model.other_file_count += 1
                continue

            if self._parser.supports(language) and len(content) <= _MAX_PARSE_BYTES:
                parsed = self._parser.parse(rel, language, content)
            else:
                parsed = ParsedFile(path=rel, language=language, loc=_count_lines(content))
            model.parsed_files.append(parsed)

        model.stacks, model.dependencies = self._manifests.detect(workspace)

        logger.info(
            "code_model_built",
            files=len(model.parsed_files),
            symbols=model.symbol_count,
            stacks=[s.name for s in model.stacks],
            dependencies=len(model.dependencies),
        )
        return model


def _count_lines(content: bytes) -> int:
    if not content:
        return 0
    return content.count(b"\n") + (0 if content.endswith(b"\n") else 1)
