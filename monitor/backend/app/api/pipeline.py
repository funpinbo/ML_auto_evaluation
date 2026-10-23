"""GET /api/v1/pipeline (FR-001)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.api.deps import ERROR_RESPONSES, Services, run_panel, services
from app.models.envelope import Envelope
from app.models.pipeline import PipelineData

router = APIRouter(tags=["pipeline"])


@router.get(
    "/pipeline",
    response_model=Envelope[PipelineData],
    responses=ERROR_RESPONSES,
    summary="AI-DLC 단계 0~6 상태와 Gate 3종",
)
def get_pipeline(svc: Annotated[Services, Depends(services)]) -> Any:
    """단계 판정은 FR-001 §2(D-21). Gate 는 `aidlc.py check` 서브프로세스(TTL 5 s)."""
    return run_panel(svc, svc.pipeline.read, "pipeline")
