"""에러 코드 닫힌 집합과 요청 오류 본문 모델 (ADR-011 §9, D-26)."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class ErrorCode(str, Enum):
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    METHOD_NOT_ALLOWED = "METHOD_NOT_ALLOWED"
    BAD_HOST = "BAD_HOST"
    FORBIDDEN_ORIGIN = "FORBIDDEN_ORIGIN"
    NO_ACTIVE_LOOP = "NO_ACTIVE_LOOP"
    TOO_MANY_STREAMS = "TOO_MANY_STREAMS"
    CONTROL_WRITE_FAILED = "CONTROL_WRITE_FAILED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class ErrorDetail(BaseModel):
    code: ErrorCode
    message: str


class ErrorResponse(BaseModel):
    """요청 오류 본문 `{"error": {"code", "message"}}` (02 §6). 코드는 닫힌 집합 9개."""

    error: ErrorDetail
