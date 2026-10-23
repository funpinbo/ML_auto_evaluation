"""GET /api/v1/memory 모델 (FR-003)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.models.envelope import SourceErrorCode

StmStatus = Literal["idle", "active", "closed", "unknown"]
CascadeLevel = Literal["none", "ltm", "tasks", "plan", "unknown"]


class StmView(BaseModel):
    status: StmStatus | None = Field(description="STM 을 읽지 못하면 null")
    task: str | None
    team: str | None
    outcome: str | None
    opened_at: str | None
    elapsed_sec: int | None = Field(
        description="현재 − opened_at (초). 없음·형식 오류·미래면 null"
    )
    error_code: SourceErrorCode | None = None


class MemoryData(BaseModel):
    stm: StmView
    ltm_rev: int | None
    last_merged_stm: int | None
    tasks_rev: int | None
    synced_ltm_rev: int | None
    current_phase: str | None
    completed_phases: list[str] | None
    archive_count: int | None
    latest_archive_seq: int | None
    pending_cascade: CascadeLevel = Field(
        description="Hook Memory.pending().level (없음 = none, 판정 불가 = unknown)"
    )
    stop_blocks: int | None = Field(
        description="Stop Hook 연속 차단 횟수 (.cascade-state.json)"
    )
