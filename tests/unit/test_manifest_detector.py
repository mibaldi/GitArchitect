"""Tests for CompositeManifestDetector."""

from __future__ import annotations

from pathlib import Path

from codebase_architect.domain.model.source import SourceType
from codebase_architect.domain.model.workspace import Workspace
from codebase_architect.infrastructure.detection.manifest_detector import CompositeManifestDetector
from codebase_architect.shared.ids import new_id


def _workspace(root: Path) -> Workspace:
    return Workspace(id=new_id("ws"), root_path=root, source_type=SourceType.FOLDER)


def _names(stacks: list) -> set[str]:
    return {s.name for s in stacks}


def test_maven_with_spring(tmp_path: Path) -> None:
    (tmp_path / "pom.xml").write_text(
        """<project xmlns="http://maven.apache.org/POM/4.0.0">
          <dependencies>
            <dependency>
              <groupId>org.springframework.boot</groupId>
              <artifactId>spring-boot-starter-web</artifactId>
              <version>3.2.0</version>
            </dependency>
          </dependencies>
        </project>""",
        encoding="utf-8",
    )
    stacks, deps = CompositeManifestDetector().detect(_workspace(tmp_path))
    assert {"Maven", "Spring"} <= _names(stacks)
    assert deps[0].name == "org.springframework.boot:spring-boot-starter-web"
    assert deps[0].version == "3.2.0"


def test_gradle(tmp_path: Path) -> None:
    (tmp_path / "build.gradle").write_text(
        """dependencies {
            implementation 'org.springframework.boot:spring-boot-starter:3.2.0'
            testImplementation "junit:junit:4.13"
        }""",
        encoding="utf-8",
    )
    stacks, deps = CompositeManifestDetector().detect(_workspace(tmp_path))
    assert {"Gradle", "Spring"} <= _names(stacks)
    names = {d.name for d in deps}
    assert "org.springframework.boot:spring-boot-starter" in names
    assert any(d.scope == "test" for d in deps)


def test_npm_angular(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text(
        """{
          "dependencies": { "@angular/core": "17.0.0", "rxjs": "7.8.0" },
          "devDependencies": { "typescript": "5.4.0" }
        }""",
        encoding="utf-8",
    )
    (tmp_path / "angular.json").write_text("{}", encoding="utf-8")
    stacks, deps = CompositeManifestDetector().detect(_workspace(tmp_path))
    assert {"npm", "Angular"} <= _names(stacks)
    # Angular detected once despite two evidence sources.
    assert sum(1 for s in stacks if s.name == "Angular") == 1
    assert any(d.name == "typescript" and d.scope == "dev" for d in deps)


def test_pyproject_pep621_fastapi(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        """[project]
name = "demo"
dependencies = ["fastapi>=0.110", "pydantic>=2.6"]

[project.optional-dependencies]
dev = ["pytest>=8.2"]
""",
        encoding="utf-8",
    )
    stacks, deps = CompositeManifestDetector().detect(_workspace(tmp_path))
    assert {"Python", "pip", "FastAPI"} <= _names(stacks)
    names = {d.name for d in deps}
    assert {"fastapi", "pydantic"} <= names
    assert any(d.name == "pytest" and d.scope == "dev" for d in deps)


def test_requirements_txt(tmp_path: Path) -> None:
    (tmp_path / "requirements.txt").write_text(
        "# comment\nflask==3.0.0\n-r other.txt\nrequests>=2.31\n",
        encoding="utf-8",
    )
    stacks, deps = CompositeManifestDetector().detect(_workspace(tmp_path))
    assert {"Python", "pip", "Flask"} <= _names(stacks)
    names = {d.name for d in deps}
    assert {"flask", "requests"} <= names


def test_malformed_manifest_is_skipped(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text("{ not valid json", encoding="utf-8")
    stacks, deps = CompositeManifestDetector().detect(_workspace(tmp_path))
    # npm stack still detected from the file's presence; deps simply empty.
    assert "npm" in _names(stacks)
    assert deps == []
