"""Detect technology stacks and dependencies from project manifests.

Best-effort and resilient: a malformed manifest yields no results for that file
rather than failing the scan. Focused on the stacks that matter most here —
Maven/Gradle (Java/Kotlin) and npm/Angular.
"""

from __future__ import annotations

import json
import re
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path

from codebase_architect.domain.model.stack import (
    Dependency,
    DetectedStack,
    StackCategory,
)
from codebase_architect.domain.model.workspace import Workspace
from codebase_architect.domain.ports.analysis import ManifestDetector

_GRADLE_DEP = re.compile(
    r"""(?P<conf>implementation|api|compileOnly|runtimeOnly|annotationProcessor|kapt|
         testImplementation|testRuntimeOnly)
        \s*[(]?\s*['"](?P<coord>[^'"]+)['"]""",
    re.VERBOSE,
)


class CompositeManifestDetector(ManifestDetector):
    """Runs every built-in manifest detector over the workspace."""

    def detect(self, workspace: Workspace) -> tuple[list[DetectedStack], list[Dependency]]:
        stacks: list[DetectedStack] = []
        deps: list[Dependency] = []

        for path in workspace.iter_files():
            rel = workspace.relative(path)
            name = path.name.lower()
            try:
                if name == "pom.xml":
                    self._maven(path, rel, stacks, deps)
                elif name in {"build.gradle", "build.gradle.kts"}:
                    self._gradle(path, rel, stacks, deps)
                elif name in {"settings.gradle", "settings.gradle.kts"}:
                    _add(stacks, DetectedStack("Gradle", StackCategory.BUILD_TOOL, rel))
                elif name == "package.json":
                    self._npm(path, rel, stacks, deps)
                elif name == "angular.json":
                    _add(stacks, DetectedStack("Angular", StackCategory.FRAMEWORK, rel))
                elif name == "pyproject.toml":
                    self._pyproject(path, rel, stacks, deps)
                elif name == "requirements.txt":
                    self._requirements(path, rel, stacks, deps)
                elif name == "setup.py":
                    _add(stacks, DetectedStack("Python", StackCategory.RUNTIME, rel))
            except (OSError, ValueError, ET.ParseError, json.JSONDecodeError):
                continue

        return _dedupe_stacks(stacks), deps

    # -- Maven ---------------------------------------------------------------
    def _maven(
        self, path: Path, rel: str, stacks: list[DetectedStack], deps: list[Dependency]
    ) -> None:
        _add(stacks, DetectedStack("Maven", StackCategory.BUILD_TOOL, rel))
        root = ET.fromstring(path.read_text(encoding="utf-8", errors="replace"))
        for dep in _iter_local(root, "dependency"):
            group = _text(dep, "groupId")
            artifact = _text(dep, "artifactId")
            if not artifact:
                continue
            full = f"{group}:{artifact}" if group else artifact
            deps.append(
                Dependency(
                    name=full,
                    version=_text(dep, "version"),
                    manifest=rel,
                    scope=_text(dep, "scope"),
                )
            )
            if group and group.startswith("org.springframework"):
                _add(stacks, DetectedStack("Spring", StackCategory.FRAMEWORK, rel))

    # -- Gradle --------------------------------------------------------------
    def _gradle(
        self, path: Path, rel: str, stacks: list[DetectedStack], deps: list[Dependency]
    ) -> None:
        _add(stacks, DetectedStack("Gradle", StackCategory.BUILD_TOOL, rel))
        text = path.read_text(encoding="utf-8", errors="replace")
        if "org.springframework" in text or "spring-boot" in text:
            _add(stacks, DetectedStack("Spring", StackCategory.FRAMEWORK, rel))
        if "com.android" in text:
            _add(stacks, DetectedStack("Android", StackCategory.FRAMEWORK, rel))
        for match in _GRADLE_DEP.finditer(text):
            coord = match.group("coord")
            conf = match.group("conf")
            parts = coord.split(":")
            name = ":".join(parts[:2]) if len(parts) >= 2 else coord
            version = parts[2] if len(parts) >= 3 else None
            scope = "test" if conf.startswith("test") else "compile"
            deps.append(Dependency(name=name, version=version, manifest=rel, scope=scope))

    # -- npm / Angular -------------------------------------------------------
    def _npm(
        self, path: Path, rel: str, stacks: list[DetectedStack], deps: list[Dependency]
    ) -> None:
        _add(stacks, DetectedStack("npm", StackCategory.PACKAGE_MANAGER, rel))
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        for scope, key in (("compile", "dependencies"), ("dev", "devDependencies")):
            section = data.get(key, {})
            if not isinstance(section, dict):
                continue
            for dep_name, version in section.items():
                deps.append(
                    Dependency(
                        name=str(dep_name),
                        version=str(version),
                        manifest=rel,
                        scope=scope,
                    )
                )
                if dep_name == "@angular/core":
                    _add(
                        stacks,
                        DetectedStack("Angular", StackCategory.FRAMEWORK, rel, str(version)),
                    )


    # -- Python --------------------------------------------------------------
    def _pyproject(
        self, path: Path, rel: str, stacks: list[DetectedStack], deps: list[Dependency]
    ) -> None:
        _add(stacks, DetectedStack("Python", StackCategory.RUNTIME, rel))
        data = tomllib.loads(path.read_text(encoding="utf-8", errors="replace"))
        project = data.get("project", {})
        tool = data.get("tool", {})

        if isinstance(tool, dict) and "poetry" in tool:
            _add(stacks, DetectedStack("Poetry", StackCategory.PACKAGE_MANAGER, rel))
            poetry = tool["poetry"]
            if isinstance(poetry, dict):
                for dep_name in poetry.get("dependencies", {}):
                    if str(dep_name).lower() != "python":
                        deps.append(Dependency(str(dep_name), None, rel))
        else:
            _add(stacks, DetectedStack("pip", StackCategory.PACKAGE_MANAGER, rel))

        if isinstance(project, dict):
            for spec in project.get("dependencies", []):
                name = _pep508_name(str(spec))
                if name:
                    deps.append(Dependency(name, None, rel))
            extras = project.get("optional-dependencies", {})
            if isinstance(extras, dict):
                for group, specs in extras.items():
                    for spec in specs if isinstance(specs, list) else []:
                        name = _pep508_name(str(spec))
                        if name:
                            deps.append(Dependency(name, None, rel, scope=str(group)))

        self._py_frameworks(deps, rel, stacks)

    def _requirements(
        self, path: Path, rel: str, stacks: list[DetectedStack], deps: list[Dependency]
    ) -> None:
        _add(stacks, DetectedStack("Python", StackCategory.RUNTIME, rel))
        _add(stacks, DetectedStack("pip", StackCategory.PACKAGE_MANAGER, rel))
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith(("#", "-")):
                continue
            name = _pep508_name(line)
            if name:
                deps.append(Dependency(name, None, rel))
        self._py_frameworks(deps, rel, stacks)

    def _py_frameworks(
        self, deps: list[Dependency], rel: str, stacks: list[DetectedStack]
    ) -> None:
        names = {d.name.lower() for d in deps}
        for pkg, label in (
            ("fastapi", "FastAPI"),
            ("django", "Django"),
            ("flask", "Flask"),
        ):
            if pkg in names:
                _add(stacks, DetectedStack(label, StackCategory.FRAMEWORK, rel))


def _pep508_name(spec: str) -> str | None:
    match = re.match(r"[A-Za-z0-9][A-Za-z0-9._-]*", spec.strip())
    return match.group(0) if match else None


def _add(stacks: list[DetectedStack], stack: DetectedStack) -> None:
    stacks.append(stack)


def _dedupe_stacks(stacks: list[DetectedStack]) -> list[DetectedStack]:
    seen: set[tuple[str, str]] = set()
    result: list[DetectedStack] = []
    for stack in stacks:
        key = (stack.name, stack.category)
        if key not in seen:
            seen.add(key)
            result.append(stack)
    return result


def _iter_local(root: ET.Element, local_name: str) -> list[ET.Element]:
    return [el for el in root.iter() if _local(el.tag) == local_name]


def _text(parent: ET.Element, local_name: str) -> str | None:
    for child in parent:
        if _local(child.tag) == local_name:
            return (child.text or "").strip() or None
    return None


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]
