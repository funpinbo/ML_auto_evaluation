"""정적 dist 서빙 (ADR-005 §2·§3, ADR-011 §9: SPA 폴백 없음, 405 미가로채기)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from backend_support import (
    TEST_PORT,
    asgi_http,
    assert_error,
    client_for,
    http_scope,
    make_settings,
)

from app.main import create_app
from app.static_files import resolve_static


def test_root_serves_index_no_cache(engine_workspace, dist_dir: Path) -> None:
    client = client_for(engine_workspace("full").root, dist_dir=dist_dir)
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    assert resp.headers["cache-control"] == "no-cache"
    assert "fake dist" in resp.text
    head = client.head("/")
    assert head.status_code == 200 and head.content == b""


def test_assets_immutable(engine_workspace, dist_dir: Path) -> None:
    client = client_for(engine_workspace("full").root, dist_dir=dist_dir)
    resp = client.get("/assets/app-abc123.js")
    assert resp.status_code == 200
    assert "immutable" in resp.headers["cache-control"]


@pytest.mark.parametrize(
    "path", ["/nope", "/assets/nope.js", "/views/home", "/assets/", "/.hidden"]
)
def test_unknown_static_404_no_spa_fallback(
    engine_workspace, dist_dir: Path, path
) -> None:
    client = client_for(engine_workspace("full").root, dist_dir=dist_dir)
    resp = client.get(path)
    assert_error(resp, 404, "NOT_FOUND")
    assert "fake dist" not in resp.text


@pytest.mark.parametrize(
    "path",
    [
        "/../secret.txt",
        "/assets/../../secret.txt",
        "/assets/..",
        "/a\\..\\secret.txt",
        "/C:x",
    ],
)
def test_traversal_paths_rejected_raw_scope(
    engine_workspace, dist_dir: Path, path
) -> None:
    (dist_dir.parent / "secret.txt").write_text("SECRETMARKER", encoding="utf-8")
    app = create_app(make_settings(engine_workspace("full").root, dist_dir=dist_dir))
    resp = asgi_http(
        app, http_scope("GET", path, [(b"host", f"127.0.0.1:{TEST_PORT}".encode())])
    )
    assert resp.status == 404
    assert b"SECRETMARKER" not in resp.body


def test_symlink_escaping_dist_rejected(dist_dir: Path) -> None:
    outside = dist_dir.parent / "outside.txt"
    outside.write_text("SECRETMARKER", encoding="utf-8")
    link = dist_dir / "assets" / "leak.txt"
    try:
        os.symlink(outside, link)
    except (OSError, NotImplementedError):
        pytest.skip("symlink 를 만들 수 없는 환경")
    assert resolve_static(dist_dir, "/assets/leak.txt") is None
    assert resolve_static(dist_dir, "/assets/app-abc123.js") is not None


def test_dist_missing_root_shows_guidance(engine_workspace, tmp_path: Path) -> None:
    client = client_for(
        engine_workspace("full").root, dist_dir=tmp_path / "missing-dist"
    )
    resp = client.get("/")
    assert resp.status_code == 200
    assert "npm run build" in resp.text
    assert_error(client.get("/assets/app.js"), 404, "NOT_FOUND")
    assert client.get("/api/v1/memory").status_code == 200
