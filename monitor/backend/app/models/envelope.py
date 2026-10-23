"""조회 응답 봉투 `{data, meta}` 와 에러 본문 (ADR-011 §1·§2, D-08)."""

from __future__ import annotations

from enum import Enum
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")

PanelStatus = Literal["ok", "partial", "empty", "error", "warming"]


class SourceErrorCode(str, Enum):
    """패널 `meta.error.code` (20 §5). HTTP 에러 코드 집합과 별개다."""

    SOURCE_MISSING = "SOURCE_MISSING"
    SOURCE_PARSE_ERROR = "SOURCE_PARSE_ERROR"
    SOURCE_UNREADABLE = "SOURCE_UNREADABLE"
    GATE_TIMEOUT = "GATE_TIMEOUT"
    PROJECT_DIR_NOT_FOUND = "PROJECT_DIR_NOT_FOUND"
    SNAPSHOT_STALE = "SNAPSHOT_STALE"


class SourceError(BaseModel):
    code: SourceErrorCode
    message: str


class Meta(BaseModel):
    status: PanelStatus
    warnings: list[str] = Field(default_factory=list)
    error: SourceError | None = None
    generated_at: str = Field(description="응답 생성 시각 (RFC 3339, UTC)")
    source_mtime: str | None = Field(
        default=None,
        description="읽은 소스 파일 중 가장 최근 수정 시각 (RFC 3339, UTC)",
    )


class Envelope(BaseModel, Generic[T]):
    data: T | None
    meta: Meta
