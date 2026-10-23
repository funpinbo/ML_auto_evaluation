"""에러 코드 닫힌 집합과 에러 응답 (ADR-011 §2·§9, D-26).

어떤 경로에서도 프레임워크 기본 본문(`{"detail": ...}`, 평문 `Not Found`)을 내보내지 않는다.
메시지는 고정 문구이며 요청 값(Host·Origin·Content-Type·입력 원문·경로)을 담지 않는다.
"""

from __future__ import annotations

import json
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.models.errors import ErrorCode

log = logging.getLogger("aidlc_monitor.errors")


STATUS_OF: dict[ErrorCode, int] = {
    ErrorCode.VALIDATION_ERROR: 422,
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.METHOD_NOT_ALLOWED: 405,
    ErrorCode.BAD_HOST: 400,
    ErrorCode.FORBIDDEN_ORIGIN: 403,
    ErrorCode.NO_ACTIVE_LOOP: 409,
    ErrorCode.TOO_MANY_STREAMS: 503,
    ErrorCode.CONTROL_WRITE_FAILED: 500,
    ErrorCode.INTERNAL_ERROR: 500,
}

MESSAGES: dict[ErrorCode, str] = {
    ErrorCode.VALIDATION_ERROR: "요청 값이 올바르지 않습니다.",
    ErrorCode.NOT_FOUND: "요청한 리소스를 찾을 수 없습니다.",
    ErrorCode.METHOD_NOT_ALLOWED: "이 경로에서 허용하지 않는 메서드입니다.",
    ErrorCode.BAD_HOST: "허용되지 않은 Host 헤더입니다. 대시보드 주소로 다시 접속하세요.",
    ErrorCode.FORBIDDEN_ORIGIN: "허용되지 않은 출처 또는 Content-Type 입니다.",
    ErrorCode.NO_ACTIVE_LOOP: "활성 루프가 없습니다.",
    ErrorCode.TOO_MANY_STREAMS: "동시 스트림 연결 수가 상한을 넘었습니다.",
    ErrorCode.CONTROL_WRITE_FAILED: "제어 파일을 쓰지 못했습니다.",
    ErrorCode.INTERNAL_ERROR: "서버 내부 오류가 발생했습니다.",
}

SECURITY_HEADERS: tuple[tuple[str, str], ...] = (
    ("x-content-type-options", "nosniff"),
    ("referrer-policy", "no-referrer"),
    (
        "content-security-policy",
        "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'",
    ),
)


class AppError(Exception):
    """앱 코드가 던지는 유일한 요청 오류. 코드는 닫힌 집합만."""

    def __init__(
        self, code: ErrorCode, *, headers: dict[str, str] | None = None
    ) -> None:
        super().__init__(code.value)
        self.code = code
        self.status_code = STATUS_OF[code]
        self.headers = headers or {}


def error_body(code: ErrorCode) -> dict[str, dict[str, str]]:
    return {"error": {"code": code.value, "message": MESSAGES[code]}}


def error_bytes(code: ErrorCode) -> bytes:
    return json.dumps(error_body(code), ensure_ascii=False).encode("utf-8")


def error_response(
    code: ErrorCode, headers: dict[str, str] | None = None
) -> JSONResponse:
    return JSONResponse(error_body(code), status_code=STATUS_OF[code], headers=headers)


def map_http_status(status_code: int) -> ErrorCode:
    """ADR-011 §9 매핑 표: 404/405 는 그대로, 그 밖 4xx 는 422, 5xx 는 500."""
    if status_code == 404:
        return ErrorCode.NOT_FOUND
    if status_code == 405:
        return ErrorCode.METHOD_NOT_ALLOWED
    if 400 <= status_code < 500:
        return ErrorCode.VALIDATION_ERROR
    return ErrorCode.INTERNAL_ERROR


async def _http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    code = map_http_status(exc.status_code)
    headers: dict[str, str] = {}
    if code is ErrorCode.METHOD_NOT_ALLOWED and exc.headers:
        allow = exc.headers.get("Allow") or exc.headers.get("allow")
        if allow:
            headers["Allow"] = ", ".join(
                sorted(m.strip() for m in allow.split(",") if m.strip())
            )
    return error_response(code, headers)


async def _validation_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    # 입력 원문·`detail`·`input` 을 되돌려주지 않는다 (N-07).
    return error_response(ErrorCode.VALIDATION_ERROR)


async def _app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return error_response(exc.code, exc.headers)


async def _unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
    # 로그에는 예외 종류만 (ADR-011 §2·§8).
    log.error("처리되지 않은 예외: %s", type(exc).__name__)
    return error_response(ErrorCode.INTERNAL_ERROR)


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, _validation_handler)  # type: ignore[arg-type]
    app.add_exception_handler(AppError, _app_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, _unhandled_handler)
