"""S-12 일시정지/재개 E2E (FR-005, QS-11, ADR-004): 실서버 + 실제 루프 CLI.

서버는 `python -m app` 서브프로세스(임시 포트, 127.0.0.1, fixture 경로), CLI 는 workspace 로 복사한
`aidlc.py loop-start / loop-check / wait-resume / loop-end` 를 서브프로세스로 실행한다. 대기 시간은
`wait-resume --max-wait 1`(최소값)이나 재개 요청으로 끝나게 해서 짧게 유지한다.
exit code: 0 정상/재개, 10 일시정지, 20 일시정지 상한 초과, 2 제어 파일 broken (loop-cli 계약 §5).
exit 64·1·NO_LOOP 응답은 backend `tests/unit/test_loop_cli.py` 범위다.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fixtures import contracts
from fixtures.engine import install_engine
from fixtures.live_server import LiveServer, live_server
from fixtures.runtime_files import (
    HEARTBEAT_EXPIRY_SEC,
    control_doc,
    iso,
    loop_status_doc,
    write_json,
)

CLI_TIMEOUT_SEC = 20
POLL_TIMEOUT_SEC = 10.0
EXIT_OK, EXIT_PAUSED, EXIT_PAUSE_TIMEOUT, EXIT_CONTROL_BROKEN = 0, 10, 20, 2
BROKEN_CONTROL_FILES = {
    "truncated": b'{"schema": 1, "seq": 7, "state": "pa',
    "not_an_object": b"[1, 2, 3]",
    "wrong_types": b'{"schema": 1, "seq": "7", "state": "pause", '
    b'"requested_at": "2026-10-23T09:00:00Z", "max_pause_sec": 7200}',
}


class Cli:
    """workspace 안의 `aidlc.py` 로 루프 서브커맨드를 실행한다."""

    def __init__(self, root: Path, fake_home: Path) -> None:
        self.script = install_engine(root)
        self.env = {**os.environ, "HOME": str(fake_home), "USERPROFILE": str(fake_home)}
        self.env["PYTHONDONTWRITEBYTECODE"] = "1"

    def start(self, *argv: str) -> subprocess.Popen[str]:
        return subprocess.Popen(
            [sys.executable, str(self.script), *argv],
            env=self.env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def run(self, *argv: str) -> tuple[int, str]:
        """(exit code, stdout 한 줄). stdout 은 `AIDLC-LOOP <sub> <RESULT> k=v ...` 한 줄뿐이다."""
        proc = self.start(*argv)
        out, _ = proc.communicate(timeout=CLI_TIMEOUT_SEC)
        assert len(out.splitlines()) == 1, out
        return proc.returncode, out.strip()


@pytest.fixture
def setup(workspace_factory, claude_home_factory, tmp_path):
    workspace = workspace_factory("full")
    cli = Cli(workspace.root, tmp_path)
    home = claude_home_factory(workspace.root).home
    with live_server(workspace.root, home, tmp_path) as server:
        yield workspace, cli, server


def expect(code: int, line: str, want_code: int, result: str) -> None:
    """exit code 와 stdout 의 RESULT 단어(`AIDLC-LOOP <sub> <RESULT> ...`)를 함께 확인한다."""
    assert (code, f" {result} " in line) == (want_code, True), (code, line)


def control_view(server: LiveServer) -> dict:
    response = server.client.get("/api/v1/control")
    assert response.status_code == 200
    return response.json()


def wait_for_view(server: LiveServer, view: str) -> dict:
    deadline = time.monotonic() + POLL_TIMEOUT_SEC
    while True:
        data = control_view(server)["data"]
        if data["view"] == view or time.monotonic() > deadline:
            assert data["view"] == view, data["view"]
            return data
        time.sleep(0.1)


def post(server: LiveServer, action: str):
    return server.client.post(f"/api/v1/control/{action}", json={})


def now_utc() -> datetime:
    return datetime.now(UTC)


def test_pause_then_resume_through_dashboard_and_cli(setup) -> None:
    workspace, cli, server = setup

    code, line = cli.run("loop-start", "3")
    expect(code, line, EXIT_OK, "STARTED")
    assert control_view(server)["data"]["view"] == "V3"  # 실행 중

    response = post(server, "pause")  # 대시보드의 일시정지 버튼
    assert response.status_code == 200
    assert response.json()["data"]["view"] == "V2"  # 일시정지 요청됨
    control = json.loads(workspace.control_file.read_text(encoding="utf-8"))
    assert contracts.schema_errors(control, "control") == []
    assert control["state"] == "pause"

    code, line = cli.run("loop-check", "1")  # 사이클 경계에서 요청을 본다
    expect(code, line, EXIT_PAUSED, "PAUSE")

    code, line = cli.run(
        "wait-resume", "--max-wait", "1"
    )  # 재개가 없으면 대기 상한에서 다시 10
    expect(code, line, EXIT_PAUSED, "STILL_PAUSED")
    assert wait_for_view(server, "V4")["can_resume"]  # 일시정지됨

    waiting = cli.start("wait-resume", "--max-wait", "30")
    wait_for_view(server, "V4")
    assert waiting.poll() is None  # 재개 전에는 계속 기다린다
    assert post(server, "resume").status_code == 200  # 대시보드의 재개 버튼
    out, _ = waiting.communicate(timeout=CLI_TIMEOUT_SEC)
    expect(waiting.returncode, out, EXIT_OK, "RESUMED")
    assert control_view(server)["data"]["view"] == "V3"

    code, line = cli.run("loop-check", "2")  # 남은 반복은 계속 진행
    expect(code, line, EXIT_OK, "CONTINUE")
    code, line = cli.run("loop-end", "done", "--done", "3")
    expect(code, line, EXIT_OK, "ENDED")
    assert control_view(server)["data"]["view"] == "V1"  # 루프 없음


def test_pause_over_limit_ends_loop_and_leaves_stm_untouched(setup) -> None:
    workspace, cli, server = setup
    now = now_utc()
    write_json(workspace.loop_status_file, loop_status_doc("pause_over_limit", now=now))
    write_json(workspace.control_file, control_doc("pause", seq=7, now=now))
    stm_before = (workspace.memory / "short-term.md").read_bytes()
    assert wait_for_view(server, "V4")["loop_state"] == "paused"

    code, line = cli.run("wait-resume", "--max-wait", "1")

    expect(code, line, EXIT_PAUSE_TIMEOUT, "PAUSE_TIMEOUT")
    status = json.loads(workspace.loop_status_file.read_text(encoding="utf-8"))
    assert contracts.schema_errors(status, "loop-status") == []
    assert (status["state"], status["ended_reason"]) == ("ended", "pause_timeout")
    assert (workspace.memory / "short-term.md").read_bytes() == stm_before
    assert control_view(server)["data"]["view"] == "V1"


def test_expired_heartbeat_while_paused_shows_no_session(setup) -> None:
    workspace, _, server = setup
    now = now_utc()
    stale = now - timedelta(seconds=HEARTBEAT_EXPIRY_SEC + 60)
    doc = loop_status_doc("paused", now=now) | {"heartbeat_at": iso(stale)}
    write_json(workspace.loop_status_file, doc)

    assert wait_for_view(server, "V6")["can_resume"] is False  # 세션 없음


@pytest.mark.parametrize("broken", BROKEN_CONTROL_FILES, ids=list(BROKEN_CONTROL_FILES))
def test_broken_control_file_keeps_loop_running_with_exit_2(broken, setup) -> None:
    workspace, cli, server = setup
    workspace.control_file.write_bytes(BROKEN_CONTROL_FILES[broken])

    code, line = cli.run("loop-start", "2")
    expect(code, line, EXIT_CONTROL_BROKEN, "CONTROL_BROKEN")
    code, line = cli.run("loop-check", "1")
    expect(code, line, EXIT_CONTROL_BROKEN, "CONTROL_BROKEN")
    code, line = cli.run("wait-resume", "--max-wait", "1")
    expect(code, line, EXIT_CONTROL_BROKEN, "CONTROL_BROKEN")

    response = server.client.get("/api/v1/control")
    assert response.status_code == 200  # 대시보드도 500 이 아니라 부분 상태로 응답
    assert response.json()["meta"]["status"] in {"partial", "error"}
    status = json.loads(workspace.loop_status_file.read_text(encoding="utf-8"))
    assert status["state"] == "running"  # 제어 파일이 깨져도 루프는 계속된다
