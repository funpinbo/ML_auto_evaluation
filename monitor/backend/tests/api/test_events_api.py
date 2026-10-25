"""GET /api/v1/events — contracts/sse-events.md (T-011)."""

from __future__ import annotations

import asyncio
import dataclasses
import os
import time
from pathlib import Path

import pytest
from backend_support import assert_error, client_for

from app.api.events import EventHub, frame
from app.services.watcher import Watcher


@pytest.fixture
def root(engine_workspace) -> Path:
    return engine_workspace("full").root


def _touch(path: Path) -> None:
    path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    st = path.stat()
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000_000))


def test_watcher_detects_tasks_change(root: Path) -> None:
    w = Watcher(root)
    assert w.poll() == []
    assert w.poll() == []
    _touch(root / "workspace" / "memory" / "tasks.md")
    changed = w.poll()
    assert "tasks" in changed and "plan" in changed
    assert "memory" not in changed


def test_watcher_extra_signature(root: Path) -> None:
    box = {"v": 1}
    w = Watcher(root, control_view=lambda: box["v"])
    w.poll()
    box["v"] = 2
    assert w.poll() == ["control"]


def test_hub_broadcasts_changed_and_ready(root: Path) -> None:
    state = {"state": "warming", "progress": 0.5}
    w = Watcher(root)
    hub = EventHub(w, progress=lambda: dict(state))

    async def run() -> list[str]:
        q = hub.subscribe()
        last = ("warming", 0.5)
        w.poll()
        _touch(root / "workspace" / "memory" / "tasks.md")
        state.update(state="done", progress=1.0)
        await hub.step(last)
        out = [q.get_nowait() for _ in range(q.qsize())]
        hub.unsubscribe(q)
        return out

    frames = asyncio.run(run())
    assert frames[0].startswith("event: ready\n")
    assert frames[1].startswith("event: changed\n")
    assert '"usage"' in frames[1] and '"tasks"' in frames[1]


def test_frame_format() -> None:
    assert frame("ready", {"at": "x"}) == 'event: ready\ndata: {"at":"x"}\n\n'


def test_head_and_post_rejected_without_slot(root: Path) -> None:
    c = client_for(root)
    hub = c.app.state.events
    resp = c.head("/api/v1/events")
    assert resp.status_code == 405
    assert_error(c.post("/api/v1/events", json={}), 405, "METHOD_NOT_ALLOWED")
    assert hub.active == 0


@pytest.mark.parametrize(
    "headers",
    [
        {"Origin": "http://evil.example"},
        {"Origin": "null"},
        {"Sec-Fetch-Site": "cross-site"},
    ],
)
def test_cross_origin_forbidden(root: Path, headers: dict[str, str]) -> None:
    c = client_for(root)
    assert_error(c.get("/api/v1/events", headers=headers), 403, "FORBIDDEN_ORIGIN")
    assert c.app.state.events.active == 0


def test_stream_limit_503(root: Path) -> None:
    c = client_for(root)
    hub = c.app.state.events
    hub.subscribers.update(asyncio.Queue() for _ in range(hub.limit))
    assert_error(c.get("/api/v1/events"), 503, "TOO_MANY_STREAMS")


def test_live_stream_receives_change_within_5s(root: Path) -> None:
    """실제 uvicorn 위에서: 연결 → retry·ready 프레임 → tasks.md 변경 → 5초 안에 changed."""
    import socket
    import threading

    import httpx
    import uvicorn
    from backend_support import make_settings

    from app.main import create_app

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    settings = dataclasses.replace(make_settings(root), port=port)
    server = uvicorn.Server(
        uvicorn.Config(
            create_app(settings),
            host="127.0.0.1",
            port=port,
            log_config=None,
            access_log=False,
            lifespan="off",
        )
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        for _ in range(100):
            if server.started:
                break
            time.sleep(0.05)
        url = f"http://127.0.0.1:{port}/api/v1/events"
        with httpx.Client(timeout=10) as client, client.stream("GET", url) as resp:
            assert resp.status_code == 200
            assert resp.headers["content-type"].startswith("text/event-stream")
            lines = resp.iter_lines()
            assert next(lines) == "retry: 5000"
            start = time.monotonic()
            touched = False
            seen = ""
            for line in lines:
                if line.startswith("event: ") and not touched:
                    time.sleep(1.2)  # 허브가 기준선을 잡은 뒤 바꾼다
                    _touch(root / "workspace" / "memory" / "tasks.md")
                    touched = True
                if line.startswith("data: ") and touched and '"topics"' in line:
                    seen = line
                    break
                assert time.monotonic() - start < 8
            assert '"tasks"' in seen
    finally:
        server.should_exit = True
        thread.join(5)
