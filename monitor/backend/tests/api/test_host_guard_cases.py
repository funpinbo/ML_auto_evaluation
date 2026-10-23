"""privacy.md §5.1 H-01~H-22 (N-02) — Host 가드 (D-18, D-25, ADR-011 §4).

`*` 행은 4개 대상(GET /api/v1/health, POST /api/v1/control/pause, GET /api/v1/events, GET /) 각각에 대해
원시 ASGI scope 로 실행한다(Host 0개·2개·빈 값까지 정확히 구성 — H-16~H-19). 통과 행은 가드를 지나
핸들러(대역·실제 라우트·dist index)에 닿음을 확인한다 — pause 는 실제 라우트라 활성 루프 없음 409(I-25). 거부 행은 400 `BAD_HOST`, 메시지에 받은 Host
미포함, 보안 헤더 포함, workspace(.control.json 포함) 해시 불변.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from backend_support import (
    BASE_URL,
    GUARD_REJECT_STATUSES,
    ORIGIN,
    OTHER_PORT,
    TEST_PORT,
    add_stub_targets,
    asgi_http,
    assert_error,
    http_scope,
    make_client,
    make_settings,
)
from fixtures.hashing import hash_tree

from app.main import create_app

P = TEST_PORT
OK_HOST = f"127.0.0.1:{P}"

TARGETS = {
    "health": ("GET", "/api/v1/health"),
    "pause": ("POST", "/api/v1/control/pause"),
    "events": ("GET", "/api/v1/events"),
    "dist": ("GET", "/"),
}

# case id -> (Host 헤더 값 목록, 통과 여부)
STAR_CASES: dict[str, tuple[list[str], bool]] = {
    "H-01": ([f"127.0.0.1:{P}"], True),
    "H-02": ([f"localhost:{P}"], True),
    "H-03": ([f"LOCALHOST:{P}"], True),
    "H-04": (["127.0.0.1:1"], False),
    "H-05": ([f"localhost:{OTHER_PORT}"], False),
    "H-06": (["127.0.0.1"], False),
    "H-07": (["localhost"], False),
    "H-08": ([f"[::1]:{P}"], False),
    "H-09": ([f"localhost.:{P}"], False),
    "H-10": ([f"127.0.0.1:0{P}"], False),
    "H-11": ([f"user@127.0.0.1:{P}"], False),
    "H-12": ([f"127.0.0.1:{P}:x"], False),
    "H-13": ([f"localhost.evil.com:{P}"], False),
    "H-14": (["evil.example"], False),
    "H-15": ([f"192.168.0.10:{P}"], False),
    "H-16": ([""], False),
    "H-17": ([], False),
    "H-18": ([OK_HOST, OK_HOST], False),
    "H-19": ([OK_HOST, "evil.example"], False),
}


@pytest.fixture
def guarded(engine_workspace, dist_dir: Path):
    info = engine_workspace("full")
    app = create_app(make_settings(info.root, dist_dir=dist_dir))
    add_stub_targets(app)
    return app, info


def _headers(hosts: list[str], method: str) -> list[tuple[bytes, bytes]]:
    headers = [(b"host", h.encode("latin-1")) for h in hosts]
    if method == "POST":
        headers += [
            (b"content-type", b"application/json"),
            (b"origin", ORIGIN.encode()),
        ]
    return headers


def _assert_rejected(resp, hosts: list[str]) -> None:
    assert resp.status == 400
    body = resp.json()
    assert body == {"error": {"code": "BAD_HOST", "message": body["error"]["message"]}}
    for host in hosts:
        if host and host != OK_HOST:
            assert host.lower() not in body["error"]["message"].lower()
    assert "detail" not in body
    assert resp.header("x-content-type-options") == "nosniff"
    assert resp.header("referrer-policy") == "no-referrer"
    assert resp.header("content-security-policy")


@pytest.mark.parametrize("target", sorted(TARGETS))
@pytest.mark.parametrize("case", sorted(STAR_CASES))
def test_host_cases_star(guarded, case: str, target: str) -> None:
    app, info = guarded
    hosts, should_pass = STAR_CASES[case]
    method, path = TARGETS[target]
    before = hash_tree(info.root)
    body = b"{}" if method == "POST" else b""
    resp = asgi_http(app, http_scope(method, path, _headers(hosts, method)), body)
    if should_pass:
        # I-25: 실제 pause 라우트 — 활성 루프가 없는 workspace 라 409 NO_ACTIVE_LOOP (가드는 통과)
        expected = 409 if target == "pause" else 200
        assert resp.status not in GUARD_REJECT_STATUSES
        assert resp.status == expected, (case, target, resp.status, resp.body[:200])
    else:
        _assert_rejected(resp, hosts)
    assert hash_tree(info.root) == before
    assert not info.control_file.exists() or target != "pause"


def test_h20_testserver_default_host(guarded) -> None:
    app, _ = guarded
    resp = asgi_http(
        app, http_scope("GET", "/api/v1/health", [(b"host", b"testserver")])
    )
    _assert_rejected(resp, ["testserver"])


def test_h20_testclient_without_base_url_is_rejected(guarded) -> None:
    from fastapi.testclient import TestClient

    app, _ = guarded
    client = TestClient(app)  # 기본 Host = testserver
    assert_error(client.get("/api/v1/health"), 400, "BAD_HOST")


def test_h21_host_checked_before_origin_and_content_type(guarded) -> None:
    app, info = guarded
    before = hash_tree(info.root)
    headers = [
        (b"host", b"evil.example"),
        (b"content-type", b"text/plain"),
        (b"origin", b"http://evil.example"),
    ]
    resp = asgi_http(
        app, http_scope("POST", "/api/v1/control/pause", headers), b"not json"
    )
    _assert_rejected(resp, ["evil.example"])
    assert hash_tree(info.root) == before


@pytest.mark.parametrize("path", ["/api/v1/nope", "/assets/nope.js"])
def test_h22_host_checked_before_routing(guarded, path: str) -> None:
    app, _ = guarded
    resp = asgi_http(app, http_scope("GET", path, [(b"host", b"evil.example")]))
    _assert_rejected(resp, ["evil.example"])


@pytest.mark.parametrize(
    "host",
    [f"127.0.0.1:{P}", f"localhost:{P}", f"LOCALHOST:{P}", f"  127.0.0.1:{P}  "],
)
def test_testclient_allowed_hosts(guarded, host: str) -> None:
    app, _ = guarded
    client = make_client(app)
    assert client.base_url == BASE_URL
    resp = client.get("/api/v1/pipeline", headers={"host": host})
    assert resp.status_code == 200


@pytest.mark.parametrize(
    "host",
    ["127.0.0.1:1", f"localhost:{OTHER_PORT}", "evil.example", f"127.0.0.1:0{P}"],
)
def test_testclient_rejected_hosts(guarded, host: str) -> None:
    app, _ = guarded
    body = assert_error(
        make_client(app).get("/api/v1/pipeline", headers={"host": host}),
        400,
        "BAD_HOST",
    )
    assert host not in body["error"]["message"]
