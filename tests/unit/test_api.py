"""Tests for the REST API (in-process, no network)."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from codebase_architect.api.app import create_app
from codebase_architect.shared.config import Settings


@pytest.fixture
def project(tmp_path: Path) -> Path:
    base = tmp_path / "project"
    root = base / "src/main/java/com/demo/web"
    root.mkdir(parents=True)
    (root / "GreetController.java").write_text(
        "package com.demo.web;\n"
        "import org.springframework.web.bind.annotation.RestController;\n"
        "public class GreetController {}\n",
        encoding="utf-8",
    )
    (base / "pom.xml").write_text(
        '<project xmlns="http://maven.apache.org/POM/4.0.0"><dependencies>'
        "<dependency><groupId>org.springframework.boot</groupId>"
        "<artifactId>spring-boot-starter-web</artifactId><version>3.2.0</version></dependency>"
        "</dependencies></project>",
        encoding="utf-8",
    )
    return base


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    settings = Settings(
        workspaces_dir=str(tmp_path / "ws"),
        data_dir=str(tmp_path / "data"),
    )
    return TestClient(create_app(settings))


def _submit(client: TestClient, location: Path) -> str:
    response = client.post("/scans", json={"location": str(location), "static_only": True})
    assert response.status_code == 202
    body = response.json()
    assert body["status"] in ("queued", "done")
    return str(body["id"])


def test_health(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_scan_lifecycle_and_summary(client: TestClient, project: Path) -> None:
    scan_id = _submit(client, project)

    status = client.get(f"/scans/{scan_id}").json()
    assert status["status"] == "done"
    assert status["summary"]["source_type"] == "folder"
    assert status["summary"]["entrypoints"] >= 1
    assert any(s["name"] == "Spring" for s in status["summary"]["stacks"])


def test_documentation_endpoints(client: TestClient, project: Path) -> None:
    scan_id = _submit(client, project)

    docs = client.get(f"/scans/{scan_id}/documentation").json()
    slugs = {p["slug"] for p in docs["pages"]}
    assert {"README", "architecture", "modules"} <= slugs

    code_model = client.get(f"/scans/{scan_id}/code-model").json()
    assert code_model["modules"]
    assert code_model["symbols"] >= 1

    architecture = client.get(f"/scans/{scan_id}/architecture").json()
    assert any(c["module_id"] == "com.demo.web" for c in architecture["components"])


def test_download_returns_zip(client: TestClient, project: Path) -> None:
    scan_id = _submit(client, project)
    response = client.get(f"/scans/{scan_id}/download")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        names = archive.namelist()
    assert "README.md" in names
    assert "architecture.md" in names


def test_unknown_scan_is_404(client: TestClient) -> None:
    assert client.get("/scans/scan_does_not_exist").status_code == 404


def test_list_scans(client: TestClient, project: Path) -> None:
    scan_id = _submit(client, project)
    listed = client.get("/scans").json()
    assert any(item["id"] == scan_id for item in listed)
