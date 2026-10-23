"""앱 팩토리 `create_app(settings)` (ADR-001, ADR-011).

- 가드(Host → Origin/미디어 타입 → 보안 헤더)는 FastAPI 전체(텔레메트리·ServerErrorMiddleware 포함)보다
  바깥에서 돈다: `MonitorApp.__call__` 이 가드 체인을 먼저 부른다 (D-18, D-29).
- 정적 dist 는 라우터 기본 처리기로만 서빙한다 → API 405 를 가로채지 않는다.
- `redirect_slashes=False`: `/api/v1/pipeline/` 같은 끝 슬래시는 307 이 아니라 404 (I-20 과 같은 경로 기준).
- ops 소유 모듈(`app/logging_config.py`, `app/api/health.py`)은 있으면 연결한다 (T-006 훅).
"""

from __future__ import annotations

import importlib
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, FastAPI
from starlette.types import Receive, Scope, Send

from app import APP_NAME, __version__
from app.api import memory as memory_api
from app.api import pipeline as pipeline_api
from app.api import tasks as tasks_api
from app.api.deps import Services
from app.config import Settings
from app.errors import install_error_handlers
from app.security import wrap_guards
from app.services.aidlc_reader import HookLoader
from app.services.gates import GateService, Runner, subprocess_runner
from app.services.memory import MemoryService
from app.services.pipeline import PipelineService
from app.services.tasks import TasksService
from app.static_files import StaticFallback

API_PREFIX = "/api/v1"
log = logging.getLogger("aidlc_monitor")


def _utcnow() -> datetime:
    return datetime.now(UTC)


class MonitorApp(FastAPI):
    """FastAPI + 가장 바깥 가드 체인."""

    settings: Settings

    def __init__(self, settings: Settings, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.settings = settings

        async def inner(scope: Scope, receive: Receive, send: Send) -> None:
            await FastAPI.__call__(self, scope, receive, send)

        self._guarded = wrap_guards(inner, port=settings.port)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        await self._guarded(scope, receive, send)


def _optional_module(name: str) -> Any | None:
    """ops 소유 모듈(T-006)이 아직 없으면 None."""
    try:
        return importlib.import_module(name)
    except ModuleNotFoundError as exc:
        if exc.name == name:
            return None
        raise


def create_app(
    settings: Settings,
    *,
    gate_runner: Runner = subprocess_runner,
    clock: Callable[[], datetime] = _utcnow,
) -> MonitorApp:
    """설정 하나로 앱을 만든다. 테스트는 `gate_runner`·`clock` 을 주입할 수 있다."""
    app = MonitorApp(
        settings,
        title="AI-DLC Monitor API",
        version=__version__,
        description=(
            "로컬 전용(127.0.0.1) AI-DLC 대시보드 API. 조회 응답은 `{data, meta}` 봉투, "
            '요청 오류는 `{"error":{code,message}}` (닫힌 코드 9개). 소스 문제는 HTTP 200 + `meta.status`.'
        ),
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        redirect_slashes=False,
        generate_unique_id_function=lambda route: route.name,
    )
    install_error_handlers(app)

    loader = HookLoader()
    gates = GateService(runner=gate_runner)
    root = settings.aidlc_root
    app.state.services = Services(
        pipeline=PipelineService(root, loader, gates),
        tasks=TasksService(root, loader),
        memory=MemoryService(root, loader, clock),
        gates=gates,
        clock=clock,
    )

    api = APIRouter(prefix=API_PREFIX)
    api.include_router(pipeline_api.router)
    api.include_router(tasks_api.router)
    api.include_router(memory_api.router)
    health = _optional_module("app.api.health")
    if health is not None and hasattr(health, "router"):
        api.include_router(health.router)
    app.include_router(api)

    app.router.default = StaticFallback(settings.dist_dir)
    app.state.app_name = APP_NAME
    return app


def setup_logging() -> None:
    """ops 의 `app.logging_config.setup_logging()` 이 있으면 쓰고, 없으면 기본 콘솔 로그."""
    module = _optional_module("app.logging_config")
    if module is not None and hasattr(module, "setup_logging"):
        module.setup_logging()
        return
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )


def __getattr__(name: str) -> Any:
    """`uvicorn app.main:app` 용 지연 생성 — import 만으로는 설정을 읽지 않는다."""
    if name == "app":
        setup_logging()
        instance = create_app(Settings.from_env())
        globals()["app"] = instance
        return instance
    raise AttributeError(name)
