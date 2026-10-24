"""GET /api/v1/events — SSE 알림 (FR-008, contracts/sse-events.md).

데이터는 보내지 않고 바뀐 topic 만 알린다. 프론트는 해당 REST 를 다시 조회한다.
- 허브 하나가 1초마다 `Watcher.poll()` + `collector.refresh()` 를 돌려 모든 연결에 나눠 준다.
  구독자가 없으면 허브 작업은 멈춘다.
- 동시 연결 상한 8, 넘으면 503 `TOO_MANY_STREAMS`. 출처 검사(403)는 `OriginGuardMiddleware` 가 먼저 한다.
- `APIRoute` 로 GET 만 등록 → HEAD·POST 는 라우터가 405 (Starlette `Route` 는 HEAD 를 자동 추가한다).
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.api.deps import ERROR_RESPONSES
from app.errors import AppError, ErrorCode
from app.services.watcher import Watcher

router = APIRouter(tags=["events"])
log = logging.getLogger("aidlc_monitor.events")

MAX_STREAMS = 8
TICK_SEC = 1.0
KEEPALIVE_SEC = 15.0
RETRY_MS = 5000


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def frame(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, separators=(',', ':'))}\n\n"


def warm_frame(progress: dict[str, Any]) -> str:
    if progress.get("state") == "warming":
        return frame("warming", {"progress": progress.get("progress") or 0.0, "at": _now()})
    return frame("ready", {"at": _now()})


class EventHub:
    """구독자 큐 묶음 + 1초 폴링 작업."""

    def __init__(
        self,
        watcher: Watcher,
        *,
        refresh: Callable[[], Any] = lambda: None,
        progress: Callable[[], dict[str, Any]] = lambda: {"state": "done"},
        tick: float = TICK_SEC,
        limit: int = MAX_STREAMS,
    ) -> None:
        self.watcher = watcher
        self.refresh = refresh
        self.progress = progress
        self.tick = tick
        self.limit = limit
        self.subscribers: set[asyncio.Queue[str]] = set()
        self._task: asyncio.Task[None] | None = None

    @property
    def active(self) -> int:
        return len(self.subscribers)

    def subscribe(self) -> asyncio.Queue[str]:
        if len(self.subscribers) >= self.limit:
            raise AppError(ErrorCode.TOO_MANY_STREAMS)
        queue: asyncio.Queue[str] = asyncio.Queue(maxsize=64)
        self.subscribers.add(queue)
        if self._task is None or self._task.done():
            self._task = asyncio.get_running_loop().create_task(self._run())
        return queue

    def unsubscribe(self, queue: asyncio.Queue[str]) -> None:
        self.subscribers.discard(queue)
        if not self.subscribers and self._task is not None:
            self._task.cancel()
            self._task = None

    def broadcast(self, text: str) -> None:
        for queue in list(self.subscribers):
            try:
                queue.put_nowait(text)
            except asyncio.QueueFull:  # 느린 소비자: 오래된 알림을 버리고 최신을 넣는다
                queue.get_nowait()
                queue.put_nowait(text)

    async def step(self, last_warm: tuple[Any, Any]) -> tuple[Any, Any]:
        """tick 1회. 데우기 상태와 변경 topic 을 방송한다."""
        topics: list[str] = []
        try:
            await asyncio.to_thread(self.refresh)
            topics = await asyncio.to_thread(self.watcher.poll)
            p = self.progress()
        except Exception as exc:  # noqa: BLE001 — 허브는 죽지 않는다
            log.error("이벤트 허브 오류: %s", type(exc).__name__)
            return last_warm
        warm = (p.get("state"), round(p.get("progress") or 0.0, 2))
        if warm != last_warm:
            self.broadcast(warm_frame(p))
            if p.get("state") != "warming" and last_warm[0] == "warming":
                topics = sorted(set(topics) | {"usage"})
        if topics:
            self.broadcast(frame("changed", {"topics": topics, "at": _now()}))
        return warm

    async def _run(self) -> None:
        p = self.progress()
        last = (p.get("state"), round(p.get("progress") or 0.0, 2))
        while True:
            await asyncio.sleep(self.tick)
            last = await self.step(last)


def hub(request: Request) -> EventHub:
    return request.app.state.events  # type: ignore[no-any-return]


async def stream(request: Request, hub_: EventHub, queue: asyncio.Queue[str]) -> AsyncIterator[str]:
    try:
        yield f"retry: {RETRY_MS}\n\n"
        yield warm_frame(hub_.progress())
        while True:
            try:
                yield await asyncio.wait_for(queue.get(), timeout=KEEPALIVE_SEC)
            except TimeoutError:
                if await request.is_disconnected():
                    break
                yield ": keep-alive\n\n"
    finally:
        hub_.unsubscribe(queue)


@router.get(
    "/events",
    responses={**ERROR_RESPONSES, 503: {"description": "TOO_MANY_STREAMS — 동시 연결 상한 8"}},
    response_class=StreamingResponse,
    summary="변경 알림 스트림 (text/event-stream)",
)
async def get_events(request: Request, hub_: Annotated[EventHub, Depends(hub)]) -> StreamingResponse:
    """`changed{topics}`·`warming`·`ready` 이벤트와 15초 keep-alive. 형식 기준은 contracts/sse-events.md."""
    queue = hub_.subscribe()
    return StreamingResponse(
        stream(request, hub_, queue),
        media_type="text/event-stream; charset=utf-8",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
