"""GET /api/v1/pipeline 모델 (FR-001, D-21)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.models.envelope import SourceErrorCode

StageState = Literal["done", "in_progress", "waiting", "unknown"]
GateResult = Literal["PASS", "FAIL", "UNKNOWN"]
GateLayer = Literal["user", "project", "docs"]


class Stage(BaseModel):
    index: int = Field(ge=0, le=6)
    name: str
    command: str
    state: StageState


class Gate(BaseModel):
    layer: GateLayer
    result: GateResult
    unwritten: int | None = Field(
        description="미작성 플레이스홀더 수 (대상 없음·확인 불가면 null)"
    )
    missing: int | None = Field(description="누락 문서 수 (대상 없음·확인 불가면 null)")
    target_missing: bool = Field(description="대상 디렉터리 없음 (FAIL + '대상 없음')")
    no_documents: bool = Field(description="검사 대상 문서 0개로 PASS (R5)")
    error_code: SourceErrorCode | None = None
    checked_at: str | None


class PipelineData(BaseModel):
    current_stage: int = Field(ge=0, le=6)
    current_stage_name: str
    next_command: str | None = Field(description="다음에 실행할 명령. 전체 완료면 null")
    all_done: bool
    stages: list[Stage]
    gates: list[Gate]
