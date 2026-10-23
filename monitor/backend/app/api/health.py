"""GET /api/v1/health (CON-05, 20 §5, ops 소유).

- 생존 + 소스별 접근 가능 여부 + 사용량 데우기 진행률 + 앱 식별자(`app`, 런처 중복 실행 판정).
- 소스 검사는 `stat`/`access` 만 쓴다. 파일 내용을 열지 않고, 디렉터리를 나열하지 않으며, 아무것도 쓰지
  않는다(원칙 2, D-07). `~/.claude` 에서는 `projects` 디렉터리 하나만 본다(02 §8).
- 소스가 없거나 깨져도 HTTP 200 + `meta.status=partial` (NFR-002). 응답·로그에 경로·값을 넣지 않는다.
- 런처가 20 s 동안 반복 호출하므로 가볍게 유지한다(검사 5회 stat, 캐시 없음).

데우기 진행률은 backend 가 `app.state.warmup` 에 `progress()` 를 가진 객체를 두면 그것을 읽는다
(T-010, 40 §1.1 `warmup.progress()`). `progress()` 는 `UsageWarming` 또는
`{"state": ..., "progress": ...}` 를 돌려준다. 없으면 `not_started`, 실패하면 `unknown`.
"""

from __future__ import annotations

import logging
import os
import stat
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request

from app import APP_NAME, __version__
from app.api.deps import ERROR_RESPONSES, Services, services
from app.models.envelope import Envelope
from app.models.health import HealthData, HealthSources, SourceState, UsageWarming
from app.services.panel import Panel

router = APIRouter(tags=["health"])
log = logging.getLogger("aidlc_monitor.health")

STALE_AFTER_SEC = 600  # ADR-003 §4: 10분 넘은 스냅샷은 SNAPSHOT_STALE

# 경고 문구는 고정 문자열 — 경로·파일 이름 원문을 담지 않는다 (ADR-011 §8).
WARNINGS: dict[tuple[str, SourceState], str] = {
    ("workspace", "missing"): "workspace 메모리 폴더가 없습니다.",
    ("workspace", "unreadable"): "workspace 메모리 폴더를 읽을 수 없습니다.",
    ("claude_projects", "missing"): "Claude Code 기록 폴더가 없습니다.",
    ("claude_projects", "unreadable"): "Claude Code 기록 폴더를 읽을 수 없습니다.",
    (
        "statusline",
        "missing",
    ): "status line 스냅샷이 없습니다 (statusLine 미실행 또는 첫 응답 전).",
    ("statusline", "stale"): "status line 스냅샷이 10분 넘게 갱신되지 않았습니다.",
    ("statusline", "unreadable"): "status line 스냅샷을 읽을 수 없습니다.",
    ("control", "unreadable"): "루프 제어 파일을 읽을 수 없습니다.",
}


def _state(path: Path, *, want_dir: bool, now: datetime | None = None) -> SourceState:
    """메타데이터만으로 접근 상태를 판정한다. 예외는 밖으로 내보내지 않는다."""
    try:
        st = os.stat(path)
    except (FileNotFoundError, NotADirectoryError):
        return "missing"
    except (OSError, ValueError):
        return "unreadable"
    kind_ok = stat.S_ISDIR(st.st_mode) if want_dir else stat.S_ISREG(st.st_mode)
    mode = os.R_OK | os.X_OK if want_dir else os.R_OK
    try:
        if not kind_ok or not os.access(path, mode):
            return "unreadable"
    except (OSError, ValueError):
        return "unreadable"
    if now is not None and now.timestamp() - st.st_mtime > STALE_AFTER_SEC:
        return "stale"
    return "ok"


def _warming(request: Request) -> UsageWarming:
    provider = getattr(request.app.state, "warmup", None)
    progress = getattr(provider, "progress", None)
    if not callable(progress):
        return UsageWarming(state="not_started")
    try:
        value = progress()
        if isinstance(value, UsageWarming):
            return value
        return UsageWarming.model_validate(value)
    except Exception as exc:  # noqa: BLE001 — health 는 데우기 오류로 실패하지 않는다
        log.warning("데우기 진행률을 읽지 못했습니다: %s", type(exc).__name__)
        return UsageWarming(state="unknown")


def build_health(request: Request, svc: Services) -> dict[str, Any]:
    settings = request.app.settings
    now = svc.clock()
    memory = settings.aidlc_root / "workspace" / "memory"
    sources = HealthSources(
        workspace=_state(memory, want_dir=True),
        claude_projects=_state(settings.claude_home / "projects", want_dir=True),
        statusline=_state(
            memory / ".monitor" / "claude-status.json", want_dir=False, now=now
        ),
        control=_state(memory / ".control.json", want_dir=False),
    )
    dist = (
        "ok"
        if _state(settings.dist_dir / "index.html", want_dir=False) == "ok"
        else "missing"
    )
    warming = _warming(request)

    panel = Panel()
    for name, state in sources.model_dump().items():
        message = WARNINGS.get((name, state))
        if message is not None:
            panel.warn(message)
    if dist == "missing":
        panel.warn("프론트 dist 가 없습니다 (npm ci && npm run build).")
    if warming.state == "warming" and not panel.warnings:
        panel.status = "warming"
    data = HealthData(
        status="ok",
        app=APP_NAME,  # type: ignore[arg-type]
        version=__version__,
        sources=sources,
        dist=dist,  # type: ignore[arg-type]
        usage_warming=warming,
    )
    return {
        "data": data.model_dump(mode="json"),
        "meta": panel.meta(now).model_dump(mode="json"),
    }


@router.get(
    "/health",
    response_model=Envelope[HealthData],
    responses=ERROR_RESPONSES,
    summary="생존·소스 접근 가능 여부·데우기 진행률·앱 식별자",
)
def get_health(request: Request, svc: Annotated[Services, Depends(services)]) -> Any:
    """소스 문제는 HTTP 200 + `meta.status=partial`. 런처는 `data.app == "aidlc-monitor"` 로 판정한다."""
    return build_health(request, svc)
