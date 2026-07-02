"""Tests for the REST API (in-process, no network)."""

from __future__ import annotations

import io
import tempfile
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


def test_dashboard_served_at_root(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Codebase Architect" in response.text


def test_page_content_endpoint(client: TestClient, project: Path) -> None:
    scan_id = _submit(client, project)
    page = client.get(f"/scans/{scan_id}/pages/README").json()
    assert page["slug"] == "README"
    assert page["markdown"].startswith("# ")
    # Unknown page is a 404.
    assert client.get(f"/scans/{scan_id}/pages/nope").status_code == 404


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


def test_scan_tags_and_meta_edit(client: TestClient, project: Path) -> None:
    resp = client.post(
        "/scans", json={"location": str(project), "static_only": True, "tags": ["backend"]}
    )
    scan_id = resp.json()["id"]
    assert resp.json()["tags"] == ["backend"]

    # rename + re-tag after the fact
    meta = client.put(
        f"/scans/{scan_id}/meta", json={"title": "Orders API", "tags": ["backend", "orders"]}
    ).json()
    assert meta["title"] == "Orders API"
    assert meta["tags"] == ["backend", "orders"]

    # surfaced in the list and the status
    listed = {s["id"]: s for s in client.get("/scans").json()}
    assert listed[scan_id]["title"] == "Orders API"
    assert listed[scan_id]["tags"] == ["backend", "orders"]
    assert client.get(f"/scans/{scan_id}").json()["tags"] == ["backend", "orders"]


def test_scan_meta_unknown_is_404(client: TestClient) -> None:
    assert client.put("/scans/scan_missing/meta", json={"tags": ["x"]}).status_code == 404


def test_tags_survive_restart(tmp_path: Path, project: Path) -> None:
    settings = Settings(workspaces_dir=str(tmp_path / "ws"), data_dir=str(tmp_path / "data"))
    first = TestClient(create_app(settings))
    scan_id = first.post(
        "/scans", json={"location": str(project), "static_only": True, "tags": ["frontend"]}
    ).json()["id"]
    second = TestClient(create_app(settings))
    assert second.get(f"/scans/{scan_id}").json()["tags"] == ["frontend"]


def test_runner_check_unreachable(client: TestClient) -> None:
    resp = client.post("/ai/runner-check", json={"base_url": "http://127.0.0.1:1"})
    assert resp.status_code == 200
    assert resp.json() == {"reachable": False, "detail": "not reachable"}


def _zip_bytes() -> io.BytesIO:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        archive.writestr(
            "proj/src/main/java/com/demo/web/GreetController.java",
            "package com.demo.web;\n"
            "import org.springframework.web.bind.annotation.RestController;\n"
            "public class GreetController {}\n",
        )
    buf.seek(0)
    return buf


def test_upload_archive_is_scanned_then_discarded(client: TestClient) -> None:
    response = client.post(
        "/scans/upload",
        files={"file": ("proj.zip", _zip_bytes(), "application/zip")},
        data={"static_only": "true", "title": "Uploaded"},
    )
    assert response.status_code == 202
    scan_id = response.json()["id"]

    status = client.get(f"/scans/{scan_id}").json()
    assert status["status"] == "done"
    assert status["summary"]["entrypoints"] >= 1
    # The temporary upload file is cleaned up after the background scan runs.
    assert not list(Path(tempfile.gettempdir()).glob("ca-upload-*"))


def test_upload_rejects_unsupported_type(client: TestClient) -> None:
    response = client.post(
        "/scans/upload",
        files={"file": ("notes.txt", io.BytesIO(b"hello"), "text/plain")},
    )
    assert response.status_code == 400


def _spec_payload() -> dict:
    return {
        "product": "Demo",
        "objective": "Greet people",
        "actors": ["User"],
        "features": [
            {
                "name": "Greet",
                "actors": ["User"],
                "goal": "Say hi",
                "main_flow": [
                    {"actor": "User", "action": "opens app", "target": "Frontend"},
                    {"actor": "Frontend", "action": "GET /greet", "target": "Backend"},
                ],
                "systems": ["Frontend", "Backend"],
                "endpoints": [{"method": "GET", "path": "/greet"}],
            }
        ],
    }


def test_spec_crud_and_persistence(tmp_path: Path) -> None:
    settings = Settings(
        workspaces_dir=str(tmp_path / "ws"),
        data_dir=str(tmp_path / "data"),
    )
    app = TestClient(create_app(settings))

    created = app.post("/specs", json=_spec_payload())
    assert created.status_code == 201
    spec_id = created.json()["id"]
    assert created.json()["features"][0]["main_flow"][1]["target"] == "Backend"

    # Update preserves id, list shows a summary.
    payload = _spec_payload()
    payload["product"] = "Renamed"
    assert app.put(f"/specs/{spec_id}", json=payload).json()["product"] == "Renamed"
    summaries = app.get("/specs").json()
    assert summaries[0]["id"] == spec_id and summaries[0]["features"] == 1

    # A fresh app over the same data dir still has the spec.
    restarted = TestClient(create_app(settings))
    got = restarted.get(f"/specs/{spec_id}").json()
    assert got["product"] == "Renamed"
    assert got["features"][0]["endpoints"][0] == {"method": "GET", "path": "/greet"}

    assert restarted.delete(f"/specs/{spec_id}").status_code == 204
    assert restarted.get(f"/specs/{spec_id}").status_code == 404


def test_reconcile_spec_against_scan(client: TestClient, project: Path) -> None:
    scan_id = _submit(client, project)
    payload = _spec_payload()
    payload["features"] = [
        {
            "name": "Greet users",
            "systems": ["Greet"],
            "endpoints": [{"method": "GET", "path": "/greet"}],
        },
        {"name": "Generate billing invoices"},
    ]
    spec_id = client.post("/specs", json=payload).json()["id"]

    report = client.get(f"/specs/{spec_id}/reconcile/{scan_id}").json()
    assert report["implemented"] + report["partial"] + report["missing"] == 2
    statuses = {c["feature"]: c["status"] for c in report["coverage"]}
    assert statuses["Greet users"] in ("implemented", "partial")
    assert statuses["Generate billing invoices"] == "missing"

    # The scan is now linked to the spec.
    assert scan_id in client.get(f"/specs/{spec_id}").json()["linked_scan_ids"]


def test_api_flow_across_separately_scanned_projects(
    client: TestClient, tmp_path: Path
) -> None:
    back = tmp_path / "back" / "src"
    back.mkdir(parents=True)
    (back / "GreetController.java").write_text(
        "package com.demo;\n"
        "@RestController\n"
        '@RequestMapping("/api")\n'
        "public class GreetController {\n"
        '  @GetMapping("/greet")\n'
        "  public String g() { return \"\"; }\n"
        "}\n",
        encoding="utf-8",
    )
    front = tmp_path / "front" / "src"
    front.mkdir(parents=True)
    (front / "greet.service.ts").write_text(
        "export class GreetService {\n"
        "  constructor(private http) {}\n"
        "  g() { return this.http.get('/api/greet'); }\n"
        "}\n",
        encoding="utf-8",
    )
    back_id = _submit(client, tmp_path / "back")
    front_id = _submit(client, tmp_path / "front")
    spec_id = client.post("/specs", json=_spec_payload()).json()["id"]
    client.post(f"/specs/{spec_id}/scans/{back_id}")
    client.post(f"/specs/{spec_id}/scans/{front_id}")

    flow = client.get(f"/specs/{spec_id}/api-flow").json()
    assert any(
        e["from_scan"] == front_id and e["to_scan"] == back_id and e["path"] == "/api/greet"
        for e in flow["edges"]
    )


def test_sequence_diagrams_endpoint(client: TestClient) -> None:
    payload = _spec_payload()  # has a "Greet" feature with a main_flow
    spec_id = client.post("/specs", json=payload).json()["id"]
    resp = client.get(f"/specs/{spec_id}/sequence").json()
    assert resp["spec_id"] == spec_id
    assert len(resp["diagrams"]) == 1
    mermaid = resp["diagrams"][0]["mermaid"]
    assert mermaid.startswith("sequenceDiagram")
    assert "Frontend" in mermaid and "Backend" in mermaid


def test_spec_document_downloadable(client: TestClient, project: Path) -> None:
    scan_id = _submit(client, project)
    spec_id = client.post("/specs", json=_spec_payload()).json()["id"]
    client.post(f"/specs/{spec_id}/scans/{scan_id}")

    resp = client.post(f"/specs/{spec_id}/document", json={})
    assert resp.status_code == 200
    assert "text/markdown" in resp.headers["content-type"]
    assert "attachment" in resp.headers["content-disposition"]
    body = resp.text
    assert "# Demo — Functional documentation" in body
    assert "## Functionalities" in body
    assert "sequenceDiagram" in body
    assert "## Cross-project API flow" in body


def test_scans_persist_across_restart(tmp_path: Path, project: Path) -> None:
    settings = Settings(
        workspaces_dir=str(tmp_path / "ws"),
        data_dir=str(tmp_path / "data"),
    )
    first = TestClient(create_app(settings))
    scan_id = _submit(first, project)
    assert first.get(f"/scans/{scan_id}").json()["status"] == "done"

    # A fresh app over the same data dir restores history and serves the docs.
    second = TestClient(create_app(settings))
    listed = {s["id"] for s in second.get("/scans").json()}
    assert scan_id in listed
    status = second.get(f"/scans/{scan_id}").json()
    assert status["status"] == "done"
    assert status["summary"]["entrypoints"] >= 1
    page = second.get(f"/scans/{scan_id}/pages/architecture").json()
    assert page["markdown"].startswith("# ")


def test_credentials_accepted_but_never_echoed(client: TestClient, project: Path) -> None:
    response = client.post(
        "/scans",
        json={
            "location": str(project),
            "static_only": True,
            "ai_provider": "local",
            "ai_api_key": "sk-super-secret",
            "ai_base_url": "http://100.9.9.9:11434/v1",
            "ai_model": "llama3",
        },
    )
    assert response.status_code == 202
    scan_id = response.json()["id"]
    status = client.get(f"/scans/{scan_id}").text
    # The key/endpoint are kept in memory only — never returned in any response.
    assert "sk-super-secret" not in status
    assert "100.9.9.9" not in status


def test_scan_request_accepts_spanish_language_and_localizes_docs(
    client: TestClient, project: Path
) -> None:
    response = client.post(
        "/scans", json={"location": str(project), "static_only": True, "language": "es"}
    )
    assert response.status_code == 202
    scan_id = response.json()["id"]

    docs = client.get(f"/scans/{scan_id}/documentation").json()
    titles = {p["slug"]: p["title"] for p in docs["pages"]}
    assert titles["architecture"] == "Arquitectura"


def test_scan_request_defaults_to_english_language(client: TestClient, project: Path) -> None:
    scan_id = _submit(client, project)
    docs = client.get(f"/scans/{scan_id}/documentation").json()
    titles = {p["slug"]: p["title"] for p in docs["pages"]}
    assert titles["architecture"] == "Architecture"


def test_scan_request_rejects_invalid_language(client: TestClient, project: Path) -> None:
    response = client.post(
        "/scans", json={"location": str(project), "static_only": True, "language": "de"}
    )
    assert response.status_code == 422


def test_scan_upload_rejects_invalid_language(client: TestClient) -> None:
    response = client.post(
        "/scans/upload",
        files={"file": ("code.zip", b"not-a-real-zip", "application/zip")},
        data={"language": "de"},
    )
    assert response.status_code == 422


def test_list_scans(client: TestClient, project: Path) -> None:
    scan_id = _submit(client, project)
    listed = client.get("/scans").json()
    assert any(item["id"] == scan_id for item in listed)
