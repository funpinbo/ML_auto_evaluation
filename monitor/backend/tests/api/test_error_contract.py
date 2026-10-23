"""ADR-011 §9~§12 — 닫힌 에러 코드 9개, `{"detail"}` 금지, 404/405(+Allow)/OPTIONS, scope 처리, 보안 헤더.

LTM I-21 실측: FastAPI 0.161.1 `APIRoute` 는 GET 에 HEAD 를 자동으로 붙이지 않는다(→ HEAD 405
`Allow: GET`). Starlette `Route`(순수) 는 붙인다. 라우터 FULL 매치가 PARTIAL 보다 우선이므로 정적 서빙은
라우터 기본 처리기에 두어 405 를 가로채지 않음을 고정한다.
"""

from __future__ import annotations

import asyncio
import json

import pytest
from backend_support import (
    ORIGIN,
    TEST_PORT,
    add_stub_targets,
    assert_error,
    make_client,
    make_settings,
    walk_keys,
)
from starlette.routing import Route
from starlette.websockets import WebSocketDisconnect

from app.errors import MESSAGES, STATUS_OF, ErrorCode, map_http_status
from app.main import create_app
from app.security import HostGuardMiddleware

EXPECTED_CODES = {
    "VALIDATION_ERROR": 422,
    "NOT_FOUND": 404,
    "METHOD_NOT_ALLOWED": 405,
    "BAD_HOST": 400,
    "FORBIDDEN_ORIGIN": 403,
    "NO_ACTIVE_LOOP": 409,
    "TOO_MANY_STREAMS": 503,
    "CONTROL_WRITE_FAILED": 500,
    "INTERNAL_ERROR": 500,
}


@pytest.fixture
def app_and_client(engine_workspace, dist_dir):
    info = engine_workspace("full")
    app = create_app(make_settings(info.root, dist_dir=dist_dir))
    add_stub_targets(app)

    def boom() -> None:
        raise RuntimeError("SECRETMARKER /home/someone/path")

    app.add_api_route("/api/v1/_boom", boom, methods=["GET"], include_in_schema=False)
    return app, make_client(app)


def test_error_code_set_is_closed_nine() -> None:
    assert {c.value: STATUS_OF[c] for c in ErrorCode} == EXPECTED_CODES
    assert set(MESSAGES) == set(ErrorCode)


@pytest.mark.parametrize(
    ("status", "code"),
    [(404, "NOT_FOUND"), (405, "METHOD_NOT_ALLOWED"), (400, "VALIDATION_ERROR"),
     (401, "VALIDATION_ERROR"), (413, "VALIDATION_ERROR"), (418, "VALIDATION_ERROR"),
     (500, "INTERNAL_ERROR"), (502, "INTERNAL_ERROR")],
)  # fmt: skip
def test_framework_status_mapping(status: int, code: str) -> None:
    assert map_http_status(status).value == code


@pytest.mark.parametrize(
    ("method", "path"),
    [("GET", "/api/v1/nope"), ("GET", "/api/v2/x"), ("GET", "/api"), ("GET", "/api/"),
     ("HEAD", "/api/v1/nope"), ("OPTIONS", "/api/v1/nope"), ("GET", "/api/v1/pipeline/"),
     ("GET", "/nope"), ("GET", "/assets/nope.js"), ("GET", "/some/spa/route"),
     ("GET", "/index.html/"), ("DELETE", "/api/v1/nope")],
)  # fmt: skip
def test_unknown_paths_404_json(app_and_client, method: str, path: str) -> None:
    _, client = app_and_client
    headers = {"content-type": "application/json", "origin": ORIGIN}
    resp = client.request(method, path, headers=headers)
    assert resp.status_code == 404, (method, path, resp.status_code)
    if method != "HEAD":
        assert_error(resp, 404, "NOT_FOUND")
    assert "location" not in resp.headers  # 끝 슬래시 리다이렉트 없음


@pytest.mark.parametrize(
    ("method", "path", "allow"),
    [
        ("HEAD", "/api/v1/pipeline", "GET"),
        ("OPTIONS", "/api/v1/pipeline", "GET"),
        ("POST", "/api/v1/pipeline", "GET"),
        ("POST", "/api/v1/health", "GET"),
        ("GET", "/api/v1/control/pause", "POST"),
        ("OPTIONS", "/api/v1/control/pause", "POST"),
        ("HEAD", "/api/v1/events", "GET"),
        ("PUT", "/", "GET, HEAD"),
        ("OPTIONS", "/", "GET, HEAD"),
        ("DELETE", "/assets/app-abc123.js", "GET, HEAD"),
    ],
)
def test_method_not_allowed_405_with_allow(app_and_client, method, path, allow) -> None:
    _, client = app_and_client
    headers = {"content-type": "application/json", "origin": ORIGIN}
    resp = client.request(
        method, path, headers=headers, content=b"{}" if method != "GET" else None
    )
    assert resp.status_code == 405, resp.text
    assert resp.headers["allow"] == allow
    assert not [h for h in resp.headers if h.lower().startswith("access-control-")]
    if method != "HEAD":
        assert_error(resp, 405, "METHOD_NOT_ALLOWED")


def test_i21_starlette_route_still_auto_adds_head() -> None:
    """순수 Starlette `Route` 는 GET 에 HEAD 를 붙인다 — T-011 SSE 는 이 방식으로 등록하면 안 된다."""

    async def endpoint(request):  # pragma: no cover - 호출되지 않음
        return None

    assert Route("/x", endpoint, methods=["GET"]).methods == {"GET", "HEAD"}


@pytest.mark.parametrize(
    "query",
    ["status=foo", "team=BAD", "team=a", "phase=X1", "phase=P", "status="],
)
def test_validation_error_422_without_detail(app_and_client, query: str) -> None:
    _, client = app_and_client
    resp = client.get(f"/api/v1/tasks?{query}&x=SECRETMARKER")
    body = assert_error(resp, 422, "VALIDATION_ERROR")
    assert "SECRETMARKER" not in resp.text
    assert "detail" not in set(walk_keys(body)) and "input" not in set(walk_keys(body))


def test_unhandled_exception_500_internal_error(app_and_client, caplog) -> None:
    _, client = app_and_client
    resp = client.get("/api/v1/_boom")
    assert_error(resp, 500, "INTERNAL_ERROR")
    assert "SECRETMARKER" not in resp.text and "/home/" not in resp.text
    assert "SECRETMARKER" not in caplog.text


def test_no_detail_body_anywhere(app_and_client) -> None:
    _, client = app_and_client
    reqs = [
        ("GET", "/api/v1/nope"), ("POST", "/api/v1/pipeline"), ("OPTIONS", "/api/v1/memory"),
        ("GET", "/api/v1/tasks?status=zzz"), ("GET", "/nope"), ("PUT", "/"),
        ("GET", "/api/v1/_boom"), ("GET", "/api/v1/pipeline"), ("GET", "/api/v1/plan"),
        ("GET", "/api/v1/tasks"), ("GET", "/api/v1/memory"),
    ]  # fmt: skip
    for method, path in reqs:
        resp = client.request(
            method, path, headers={"content-type": "application/json"}, content=b"{}"
        )
        assert resp.headers["content-type"].startswith("application/json"), path
        assert "detail" not in set(walk_keys(resp.json())), (method, path)
        assert resp.text not in ("Not Found", "Method Not Allowed")


@pytest.mark.parametrize(
    ("method", "path", "headers"),
    [
        ("GET", "/api/v1/pipeline", {}),
        ("GET", "/", {}),
        ("GET", "/assets/app-abc123.js", {}),
        ("GET", "/api/v1/nope", {}),
        ("OPTIONS", "/api/v1/pipeline", {}),
        ("POST", "/api/v1/control/pause", {"content-type": "text/plain"}),
        ("GET", "/api/v1/pipeline", {"host": "evil.example"}),
        ("GET", "/api/v1/_boom", {}),
    ],
)
def test_security_headers_on_every_response(
    app_and_client, method, path, headers
) -> None:
    _, client = app_and_client
    resp = client.request(method, path, headers=headers)
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers["referrer-policy"] == "no-referrer"
    assert resp.headers["content-security-policy"] == (
        "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
        "connect-src 'self'"
    )
    assert not [h for h in resp.headers if h.lower().startswith("access-control-")]


# ---------------------------------------------------------------- §10 scope 처리
def test_websocket_closed_1008_without_inner_app(app_and_client) -> None:
    _, client = app_and_client
    with (
        pytest.raises(WebSocketDisconnect) as caught,
        client.websocket_connect("/api/v1/events"),
    ):
        pass  # pragma: no cover
    assert caught.value.code == 1008


def test_websocket_rejected_regardless_of_host_and_inner_not_called() -> None:
    called: list[str] = []

    async def inner(scope, receive, send):  # pragma: no cover - 호출되면 실패
        called.append(scope["type"])

    guard = HostGuardMiddleware(inner, port=TEST_PORT)
    sent: list[dict] = []

    async def receive():
        return {"type": "websocket.connect"}

    async def send(message):
        sent.append(message)

    scope = {"type": "websocket", "path": "/", "headers": [(b"host", b"evil.example")]}
    asyncio.run(guard(scope, receive, send))
    assert sent == [{"type": "websocket.close", "code": 1008}]
    assert called == []


def test_lifespan_passes_through_and_unknown_scope_ignored() -> None:
    seen: list[str] = []

    async def inner(scope, receive, send):
        seen.append(scope["type"])

    guard = HostGuardMiddleware(inner, port=TEST_PORT)

    async def noop_receive():
        return {}

    async def noop_send(message):
        return None

    asyncio.run(guard({"type": "lifespan"}, noop_receive, noop_send))
    asyncio.run(guard({"type": "weird"}, noop_receive, noop_send))
    assert seen == ["lifespan"]


def test_real_app_lifespan_startup_shutdown(app_and_client) -> None:
    app, _ = app_and_client
    with make_client(
        app
    ) as client:  # lifespan startup/shutdown 이 가드를 통과해야 한다
        assert client.get("/api/v1/memory").status_code == 200


def test_openapi_and_docs_routes_disabled(app_and_client) -> None:
    _, client = app_and_client
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert_error(client.get(path), 404, "NOT_FOUND")


def test_error_body_is_plain_json(app_and_client) -> None:
    _, client = app_and_client
    resp = client.get("/api/v1/nope")
    assert json.loads(resp.content) == {
        "error": {"code": "NOT_FOUND", "message": MESSAGES[ErrorCode.NOT_FOUND]}
    }
