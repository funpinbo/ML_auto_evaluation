"""GET /api/v1/plan, /api/v1/tasks 모델 (FR-002)."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    open = "open"
    done = "done"
    blocked = "blocked"
    active = "active"


class PhaseProgress(BaseModel):
    phase: str
    title: str
    total: int
    checked: int
    percent: int = Field(
        ge=0, le=100, description="floor(checked / total × 100), total 0 이면 0"
    )
    completed: bool | None = Field(
        description="plan completed_phases 에 있음 (plan 을 못 읽으면 null)"
    )
    current: bool | None = Field(
        description="plan current_phase 와 같음 (plan 을 못 읽으면 null)"
    )


class PlanData(BaseModel):
    current_phase: str | None
    completed_phases: list[str] | None
    phases: list[PhaseProgress]


class TaskItem(BaseModel):
    id: str | None = Field(description="T-ID. 형식 불일치 줄이면 null")
    team: str | None
    title: str
    refs: list[str] = Field(
        description="제목 뒤 `—` 다음의 요구사항·이슈 ID (FR-001 등)"
    )
    deps: list[str]
    phase: str
    checked: bool
    status: TaskStatus
    well_formed: bool


class TasksData(BaseModel):
    total: int = Field(description="필터 전 Phase 섹션의 Task 수")
    items: list[TaskItem]
