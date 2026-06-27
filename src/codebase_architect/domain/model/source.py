"""Source model: where a codebase comes from.

A :class:`SourceLocation` is the raw, user-provided reference to a codebase
(a path, a URL, an archive file). A :class:`SourceProvider` later turns it into
a materialized :class:`~codebase_architect.domain.model.workspace.Workspace`.

The domain stays unaware of *how* each kind is fetched — that lives in the
infrastructure adapters.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class SourceType(StrEnum):
    """The kind of origin a codebase was imported from."""

    GIT_REMOTE = "git_remote"
    LOCAL_GIT = "local_git"
    FOLDER = "folder"
    ZIP = "zip"
    TARGZ = "targz"


@dataclass(frozen=True)
class SourceLocation:
    """A raw, unresolved reference to a codebase.

    ``raw`` is exactly what the user supplied (e.g. ``"./my-app"``,
    ``"https://example.com/app.git"``, ``"/tmp/app.zip"``). Detection of the
    concrete :class:`SourceType` is delegated to the source providers, each of
    which inspects this value (and, for archives, its magic bytes).
    """

    raw: str

    def __post_init__(self) -> None:
        if not self.raw or not self.raw.strip():
            from codebase_architect.shared.errors import ValidationError

            raise ValidationError("SourceLocation.raw must be a non-empty string")
