"""End-to-end test for BuildCodeModelUseCase over a mixed codebase."""

from __future__ import annotations

from pathlib import Path

from codebase_architect.application.use_cases.build_code_model import BuildCodeModelUseCase
from codebase_architect.domain.model.code import Language
from codebase_architect.domain.model.source import SourceType
from codebase_architect.domain.model.workspace import Workspace
from codebase_architect.infrastructure.detection.language_detector import ExtensionLanguageDetector
from codebase_architect.infrastructure.detection.manifest_detector import CompositeManifestDetector
from codebase_architect.infrastructure.parsing.tree_sitter_parser import TreeSitterParser
from codebase_architect.shared.ids import new_id


def _build_use_case() -> BuildCodeModelUseCase:
    return BuildCodeModelUseCase(
        language_detector=ExtensionLanguageDetector(),
        parser=TreeSitterParser(),
        manifest_detector=CompositeManifestDetector(),
    )


def _mixed_workspace(root: Path) -> Workspace:
    (root / "backend/src").mkdir(parents=True)
    (root / "backend/src/Greeter.java").write_text(
        "package com.demo;\npublic class Greeter { public void hi() {} }\n",
        encoding="utf-8",
    )
    (root / "backend/build.gradle").write_text(
        "dependencies { implementation 'org.springframework.boot:spring-boot-starter:3.2.0' }\n",
        encoding="utf-8",
    )
    (root / "frontend/src/app").mkdir(parents=True)
    (root / "frontend/src/app/app.component.ts").write_text(
        "import { Component } from '@angular/core';\nexport class AppComponent {}\n",
        encoding="utf-8",
    )
    (root / "frontend/src/app/app.component.html").write_text("<h1>Hi</h1>\n", encoding="utf-8")
    (root / "frontend/package.json").write_text(
        '{ "dependencies": { "@angular/core": "17.0.0" } }', encoding="utf-8"
    )
    (root / "README.md").write_text("# Demo\n", encoding="utf-8")
    return Workspace(id=new_id("ws"), root_path=root, source_type=SourceType.FOLDER)


def test_builds_model_for_java_and_angular(tmp_path: Path) -> None:
    workspace = _mixed_workspace(tmp_path)
    model = _build_use_case().execute(workspace)

    languages = {stat.language for stat in model.language_breakdown()}
    assert {Language.JAVA, Language.TYPESCRIPT, Language.HTML} <= languages

    stack_names = {s.name for s in model.stacks}
    assert {"Gradle", "Spring", "npm", "Angular"} <= stack_names

    assert model.symbol_count >= 3  # Greeter, hi(), AppComponent
    assert model.other_file_count >= 1  # README.md
    assert model.total_loc > 0


def test_empty_workspace_yields_empty_model(tmp_path: Path) -> None:
    workspace = Workspace(id=new_id("ws"), root_path=tmp_path, source_type=SourceType.FOLDER)
    model = _build_use_case().execute(workspace)
    assert model.parsed_files == []
    assert model.language_breakdown() == []
    assert model.symbol_count == 0
