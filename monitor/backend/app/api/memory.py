"""GET /api/v1/memory (FR-003)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.api.deps import ERROR_RESPONSES, Services, run_panel, services
from app.models.envelope import Envelope
from app.models.memory import MemoryData

router = APIRouter(tags=["memory"])


@router.get(
    "/memory",
    response_model=Envelope[MemoryData],
    responses=ERROR_RESPONSES,
    summary="STM·LTM·Task 동기 값과 미처리 cascade",
)
def get_memory(svc: Annotated[Services, Depends(services)]) -> Any:
    """cascade 판정은 Hook `Memory.pending().level` (ADR-009). `aidlc.py status` 는 실행하지 않는다."""
    return run_panel(svc, svc.memory.read, "memory")
