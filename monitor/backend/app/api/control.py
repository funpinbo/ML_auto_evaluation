"""GET /api/v1/control, POST /api/v1/control/pause·resume (FR-005, ADR-004).

POST 는 대시보드의 유일한 쓰기다(`.control.json`). Host·Origin·Content-Type 가드는 라우터 바깥에서 먼저 돈다.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends

from app.api.deps import ERROR_RESPONSES, Services, run_panel, services
from app.errors import AppError
from app.models.control import ControlData, PauseRequest, ResumeRequest
from app.models.envelope import Envelope
from app.models.errors import ErrorCode, ErrorResponse
from app.services.control import ControlWriteFailed, NoActiveLoop

router = APIRouter(tags=["control"])

WRITE_RESPONSES: dict[int | str, dict[str, Any]] = {
    **ERROR_RESPONSES,
    403: {
        "model": ErrorResponse,
        "description": f"{ErrorCode.FORBIDDEN_ORIGIN.value} — Origin 불일치 또는 Content-Type 이 application/json 아님",
    },
    422: {
        "model": ErrorResponse,
        "description": f"{ErrorCode.VALIDATION_ERROR.value} — 본문 검증 (max_pause_sec 600~86400)",
    },
    500: {
        "model": ErrorResponse,
        "description": (
            f"{ErrorCode.CONTROL_WRITE_FAILED.value} — 쓰기 실패·락 타임아웃(2 s)·seq 상한, "
            f"기존 파일 보존 / {ErrorCode.INTERNAL_ERROR.value}"
        ),
    },
}
PAUSE_RESPONSES: dict[int | str, dict[str, Any]] = {
    **WRITE_RESPONSES,
    409: {
        "model": ErrorResponse,
        "description": f"{ErrorCode.NO_ACTIVE_LOOP.value} — loop-status 가 running/paused 가 아님",
    },
}


def _write(svc: Services, action: Any) -> dict[str, Any]:
    try:
        panel = action()
    except NoActiveLoop:
        raise AppError(ErrorCode.NO_ACTIVE_LOOP) from None
    except ControlWriteFailed:
        raise AppError(ErrorCode.CONTROL_WRITE_FAILED) from None
    return run_panel(svc, lambda: panel, "control")


@router.get(
    "/control",
    response_model=Envelope[ControlData],
    responses=ERROR_RESPONSES,
    summary="루프 제어 화면 상태 (.control.json + loop-status.json 조합)",
)
def get_control(svc: Annotated[Services, Depends(services)]) -> Any:
    """loop-status 없음 = `meta.status=empty`, 깨짐 = `error`, 제어 파일 깨짐 = `partial`."""
    return run_panel(svc, svc.control.read, "control")


@router.post(
    "/control/pause",
    response_model=Envelope[ControlData],
    responses=PAUSE_RESPONSES,
    summary="일시정지 요청 (.control.json state=pause, seq = max(prev, baseline)+1)",
)
def post_pause(
    svc: Annotated[Services, Depends(services)],
    body: Annotated[PauseRequest | None, Body()] = None,
) -> Any:
    limit = body.max_pause_sec if body is not None else None
    return _write(svc, lambda: svc.control.pause(limit))


@router.post(
    "/control/resume",
    response_model=Envelope[ControlData],
    responses=WRITE_RESPONSES,
    summary="재개 요청 (멱등, 루프가 없어도 200)",
)
def post_resume(
    svc: Annotated[Services, Depends(services)],
    body: Annotated[ResumeRequest | None, Body()] = None,
) -> Any:
    return _write(svc, svc.control.resume)
