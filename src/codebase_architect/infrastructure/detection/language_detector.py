"""Language detection by file extension / name."""

from __future__ import annotations

from codebase_architect.domain.model.code import Language
from codebase_architect.domain.ports.analysis import LanguageDetector

_EXTENSIONS: dict[str, Language] = {
    ".java": Language.JAVA,
    ".kt": Language.KOTLIN,
    ".kts": Language.KOTLIN,
    ".ts": Language.TYPESCRIPT,
    ".mts": Language.TYPESCRIPT,
    ".cts": Language.TYPESCRIPT,
    ".tsx": Language.TSX,
    ".js": Language.JAVASCRIPT,
    ".mjs": Language.JAVASCRIPT,
    ".cjs": Language.JAVASCRIPT,
    ".jsx": Language.TSX,
    ".html": Language.HTML,
    ".htm": Language.HTML,
}


class ExtensionLanguageDetector(LanguageDetector):
    """Detects the language of a file from its extension."""

    def detect(self, relative_path: str) -> Language:
        lowered = relative_path.lower()
        # Angular component templates are HTML; keep the generic mapping.
        dot = lowered.rfind(".")
        if dot == -1:
            return Language.UNKNOWN
        return _EXTENSIONS.get(lowered[dot:], Language.UNKNOWN)
