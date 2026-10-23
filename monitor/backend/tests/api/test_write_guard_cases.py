"""privacy.md §5.2 C-01~C-11 (N-04), N-03 Origin, ADR-011 §5 쓰기 가드 범위, §11 events 출처, §12 처리 순서.

`POST /api/v1/control/{pause,resume}` 는 T-008 전이라 대역 라우트(본문 Pydantic 검증 포함)를 붙여
"가드 통과 → 핸들러 도달" 과 "403 이 422 보다 먼저" 를 함께 확인한다.
"""

from __future__ import annotations

import pytest
from backend_support import (
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

WRITE_TARGETS = ("/api/v1/control/pause", "/api/v1/control/resume")

# case -> (Content-Type 값 또는 None(헤더 없음), 본문, 통과 여부)
C_CASES: dict[str, tuple[str | None, bytes, bool]] = {
    "C-01": ("application/json", b"{}", True),
    "C-02": ("application/json; charset=utf-8", b"{}", True),
    "C-03": ("Application/JSON", b"{}", True),
    "C-04": (None, b"{}", False),
    "C-05": ("application/x-www-form-urlencoded", b"{}", False),
    "C-06": ("multipart/form-data; boundary=x", b"{}", False),
    "C-07": ("text/plain", b"{}", False),
    "C-08": ("application/jsonx", b"{}", False),
    "C-09": ("application/json-patch+json", b"{}", False),
    "C-10": ("text/plain", b"this is {not json", False),
    "C-11": ("", b"{}", False),
}


@pytest.fixture
def guarded(engine_workspace):
    info = engine_workspace("full")
    app = create_app(make_settings(info.root))
    add_stub_targets(app)
    return app, info


@pytest.mark.parametrize("path", WRITE_TARGETS)
@pytest.mark.parametrize("case", sorted(C_CASES))
def test_content_type_cases(guarded, case: str, path: str) -> None:
    app, info = guarded
    ctype, body, should_pass = C_CASES[case]
    headers = [
        (b"host", f"127.0.0.1:{TEST_PORT}".encode()),
        (b"origin", ORIGIN.encode()),
    ]
    if ctype is not None:
        headers.append((b"content-type", ctype.encode()))
    control_before = info.control_file.exists()
    before = hash_tree(info.root)
    resp = asgi_http(app, http_scope("POST", path, headers), body)
    if should_pass:
        assert resp.status == 200, (case, resp.status, resp.body)
    else:
        assert resp.status == 403, (case, resp.status)
        assert resp.status not in (415, 422)
        assert resp.json() == {
            "error": {
                "code": "FORBIDDEN_ORIGIN",
                "message": resp.json()["error"]["message"],
            }
        }
        if ctype:
            assert ctype.lower() not in resp.json()["error"]["message"].lower()
    assert info.control_file.exists() == control_before
    assert hash_tree(info.root) == before


def test_multiple_content_type_headers_rejected(guarded) -> None:
    app, _ = guarded
    headers = [
        (b"host", f"127.0.0.1:{TEST_PORT}".encode()),
        (b"content-type", b"application/json"),
        (b"content-type", b"application/json"),
    ]
    resp = asgi_http(app, http_scope("POST", WRITE_TARGETS[0], headers), b"{}")
    assert resp.status == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN_ORIGIN"


@pytest.mark.parametrize(
    "origin",
    [
        "http://evil.example",
        "null",
        f"http://127.0.0.1:{OTHER_PORT}",
        f"https://127.0.0.1:{TEST_PORT}",
        f"http://localhost.evil.com:{TEST_PORT}",
    ],
)
@pytest.mark.parametrize("path", WRITE_TARGETS)
def test_n03_bad_origin_rejected(guarded, origin: str, path: str) -> None:
    app, _ = guarded
    resp = make_client(app).post(path, json={}, headers={"origin": origin})
    body = assert_error(resp, 403, "FORBIDDEN_ORIGIN")
    assert origin not in body["error"]["message"]


@pytest.mark.parametrize("origin", [None, ORIGIN, f"http://localhost:{TEST_PORT}"])
@pytest.mark.parametrize("path", WRITE_TARGETS)
def test_n03_allowed_or_missing_origin_passes(
    guarded, origin: str | None, path: str
) -> None:
    app, _ = guarded
    headers = {} if origin is None else {"origin": origin}
    resp = make_client(app).post(path, json={}, headers=headers)
    assert resp.status_code == 200


def test_multiple_origin_headers_rejected_for_writes(guarded) -> None:
    app, _ = guarded
    headers = [
        (b"host", f"127.0.0.1:{TEST_PORT}".encode()),
        (b"content-type", b"application/json"),
        (b"origin", ORIGIN.encode()),
        (b"origin", ORIGIN.encode()),
    ]
    resp = asgi_http(app, http_scope("POST", WRITE_TARGETS[0], headers), b"{}")
    assert resp.status == 403


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
@pytest.mark.parametrize(
    "path", ["/api/v1/nope", "/", "/api/v1/pipeline", "/assets/x.js"]
)
def test_write_guard_applies_to_every_path(guarded, method: str, path: str) -> None:
    """ADR-011 §5: GET/HEAD/OPTIONS 가 아니면 경로 무관하게 가드 (라우팅 404/405 보다 먼저)."""
    app, _ = guarded
    resp = make_client(app).request(
        method,
        path,
        content=b"x=1",
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert_error(resp, 403, "FORBIDDEN_ORIGIN")


def test_order_text_plain_broken_body_is_403_not_422(guarded) -> None:
    app, _ = guarded
    resp = make_client(app).post(
        WRITE_TARGETS[0], content=b"{broken", headers={"content-type": "text/plain"}
    )
    assert_error(resp, 403, "FORBIDDEN_ORIGIN")


def test_order_json_broken_body_is_422_without_input_echo(guarded) -> None:
    app, _ = guarded
    resp = make_client(app).post(
        WRITE_TARGETS[0],
        content=b'{"max_pause_sec": "SECRETMARKER',
        headers={"content-type": "application/json", "origin": ORIGIN},
    )
    body = assert_error(resp, 422, "VALIDATION_ERROR")
    assert "SECRETMARKER" not in resp.text
    assert "detail" not in body and "input" not in str(body)


def test_order_json_out_of_range_is_422(guarded) -> None:
    app, _ = guarded
    resp = make_client(app).post(WRITE_TARGETS[0], json={"max_pause_sec": 5})
    assert_error(resp, 422, "VALIDATION_ERROR")


def test_order_valid_write_on_unknown_path_is_404(guarded) -> None:
    app, _ = guarded
    assert_error(make_client(app).post("/api/v1/nope", json={}), 404, "NOT_FOUND")


def test_order_valid_write_on_static_root_is_405(guarded) -> None:
    app, _ = guarded
    resp = make_client(app).put("/", json={})
    assert_error(resp, 405, "METHOD_NOT_ALLOWED")
    assert resp.headers["allow"] == "GET, HEAD"


# ---------------------------------------------------------------- ADR-011 §11 events 출처 (경로 기준)
EVENTS = "/api/v1/events"


@pytest.mark.parametrize(
    ("headers", "label"),
    [
        ({"origin": "http://evil.example"}, "origin-evil"),
        ({"origin": "null"}, "origin-null"),
        ({"sec-fetch-site": "cross-site"}, "sfs-cross-site"),
        ({"sec-fetch-site": "same-site"}, "sfs-same-site"),
        ({"sec-fetch-site": ""}, "sfs-empty"),
        ({"sec-fetch-site": "same-origin, none"}, "sfs-list"),
        ({"origin": ORIGIN, "sec-fetch-site": "cross-site"}, "ok-origin-cross-site"),
    ],
)
@pytest.mark.parametrize("method", ["GET", "HEAD", "OPTIONS"])
def test_events_cross_origin_rejected_any_method(
    guarded, headers, label, method
) -> None:
    app, _ = guarded
    resp = make_client(app).request(method, EVENTS, headers=headers)
    assert resp.status_code == 403, label
    if method != "HEAD":
        assert resp.json()["error"]["code"] == "FORBIDDEN_ORIGIN"


@pytest.mark.parametrize("name", [b"origin", b"sec-fetch-site"])
def test_events_duplicate_headers_rejected(guarded, name: bytes) -> None:
    app, _ = guarded
    value = ORIGIN.encode() if name == b"origin" else b"same-origin"
    headers = [
        (b"host", f"127.0.0.1:{TEST_PORT}".encode()),
        (name, value),
        (name, value),
    ]
    resp = asgi_http(app, http_scope("GET", EVENTS, headers))
    assert resp.status == 403


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"origin": ORIGIN},
        {"sec-fetch-site": "same-origin"},
        {"sec-fetch-site": "Same-Origin"},
        {"sec-fetch-site": " none "},
        {"origin": f"http://localhost:{TEST_PORT}", "sec-fetch-site": "same-origin"},
    ],
)
def test_events_same_origin_passes_guard(guarded, headers) -> None:
    app, _ = guarded
    resp = make_client(app).get(EVENTS, headers=headers)
    assert resp.status_code == 200  # 대역 핸들러 도달 (실제 스트림은 T-011)


def test_events_origin_check_not_applied_to_other_gets(guarded) -> None:
    app, _ = guarded
    resp = make_client(app).get(
        "/api/v1/pipeline",
        headers={"origin": "http://evil.example", "sec-fetch-site": "cross-site"},
    )
    assert resp.status_code == 200
