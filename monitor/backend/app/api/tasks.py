"""GET /api/v1/plan, /api/v1/tasks (FR-002)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from app.api.deps import (
    ERROR_RESPONSES,
    QUERY_ERROR_RESPONSES,
    Services,
    run_panel,
    services,
)
from app.models.envelope import Envelope
from app.models.tasks import PlanData, TasksData, TaskStatus

router = APIRouter(tags=["plan"])

TEAM_PATTERN = r"^[a-z][a-z0-9-]{1,30}$"
PHASE_PATTERN = r"^P\d{1,4}$"


@router.get(
    "/plan",
    response_model=Envelope[PlanData],
    responses=ERROR_RESPONSES,
    summary="Phase 별 진행률과 현재·완료 Phase",
)
def get_plan(svc: Annotated[Services, Depends(services)]) -> Any:
    return run_panel(svc, svc.tasks.plan, "plan")


@router.get(
    "/tasks",
    response_model=Envelope[TasksData],
    responses=QUERY_ERROR_RESPONSES,
    summary="Task 목록 (팀·상태·Phase 필터, AND)",
)
def get_tasks(
    svc: Annotated[Services, Depends(services)],
    team: Annotated[
        str | None, Query(pattern=TEAM_PATTERN, description="팀 id")
    ] = None,
    status: Annotated[
        TaskStatus | None, Query(description="open | done | blocked | active")
    ] = None,
    phase: Annotated[
        str | None, Query(pattern=PHASE_PATTERN, description="Phase (예: P1)")
    ] = None,
) -> Any:
    return run_panel(
        svc, lambda: svc.tasks.tasks(team=team, status=status, phase=phase), "tasks"
    )
