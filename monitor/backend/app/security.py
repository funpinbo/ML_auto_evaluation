"""로컬 보안 가드 — 순수 ASGI 미들웨어 (ADR-011 §4·§5·§6·§10·§11·§12, D-18·D-25·D-27·D-28·D-29).

쌓는 순서 (바깥 → 안):
  HostGuardMiddleware   scope 분기 + Host 400 `BAD_HOST`            (가장 바깥, D-18)
  OriginGuardMiddleware 쓰기 가드·SSE 출처 검사 403 `FORBIDDEN_ORIGIN`
  SecurityHeadersMiddleware 모든 응답에 보안 헤더 3종
  ErrorShieldMiddleware 프레임워크 밖으로 새는 예외를 500 JSON 으로 막고 로그는 예외 종류만
  FastAPI (ServerErrorMiddleware → ExceptionMiddleware → 라우터 404/405 → 검증 422 → 핸들러)

헤더 개수·값 판정은 서버 파서에 맡기지 않고 `scope["headers"]` 에서 직접 한다.
거부 응답에 요청 헤더 값을 넣지 않는다. Starlette 내장 호스트 검사 미들웨어는 포트를 무시하므로 쓰지 않는다.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.errors import SECURITY_HEADERS, STATUS_OF, ErrorCode, error_bytes

log = logging.getLogger("aidlc_monitor.security")

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
EVENTS_PATH = "/api/v1/events"
ALLOWED_FETCH_SITES = frozenset({"same-origin", "none"})


def header_values(scope: Scope, name: bytes) -> list[bytes]:
    """이름이 `name`(소문자 바이트)인 헤더 값 전부. 개수 판정에 쓴다."""
    return [v for k, v in scope.get("headers") or () if k.lower() == name]


def _normalized(value: bytes) -> str:
    return value.decode("latin-1").strip().lower()


def route_path(scope: Scope) -> str:
    """라우터와 같은 기준(디코드된 `scope["path"]` − root_path)으로 경로를 구한다 (I-20)."""
    path: str = scope.get("path", "")
    root_path: str = scope.get("root_path", "")
    if root_path and path.startswith(root_path):
        return path[len(root_path) :] or "/"
    return path


async def send_error(
    send: Send, code: ErrorCode, extra_headers: Iterable[tuple[str, str]] = ()
) -> None:
    body = error_bytes(code)
    headers = [
        (b"content-type", b"application/json"),
        (b"content-length", str(len(body)).encode()),
        *((k.encode(), v.encode()) for k, v in SECURITY_HEADERS),
        *((k.encode(), v.encode()) for k, v in extra_headers),
    ]
    await send(
        {"type": "http.response.start", "status": STATUS_OF[code], "headers": headers}
    )
    await send({"type": "http.response.body", "body": body})


class HostGuardMiddleware:
    """Host 헤더가 정확히 1개이고 `127.0.0.1:<port>`/`localhost:<port>` 와 정확히 같을 때만 통과."""

    def __init__(self, app: ASGIApp, *, port: int) -> None:
        self.app = app
        self.allowed = frozenset({f"127.0.0.1:{port}", f"localhost:{port}"})

    def host_ok(self, scope: Scope) -> bool:
        hosts = header_values(scope, b"host")
        return len(hosts) == 1 and _normalized(hosts[0]) in self.allowed

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        kind = scope["type"]
        if kind == "lifespan":
            await self.app(scope, receive, send)
            return
        if kind == "websocket":
            # 앱에 WebSocket 엔드포인트가 없다. accept 없이 1008 로 닫는다 (ADR-011 §10).
            await receive()
            await send({"type": "websocket.close", "code": 1008})
            return
        if kind != "http":
            return
        if not self.host_ok(scope):
            await send_error(send, ErrorCode.BAD_HOST)
            return
        await self.app(scope, receive, send)


class OriginGuardMiddleware:
    """쓰기 가드(ADR-011 §5)와 `/api/v1/events` 출처 검사(§11). 라우팅보다 먼저 돈다."""

    def __init__(self, app: ASGIApp, *, port: int) -> None:
        self.app = app
        self.allowed_origins = frozenset(
            {f"http://127.0.0.1:{port}", f"http://localhost:{port}"}
        )

    def _origin_ok(self, scope: Scope) -> bool:
        origins = header_values(scope, b"origin")
        if not origins:
            return True
        if len(origins) > 1:
            return False
        return origins[0].decode("latin-1").strip() in self.allowed_origins

    def write_ok(self, scope: Scope) -> bool:
        types = header_values(scope, b"content-type")
        if len(types) != 1:
            return False
        media = types[0].decode("latin-1").split(";", 1)[0].strip().lower()
        if media != "application/json":
            return False
        return self._origin_ok(scope)

    def events_ok(self, scope: Scope) -> bool:
        if not self._origin_ok(scope):
            return False
        sites = header_values(scope, b"sec-fetch-site")
        if len(sites) > 1:
            return False
        return not sites or _normalized(sites[0]) in ALLOWED_FETCH_SITES

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        method = str(scope.get("method", "")).upper()
        if method not in SAFE_METHODS and not self.write_ok(scope):
            await send_error(send, ErrorCode.FORBIDDEN_ORIGIN)
            return
        if route_path(scope) == EVENTS_PATH and not self.events_ok(scope):
            await send_error(send, ErrorCode.FORBIDDEN_ORIGIN)
            return
        await self.app(scope, receive, send)


class SecurityHeadersMiddleware:
    """모든 HTTP 응답(정적 dist·오류 포함)에 보안 헤더 3종을 붙인다 (ADR-011 §6)."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = [
                    (k, v)
                    for k, v in message.get("headers", [])
                    if k.lower() not in _SECURITY_NAMES
                ]
                headers.extend(_SECURITY_RAW)
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_headers)


class ErrorShieldMiddleware:
    """FastAPI ServerErrorMiddleware 가 응답 후 다시 던지는 예외를 여기서 끝낸다.

    응답 전이면 500 `INTERNAL_ERROR` JSON 을 보내고, 로그에는 예외 종류만 남긴다
    (서버 기본 traceback 로그에 경로·내용이 섞이지 않게, ADR-011 §8).
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = False

        async def tracking_send(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, receive, tracking_send)
        except Exception as exc:  # noqa: BLE001 — 마지막 방어선
            log.error("요청 처리 중 예외: %s", type(exc).__name__)
            if not started:
                await send_error(send, ErrorCode.INTERNAL_ERROR)


_SECURITY_NAMES = frozenset(k.encode() for k, _ in SECURITY_HEADERS)
_SECURITY_RAW = [(k.encode(), v.encode()) for k, v in SECURITY_HEADERS]


def wrap_guards(app: ASGIApp, *, port: int) -> ASGIApp:
    """가드를 정해진 순서로 감싼다. HostGuard 가 가장 바깥이다 (D-18, D-29)."""
    inner = ErrorShieldMiddleware(app)
    inner = SecurityHeadersMiddleware(inner)
    inner = OriginGuardMiddleware(inner, port=port)
    return HostGuardMiddleware(inner, port=port)
