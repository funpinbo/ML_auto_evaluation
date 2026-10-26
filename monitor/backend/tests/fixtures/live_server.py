"""실서버 서브프로세스 도우미 (qa, T-013): `python -m app` 을 임시 포트·127.0.0.1·fixture 경로로 기동한다.

- 경로는 환경 변수(`AIDLC_ROOT`, `CLAUDE_HOME`)로만 주고, HOME 도 임시 경로로 바꾼다 (실제 `~/.claude` 금지).
- 서버의 stdout/stderr 는 파일로 받아 종료 뒤 `log_text()` 로 읽는다 (본문 비노출 검사 대상).
- SSE 는 `sse_frames()` 가 `\n\n` 로 끝나는 프레임을 하나씩 돌려준다.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from .engine import BACKEND_DIR

HOST = "127.0.0.1"
START_TIMEOUT_SEC = 30.0
STOP_TIMEOUT_SEC = 10.0


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind((HOST, 0))
        return int(sock.getsockname()[1])


@dataclass
class LiveServer:
    port: int
    process: subprocess.Popen[bytes]
    log_path: Path
    client: httpx.Client = field(repr=False)
    started_at: float = 0.0  # monotonic, Popen 직후
    healthy_at: float = 0.0  # monotonic, health 200 을 처음 본 시각

    @property
    def base_url(self) -> str:
        return f"http://{HOST}:{self.port}"

    def log_text(self) -> str:
        return self.log_path.read_text(encoding="utf-8", errors="replace")

    def sse_frames(self, *, timeout: float = 15.0) -> Iterator[str]:
        """`/api/v1/events` 프레임을 도착 순서대로. 호출자가 멈추면 연결을 닫는다."""
        with httpx.stream(
            "GET",
            f"{self.base_url}/api/v1/events",
            timeout=httpx.Timeout(timeout, connect=5.0),
        ) as response:
            assert response.status_code == 200
            buffer = ""
            for chunk in response.iter_text():
                buffer += chunk
                while "\n\n" in buffer:
                    frame, buffer = buffer.split("\n\n", 1)
                    yield frame + "\n\n"


def _wait_healthy(server: LiveServer) -> None:
    deadline = time.monotonic() + START_TIMEOUT_SEC
    while time.monotonic() < deadline:
        if server.process.poll() is not None:
            raise RuntimeError(
                f"서버가 기동 중 종료됨 (exit {server.process.returncode})"
            )
        try:
            if server.client.get("/api/v1/health").status_code == 200:
                server.healthy_at = time.monotonic()
                return
        except httpx.TransportError:
            pass
        time.sleep(0.05)
    raise TimeoutError("서버 health 가 제한 시간 안에 200 이 되지 않음")


@contextmanager
def live_server(
    workspace_root: Path, claude_home: Path, work_dir: Path
) -> Iterator[LiveServer]:
    """`with live_server(root, home, tmp_path) as server:` — 종료 시 SIGTERM, 안 죽으면 kill."""
    port = free_port()
    log_path = work_dir / f"server-{port}.log"
    env = {
        **os.environ,
        "AIDLC_ROOT": str(workspace_root),
        "CLAUDE_HOME": str(claude_home),
        "HOME": str(work_dir),
        "USERPROFILE": str(work_dir),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    env.pop("AIDLC_MONITOR_PORT", None)
    with log_path.open("wb") as log:
        started = time.monotonic()
        process = subprocess.Popen(
            [sys.executable, "-m", "app", "--port", str(port)],
            cwd=BACKEND_DIR,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        client = httpx.Client(base_url=f"http://{HOST}:{port}", timeout=30.0)
        server = LiveServer(port, process, log_path, client, started_at=started)
        try:
            _wait_healthy(server)
            yield server
        finally:
            client.close()
            process.terminate()
            try:
                process.wait(STOP_TIMEOUT_SEC)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
