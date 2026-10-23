"""GET /api/v1/health — CON-05, NFR-002, ADR-001 §4(런처 식별자), ADR-011(봉투·가드)."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import pytest
from backend_support import (
    OTHER_PORT,
    assert_error,
    build_dist,
    make_client,
    make_settings,
    walk_keys,
)
from fixtures import markers
from fixtures.hashing import hash_tree
from fixtures.runtime_files import control_doc, write_claude_status, write_json

from app import APP_NAME, __version__
from app.main import create_app
from app.models.health import UsageWarming

SOURCES = {"workspace", "claude_projects", "statusline", "control"}


def _client(root: Path, *, claude_home: Path | None = None, dist: Path | None = None):
    app = create_app(make_settings(root, claude_home=claude_home, dist_dir=dist))
    return app, make_client(app)


def _health(client) -> dict[str, Any]:
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200, resp.status_code
    assert resp.headers["content-type"].startswith("application/json")
    return resp.json()


@pytest.fixture
def healthy(full_workspace, claude_home, tmp_path):
    write_claude_status(
        full_workspace.claude_status_file,
        "normal",
        transcript_dir_name=claude_home.dir_name,
    )
    write_json(full_workspace.control_file, control_doc("running"))
    dist = build_dist(tmp_path / "frontend")
    return full_workspace, claude_home, dist


def test_all_sources_ok_envelope(healthy) -> None:
    ws, home, dist = healthy
    _, client = _client(ws.root, claude_home=home.home, dist=dist)
    body = _health(client)
    assert set(body) == {"data", "meta"}
    data, meta = body["data"], body["meta"]
    assert set(data) == {"status", "app", "version", "sources", "dist", "usage_warming"}
    assert data["status"] == "ok"
    assert data["app"] == APP_NAME == "aidlc-monitor"
    assert data["version"] == __version__
    assert data["sources"] == dict.fromkeys(SOURCES, "ok")
    assert data["dist"] == "ok"
    assert data["usage_warming"] == {"state": "not_started", "progress": None}
    assert meta["status"] == "ok"
    assert meta["warnings"] == []
    assert meta["error"] is None


def test_body_has_no_paths_ids_or_markers(healthy) -> None:
    ws, home, dist = healthy
    _, client = _client(ws.root, claude_home=home.home, dist=dist)
    resp = client.get("/api/v1/health")
    text = resp.text + json.dumps(dict(resp.headers))
    forbidden = (*home.forbidden_strings(), str(ws.root), str(dist), ws.root.name)
    markers.assert_no_markers(text, extra=forbidden, where="health")
    assert "/" not in "".join(str(v) for v in _leaves(resp.json()["data"]))
    assert "transcript_dir_name" not in set(walk_keys(resp.json()))


def _leaves(node: Any) -> list[Any]:
    if isinstance(node, dict):
        return [x for v in node.values() for x in _leaves(v)]
    return [node]


def test_missing_sources_are_partial_not_500(empty_workspace, tmp_path) -> None:
    """빈 workspace + CLAUDE_HOME·dist 없음 → 200, 소스별 missing, 경고에 경로 없음."""
    _, client = _client(
        empty_workspace.root,
        claude_home=tmp_path / "no-home",
        dist=tmp_path / "no-dist",
    )
    body = _health(client)
    assert body["data"]["status"] == "ok"
    assert body["data"]["app"] == APP_NAME
    assert body["data"]["sources"] == dict.fromkeys(SOURCES, "missing")
    assert body["data"]["dist"] == "missing"
    assert body["meta"]["status"] == "partial"
    # control 없음은 정상(첫 일시정지 전)이라 경고 없음 → workspace·claude·statusline·dist 4건
    assert len(body["meta"]["warnings"]) == 4
    joined = " ".join(body["meta"]["warnings"])
    for value in (str(empty_workspace.root), str(tmp_path), "no-home", "no-dist"):
        assert value not in joined


def test_broken_workspace_still_200(broken_workspace, tmp_path) -> None:
    _, client = _client(broken_workspace.root, claude_home=tmp_path / "x")
    body = _health(client)
    assert body["data"]["app"] == APP_NAME
    assert body["data"]["sources"]["workspace"] == "ok"


def test_wrong_kind_is_unreadable(empty_workspace, tmp_path) -> None:
    """디렉터리 자리에 파일, 파일 자리에 디렉터리 → unreadable (내용은 읽지 않는다)."""
    mem = empty_workspace.memory
    mem.write_text("not a dir", encoding="utf-8")
    home = tmp_path / "home"
    home.mkdir()
    (home / "projects").write_text("x", encoding="utf-8")
    _, client = _client(empty_workspace.root, claude_home=home)
    sources = _health(client)["data"]["sources"]
    assert sources["workspace"] == "unreadable"
    assert sources["claude_projects"] == "unreadable"
    # memory 가 파일이면 그 아래 파일은 NotADirectory → missing
    assert sources["statusline"] == "missing"
    assert sources["control"] == "missing"


def test_control_dir_in_place_of_file_is_unreadable(
    full_workspace, claude_home
) -> None:
    full_workspace.control_file.mkdir(parents=True)
    _, client = _client(full_workspace.root, claude_home=claude_home.home)
    body = _health(client)
    assert body["data"]["sources"]["control"] == "unreadable"
    assert body["meta"]["status"] == "partial"


def test_stale_statusline_snapshot(healthy) -> None:
    ws, home, dist = healthy
    old = time.time() - 3600
    os.utime(ws.claude_status_file, (old, old))
    _, client = _client(ws.root, claude_home=home.home, dist=dist)
    body = _health(client)
    assert body["data"]["sources"]["statusline"] == "stale"
    assert body["meta"]["status"] == "partial"
    assert len(body["meta"]["warnings"]) == 1


def test_stat_error_is_isolated(healthy, monkeypatch) -> None:
    """stat 이 권한 오류를 내도 그 소스만 unreadable, 응답은 200."""
    ws, home, dist = healthy
    real_stat = os.stat
    target = str(home.projects_dir)

    def fake_stat(path, *args, **kwargs):
        if str(path) == target:
            raise PermissionError(13, "denied")
        return real_stat(path, *args, **kwargs)

    _, client = _client(ws.root, claude_home=home.home, dist=dist)
    monkeypatch.setattr("app.api.health.os.stat", fake_stat)
    body = _health(client)
    assert body["data"]["sources"]["claude_projects"] == "unreadable"
    assert body["data"]["sources"]["workspace"] == "ok"


def test_health_is_read_only(healthy) -> None:
    ws, home, dist = healthy
    before = (hash_tree(ws.root), hash_tree(home.home))
    _, client = _client(ws.root, claude_home=home.home, dist=dist)
    for _ in range(3):
        _health(client)
    assert (hash_tree(ws.root), hash_tree(home.home)) == before
    assert not list(ws.root.rglob("__pycache__"))


def test_health_does_not_open_files(healthy, monkeypatch) -> None:
    """stat 만 쓴다 — 스냅샷(transcript_dir_name 포함)·인증 decoy 를 열지 않는다."""
    ws, home, dist = healthy
    _, client = _client(ws.root, claude_home=home.home, dist=dist)
    opened: list[str] = []
    import builtins
    import io

    real_open = builtins.open

    def spy_open(file, *args, **kwargs):
        opened.append(str(file))
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", spy_open)
    monkeypatch.setattr(io, "open", spy_open)
    _health(client)
    roots = (str(ws.root), str(home.home))
    assert not [p for p in opened if p.startswith(roots)]


class _Provider:
    def __init__(self, value: Any) -> None:
        self.value = value

    def progress(self) -> Any:
        if isinstance(self.value, Exception):
            raise self.value
        return self.value


@pytest.mark.parametrize(
    ("value", "expected", "meta_status"),
    [
        (
            {"state": "warming", "progress": 0.25},
            {"state": "warming", "progress": 0.25},
            "warming",
        ),
        (
            UsageWarming(state="done", progress=1.0),
            {"state": "done", "progress": 1.0},
            "ok",
        ),
        ({"state": "bogus"}, {"state": "unknown", "progress": None}, "ok"),
        (
            RuntimeError("boom /secret/path"),
            {"state": "unknown", "progress": None},
            "ok",
        ),
    ],
)
def test_warmup_provider(healthy, value, expected, meta_status) -> None:
    ws, home, dist = healthy
    app, client = _client(ws.root, claude_home=home.home, dist=dist)
    app.state.warmup = _Provider(value)
    body = _health(client)
    assert body["data"]["usage_warming"] == expected
    assert body["meta"]["status"] == meta_status


def test_warming_does_not_hide_problems(empty_workspace, tmp_path) -> None:
    app, client = _client(empty_workspace.root, claude_home=tmp_path / "none")
    app.state.warmup = _Provider({"state": "warming", "progress": 0.5})
    assert _health(client)["meta"]["status"] == "partial"


# ---------------------------------------------------------------- 가드는 health 에도 적용된다
def test_host_guard_applies(healthy) -> None:
    ws, home, dist = healthy
    app = create_app(make_settings(ws.root, claude_home=home.home, dist_dir=dist))
    from fastapi.testclient import TestClient

    bad = TestClient(app, base_url="http://testserver", raise_server_exceptions=False)
    assert_error(bad.get("/api/v1/health"), 400, "BAD_HOST")
    other = TestClient(
        app, base_url=f"http://127.0.0.1:{OTHER_PORT}", raise_server_exceptions=False
    )
    resp = other.get("/api/v1/health")
    body = assert_error(resp, 400, "BAD_HOST")
    assert str(OTHER_PORT) not in body["error"]["message"]
    ok = make_client(app).get(
        "/api/v1/health", headers={"host": f"LOCALHOST:{app.settings.port}"}
    )
    assert ok.status_code == 200


@pytest.mark.parametrize("method", ["POST", "PUT", "DELETE", "OPTIONS", "HEAD"])
def test_other_methods_405(healthy, method) -> None:
    ws, home, dist = healthy
    _, client = _client(ws.root, claude_home=home.home, dist=dist)
    resp = client.request(
        method, "/api/v1/health", headers={"content-type": "application/json"}
    )
    assert resp.status_code == 405
    assert resp.headers["allow"] == "GET"


def test_openapi_documents_health(healthy) -> None:
    ws, home, dist = healthy
    app, _ = _client(ws.root, claude_home=home.home, dist=dist)
    spec = app.openapi()
    op = spec["paths"]["/api/v1/health"]["get"]
    assert set(spec["paths"]["/api/v1/health"]) == {"get"}
    schemas = spec["components"]["schemas"]
    assert "HealthData" in schemas
    assert schemas["HealthData"]["properties"]["app"]["const"] == "aidlc-monitor"
    assert "200" in op["responses"]
