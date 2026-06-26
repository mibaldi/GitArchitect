"""Tests for ExtensionLanguageDetector."""

from __future__ import annotations

import pytest

from codebase_architect.domain.model.code import Language
from codebase_architect.infrastructure.detection.language_detector import ExtensionLanguageDetector


@pytest.mark.parametrize(
    ("path", "language"),
    [
        ("src/Main.java", Language.JAVA),
        ("app/Greeter.kt", Language.KOTLIN),
        ("build.gradle.kts", Language.KOTLIN),
        ("app/app.component.ts", Language.TYPESCRIPT),
        ("app/app.component.tsx", Language.TSX),
        ("app/app.component.html", Language.HTML),
        ("scripts/run.js", Language.JAVASCRIPT),
        ("README.md", Language.UNKNOWN),
        ("Dockerfile", Language.UNKNOWN),
    ],
)
def test_detect(path: str, language: Language) -> None:
    assert ExtensionLanguageDetector().detect(path) is language
