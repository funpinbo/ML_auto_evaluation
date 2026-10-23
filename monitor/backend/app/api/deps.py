"""라우터 공통: 앱 상태의 서비스 꺼내기, 패널 결과 → 봉투, 패널 단위 예외 격리 (NFR-002)."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from fastapi import Request

from app.errors import ErrorCode
from app.models.envelope import SourceErrorCode
from app.models.errors import ErrorResponse
from app.services.control import ControlService
from app.services.gates import GateService
from app.services.memory import MemoryService
from app.services.panel import Panel
from app.services.pipeline import PipelineService
from app.services.tasks import TasksService

log = logging.getLogger("aidlc_monitor.api")

PANEL_FAILED = "패널 데이터를 만드는 중 오류가 발생했습니다"

ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: {
        "model": ErrorResponse,
        "description": f"{ErrorCode.BAD_HOST.value} — Host 가드",
    },
    405: {
        "model": ErrorResponse,
        "description": f"{ErrorCode.METHOD_NOT_ALLOWED.value} — `Allow` 헤더 포함 (OPTIONS·HEAD 포함)",
    },
    500: {"model": ErrorResponse, "description": ErrorCode.INTERNAL_ERROR.value},
}
QUERY_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    **ERROR_RESPONSES,
    422: {
        "model": ErrorResponse,
        "description": f"{ErrorCode.VALIDATION_ERROR.value} — 쿼리 검증",
    },
}


@dataclass
class Services:
    pipeline: PipelineService
    tasks: TasksService
    memory: MemoryService
    gates: GateService
    control: ControlService
    clock: Callable[[], datetime]


def services(request: Request) -> Services:
    return request.app.state.services  # type: ignore[no-any-return]


def run_panel(svc: Services, build: Callable[[], Panel], name: str) -> dict[str, Any]:
    """패널 하나를 만들고 봉투로 바꾼다. 예상 못 한 예외도 이 패널의 `meta.status=error` 로 가둔다."""
    try:
        panel = build()
    except Exception as exc:  # noqa: BLE001 — 패널 격리: 다른 패널·HTTP 상태에 영향 없음
        log.error("%s 패널 오류: %s", name, type(exc).__name__)
        panel = Panel()
        panel.fail(SourceErrorCode.SOURCE_UNREADABLE, PANEL_FAILED)
    data = panel.data.model_dump(mode="json") if panel.data is not None else None
    return {"data": data, "meta": panel.meta(svc.clock()).model_dump(mode="json")}
