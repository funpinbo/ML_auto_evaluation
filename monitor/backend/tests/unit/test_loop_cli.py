"""루프 제어 CLI 계약 (contracts/loop-cli.md §3~§8, D-09·D-10, FR-005 AC-2·AC-11~AC-14·AC-18).

시계·sleep 은 `SimClock` 으로 주입한다(실제 대기 없음). 쓴 `loop-status.json` 은 매번 계약 스키마로 검증하고,
CLI 가 `.control.json` 을 만들거나 고치지 않는지(R-10) 를 모든 시나리오에서 확인한다.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from fixtures.contracts import schema_errors
from fixtures.runtime_files import control_doc, write_json
from loop_support import LOOP_CONTROL_PATH, REPO_ROOT, T0, SimClock, lc, run_cli


@pytest.fixture
def root(tmp_path: Path) -> Path:
    (tmp_path / "ws" / "workspace" / "memory").mkdir(parents=True)
    return tmp_path / "ws"


def ctl_path(root: Path) -> Path:
    return root / "workspace" / "memory" / ".control.json"


def status_path(root: Path) -> Path:
    return root / "workspace" / "memory" / ".monitor" / "loop-status.json"


def status(root: Path) -> dict:
    doc = json.loads(status_path(root).read_text("utf-8"))
    assert schema_errors(doc, "loop-status") == []
    assert type(doc["baseline_seq"]) is int
    return doc


def write_control(root: Path, state: str, seq: int, **kw) -> None:
    write_json(ctl_path(root), control_doc(state, seq, **kw))


def control_snapshot(root: Path) -> tuple[bool, bytes | None, int | None]:
    p = ctl_path(root)
    if not p.exists():
        return (False, None, None)
    return (True, p.read_bytes(), p.stat().st_mtime_ns)


# ---------------------------------------------------------------- loop-start
def test_loop_start_records_baseline_and_fields(root: Path) -> None:
    write_control(root, "pause", 7)
    snap = control_snapshot(root)
    r = run_cli(root, "loop-start", "3")
    assert r.code == 0 and r.result == "STARTED"
    assert r.keys["total"] == "3" and r.keys["baseline"] == "7"
    doc = status(root)
    assert doc["state"] == "running" and doc["baseline_seq"] == 7
    assert doc["iterations_total"] == 3 and doc["iterations_done"] == 0
    assert doc["started_at"] == doc["heartbeat_at"] == T0.isoformat()
    assert doc["paused_since"] is None and doc["ended_reason"] is None
    assert r.keys["run"] == doc["run_id"][:8]
    assert r.err == ""
    assert control_snapshot(root) == snap


def test_loop_start_without_control_baseline_zero(root: Path) -> None:
    r = run_cli(root, "loop-start", "1")
    assert (r.code, r.keys["baseline"]) == (0, "0")
    assert not ctl_path(root).exists()


def test_loop_start_broken_control_exit_2_baseline_zero(root: Path) -> None:
    ctl_path(root).write_text("{broken", "utf-8")
    r = run_cli(root, "loop-start", "2")
    assert r.code == 2 and r.result == "CONTROL_BROKEN"
    assert status(root)["baseline_seq"] == 0
    assert r.err


def test_loop_start_overwrites_dead_session(root: Path) -> None:
    run_cli(root, "loop-start", "3")
    run_cli(root, "wait-resume", "--max-wait", "1")
    old = status(root)
    assert old["state"] == "paused"
    run_cli(root, "loop-start", "2")
    new = status(root)
    assert new["run_id"] != old["run_id"] and new["state"] == "running"
    assert new["paused_since"] is None


# ---------------------------------------------------------------- loop-check
def test_loop_check_continue_and_heartbeat(root: Path) -> None:
    run_cli(root, "loop-start", "3")
    clock = SimClock()
    clock.advance(600)
    r = run_cli(root, "loop-check", "1", clock=clock)
    assert r.code == 0 and r.result == "CONTINUE"
    assert r.keys == {"done": "1/3", "seq": "0", "baseline": "0"}
    doc = status(root)
    assert doc["iterations_done"] == 1
    assert doc["heartbeat_at"] == clock.now().isoformat()


def test_old_pause_ignored_by_baseline(root: Path) -> None:
    """AC-12: 이전 루프에서 남은 pause(seq 7) 는 새 루프를 멈추지 않는다."""
    write_control(root, "pause", 7)
    run_cli(root, "loop-start", "2")
    assert run_cli(root, "loop-check", "1").code == 0


def test_loop_check_pause_exit_10(root: Path) -> None:
    write_control(root, "running", 7)
    run_cli(root, "loop-start", "3")
    write_control(root, "pause", 8)
    r = run_cli(root, "loop-check", "1")
    assert r.code == 10 and r.result == "PAUSE"
    assert r.keys == {"done": "1/3", "seq": "8", "baseline": "7"}
    assert status(root)["state"] == "running"


def test_loop_check_resume_after_pause_request_continues(root: Path) -> None:
    """AC-8: pause → resume (seq 증가) 이면 최신 요청 기준으로 계속."""
    write_control(root, "running", 7)
    run_cli(root, "loop-start", "3")
    write_control(root, "pause", 8)
    write_control(root, "running", 9)
    assert run_cli(root, "loop-check", "1").code == 0


def test_loop_check_broken_control_exit_2(root: Path) -> None:
    run_cli(root, "loop-start", "3")
    ctl_path(root).write_text('{"schema": 1, "seq": 8, "state": "pa', "utf-8")
    r = run_cli(root, "loop-check", "1")
    assert r.code == 2 and r.result == "CONTROL_BROKEN" and r.keys["seq"] == "-"
    assert status(root)["iterations_done"] == 1


@pytest.mark.parametrize("prep", ["missing", "broken", "ended", "schema"])
def test_loop_check_no_loop(root: Path, prep: str) -> None:
    """D-10 / AC-11: 활성 루프 없음 → 아무것도 쓰지 않고 exit 0 NO_LOOP, stderr 경고."""
    write_control(root, "pause", 9)
    if prep == "broken":
        status_path(root).parent.mkdir(parents=True)
        status_path(root).write_text('{"schema": 1, "run_id": ', "utf-8")
    elif prep in ("ended", "schema"):
        run_cli(root, "loop-start", "2")
        run_cli(root, "loop-end", "done")
        if prep == "schema":
            doc = json.loads(status_path(root).read_text("utf-8"))
            doc.update(state="running", ended_reason=None)
            doc.pop("run_id")
            status_path(root).write_text(json.dumps(doc), "utf-8")
    before = status_path(root).read_bytes() if status_path(root).exists() else None
    snap = control_snapshot(root)
    r = run_cli(root, "loop-check", "1")
    assert r.code == 0 and r.result == "NO_LOOP" and r.err
    after = status_path(root).read_bytes() if status_path(root).exists() else None
    assert after == before
    assert control_snapshot(root) == snap
    w = run_cli(root, "wait-resume", "--max-wait", "5")
    assert w.code == 0 and w.result == "NO_LOOP"
    assert (
        status_path(root).read_bytes() if status_path(root).exists() else None
    ) == before


# ---------------------------------------------------------------- wait-resume
def _paused_loop(root: Path, *, baseline: int = 7) -> None:
    write_control(root, "running", baseline)
    run_cli(root, "loop-start", "3")
    write_control(root, "pause", baseline + 1)
    assert run_cli(root, "loop-check", "1").code == 10


def test_wait_resume_resumes_on_running_seq_gt_baseline(root: Path) -> None:
    _paused_loop(root)
    clock = SimClock()
    seen: list[str] = []

    def on_tick(n: int) -> None:
        seen.append(status(root)["state"])
        if n == 3:
            write_control(root, "running", 9)

    clock.on_tick = on_tick
    r = run_cli(root, "wait-resume", clock=clock)
    assert r.code == 0 and r.result == "RESUMED"
    assert clock.ticks == 3  # 쓰인 직후 다음 tick 에 반환
    assert seen == ["paused"] * 3
    doc = status(root)
    assert doc["state"] == "running" and doc["paused_since"] is None
    assert r.keys["paused_sec"] == "3" and r.keys["done"] == "1/3"


def test_wait_resume_max_wait_exit_10_keeps_paused(root: Path) -> None:
    _paused_loop(root)
    clock = SimClock()
    r = run_cli(root, "wait-resume", "--max-wait", "5", clock=clock)
    assert r.code == 10 and r.result == "STILL_PAUSED"
    assert clock.ticks == 5
    doc = status(root)
    assert doc["state"] == "paused" and doc["paused_since"] == T0.isoformat()
    assert r.keys["remaining_sec"] == str(7200 - 5)


def test_wait_resume_default_max_wait_540(root: Path) -> None:
    _paused_loop(root)
    clock = SimClock()
    assert run_cli(root, "wait-resume", clock=clock).code == 10
    assert clock.ticks == 540


def test_wait_resume_heartbeat_every_30s(root: Path) -> None:
    _paused_loop(root)
    clock = SimClock()
    beats: list[str] = []

    def on_tick(n: int) -> None:
        beats.append(status(root)["heartbeat_at"])

    clock.on_tick = on_tick
    run_cli(root, "wait-resume", "--max-wait", "95", clock=clock)
    distinct = sorted(set(beats))
    # 진입(0 s) → 30 s → 60 s → 90 s 에 갱신
    assert [
        int((lc.parse_ts(b) - T0).total_seconds())
        for b in distinct  # type: ignore[operator]
    ] == [0, 30, 60, 90]


def test_paused_since_accumulates_across_calls_and_cap_exit_20(root: Path) -> None:
    """D-10 / AC-13·AC-14: 반복 호출을 넘어 paused_since 유지, 상한(작은 max_pause_sec) 초과 → exit 20."""
    write_control(root, "running", 7)
    run_cli(root, "loop-start", "3")
    write_control(root, "pause", 8, max_pause_sec=600)
    run_cli(root, "loop-check", "1")
    clock = SimClock()
    codes = []
    for _ in range(5):
        r = run_cli(root, "wait-resume", "--max-wait", "250", clock=clock)
        codes.append(r.code)
        if r.code != 10:
            break
        assert status(root)["paused_since"] == T0.isoformat()
        clock.advance(3)  # 스킬의 재호출 간격
    assert codes == [10, 10, 20]
    assert r.result == "PAUSE_TIMEOUT"
    doc = status(root)
    assert doc["state"] == "ended" and doc["ended_reason"] == "pause_timeout"
    assert doc["paused_since"] == T0.isoformat()
    # 600 s 를 넘긴 첫 tick 에서 종료
    assert int((clock.now() - T0).total_seconds()) == 601
    end = run_cli(root, "loop-end", "done", "--done", "1")
    assert end.result == "ALREADY_ENDED" and end.keys["reason"] == "pause_timeout"
    assert status(root)["ended_reason"] == "pause_timeout"


def test_new_episode_after_resume_resets_paused_since(root: Path) -> None:
    _paused_loop(root)
    clock = SimClock()
    clock.on_tick = lambda n: write_control(root, "running", 9) if n == 2 else None
    assert run_cli(root, "wait-resume", clock=clock).code == 0
    clock.on_tick = None
    clock.advance(1000)
    write_control(root, "pause", 10)
    assert run_cli(root, "loop-check", "2", clock=clock).code == 10  # AC-9 재일시정지
    start = clock.now()
    run_cli(root, "wait-resume", "--max-wait", "1", clock=clock)
    assert status(root)["paused_since"] == start.isoformat()


def test_wait_resume_broken_control_exit_2_resumes(root: Path) -> None:
    """SQ-5 / AC-18."""
    _paused_loop(root)
    clock = SimClock()
    clock.on_tick = lambda n: (
        ctl_path(root).write_text('{"seq": 8', "utf-8") if n == 2 else None
    )
    r = run_cli(root, "wait-resume", clock=clock)
    assert r.code == 2 and r.result == "CONTROL_BROKEN"
    doc = status(root)
    assert doc["state"] == "running" and doc["paused_since"] is None


def test_wait_resume_deleted_control_keeps_waiting(root: Path) -> None:
    """SQ-3: 제어 파일 삭제 = 없음(정상) → 대기 유지."""
    _paused_loop(root)
    clock = SimClock()
    states: list[str] = []

    def on_tick(n: int) -> None:
        if n == 1:
            ctl_path(root).unlink()
        states.append(status(root)["state"])

    clock.on_tick = on_tick
    r = run_cli(root, "wait-resume", "--max-wait", "4", clock=clock)
    assert r.code == 10 and states == ["paused"] * 4


def test_decision_order_resume_beats_cap(root: Path) -> None:
    """같은 tick 판정 순서: 재개 → broken → 상한 → max-wait."""
    write_control(root, "running", 7)
    run_cli(root, "loop-start", "3")
    write_control(root, "pause", 8, max_pause_sec=600)
    run_cli(root, "loop-check", "1")
    clock = SimClock()
    run_cli(root, "wait-resume", "--max-wait", "1", clock=clock)
    clock.advance(700)  # 이미 상한을 넘김
    write_control(root, "running", 9, max_pause_sec=600)
    assert run_cli(root, "wait-resume", "--max-wait", "1", clock=clock).code == 0


def test_cap_uses_current_control_value(root: Path) -> None:
    """max_pause_sec 는 판독 시점의 제어 파일 값. 없으면 7200."""
    _paused_loop(root)
    clock = SimClock()
    run_cli(root, "wait-resume", "--max-wait", "1", clock=clock)
    ctl_path(root).unlink()
    clock.advance(7000)
    assert run_cli(root, "wait-resume", "--max-wait", "100", clock=clock).code == 10
    clock.advance(5)
    assert run_cli(root, "wait-resume", "--max-wait", "200", clock=clock).code == 20


# ---------------------------------------------------------------- loop-end
@pytest.mark.parametrize("reason", ["done", "blocked", "no_task"])
def test_loop_end_reasons(root: Path, reason: str) -> None:
    run_cli(root, "loop-start", "3")
    r = run_cli(root, "loop-end", reason, "--done", "2")
    assert r.code == 0 and r.result == "ENDED"
    assert r.keys == {"reason": reason, "done": "2/3"}
    doc = status(root)
    assert doc["state"] == "ended" and doc["ended_reason"] == reason
    assert doc["iterations_done"] == 2 and doc["paused_since"] is None


def test_loop_end_from_paused_clears_paused_since(root: Path) -> None:
    _paused_loop(root)
    run_cli(root, "wait-resume", "--max-wait", "1")
    run_cli(root, "loop-end", "blocked", "--done=1")
    doc = status(root)
    assert doc["state"] == "ended" and doc["paused_since"] is None


def test_loop_end_no_loop_and_already_ended(root: Path) -> None:
    r = run_cli(root, "loop-end", "done")
    assert (r.code, r.result) == (0, "NO_LOOP")
    assert not status_path(root).exists()
    run_cli(root, "loop-start", "1")
    run_cli(root, "loop-end", "done", "--done", "1")
    before = status_path(root).read_bytes()
    r = run_cli(root, "loop-end", "blocked")
    assert (r.code, r.result) == (0, "ALREADY_ENDED")
    assert status_path(root).read_bytes() == before


# ---------------------------------------------------------------- usage 64 / 예외 1
USAGE_CASES = [
    [],
    ["loop-bogus"],
    ["loop-start"],
    ["loop-start", "0"],
    ["loop-start", "11"],
    ["loop-start", "-1"],
    ["loop-start", "3.0"],
    ["loop-start", "x"],
    ["loop-start", "3", "4"],
    ["loop-start", "٣"],  # 비 ASCII 숫자
    ["loop-check"],
    ["loop-check", "11"],
    ["loop-check", "1", "--x"],
    ["wait-resume", "--max-wait"],
    ["wait-resume", "--max-wait", "0"],
    ["wait-resume", "--max-wait", "581"],
    ["wait-resume", "--max-wait", "1", "--max-wait", "2"],
    ["wait-resume", "--max-wait=abc"],
    ["wait-resume", "extra"],
    ["wait-resume", "--other", "1"],
    ["loop-end"],
    ["loop-end", "pause_timeout"],
    ["loop-end", "finished"],
    ["loop-end", "done", "--done", "11"],
    ["loop-end", "done", "blocked"],
]


@pytest.mark.parametrize("argv", USAGE_CASES, ids=lambda a: " ".join(a) or "<none>")
def test_usage_errors_exit_64(root: Path, argv: list[str]) -> None:
    r = run_cli(root, *argv)
    assert r.code == 64, (argv, r)
    assert r.out == "" and "usage" in r.err
    assert not status_path(root).exists()


def test_done_exceeding_total_is_usage_error(root: Path) -> None:
    run_cli(root, "loop-start", "2")
    before = status_path(root).read_bytes()
    assert run_cli(root, "loop-check", "3").code == 64
    assert run_cli(root, "loop-end", "done", "--done", "3").code == 64
    assert status_path(root).read_bytes() == before


def test_unexpected_exception_exit_1_type_only(root: Path) -> None:
    def boom() -> object:
        raise RuntimeError("SECRETMARKER /home/someone/x")

    run_cli(root, "loop-start", "2")
    out, err = io.StringIO(), io.StringIO()
    env = lc.Env(root=root, now=boom, out=out, err=err)
    assert lc.main(["loop-check", "1"], env) == 1
    assert out.getvalue() == ""
    assert err.getvalue().strip() == "aidlc-loop: unexpected error: RuntimeError"


def test_status_write_failure_warns_without_changing_exit(root: Path) -> None:
    """§2: loop-status 쓰기 실패는 stderr 경고만, exit code 불변. 임시 파일 정리."""
    write_control(root, "pause", 3)

    def deny(src: str, dst: str) -> None:
        raise PermissionError(13, "denied")

    clock = SimClock()
    r = run_cli(root, "loop-start", "2", clock=clock, replace=deny)
    assert r.code == 0 and r.result == "STARTED"
    assert "could not write loop status (PermissionError)" in r.err
    assert clock.sleeps == [0.05] * 4  # 5회 시도
    assert not status_path(root).exists()
    assert list(status_path(root).parent.iterdir()) == []


def test_status_write_retry_then_success(root: Path) -> None:
    calls = {"n": 0}

    def flaky(src: str, dst: str) -> None:
        calls["n"] += 1
        if calls["n"] < 3:
            raise PermissionError(13, "busy")
        os.replace(src, dst)

    r = run_cli(root, "loop-start", "2", replace=flaky)
    assert r.code == 0 and r.err == "" and calls["n"] == 3
    assert status(root)["state"] == "running"


# ---------------------------------------------------------------- 상태 전이 표 전체 (§8) + 단일 작성자
def test_state_transition_table(root: Path) -> None:
    """§8 상태 전이 전체. 전 과정에서 CLI 는 .control.json 을 쓰지 않는다(SQ-15, R-10)."""
    write_control(root, "running", 4)
    seen: list[tuple[str, int, str]] = []

    def step(*argv: str) -> None:
        code = run_cli(root, *argv).code
        seen.append((argv[0], code, status(root)["state"]))

    step("loop-start", "3")  # (없음) → running
    step("loop-check", "1")  # running → running (0)
    step("wait-resume", "--max-wait", "1")  # running → paused (10)
    step("wait-resume", "--max-wait", "1")  # paused → paused (10)
    step("loop-end", "blocked")  # paused → ended
    step("loop-start", "2")  # ended → running
    write_control(root, "pause", 5)
    step("loop-check", "1")  # running → running (10)
    step("wait-resume", "--max-wait", "1")  # → paused (10)
    write_control(root, "running", 6)
    step("wait-resume", "--max-wait", "1")  # paused → running (0)
    # 제어 파일 running(seq 6) 이 남아 있으면 재진입해도 즉시 재개 (최신 요청 기준)
    step("wait-resume", "--max-wait", "1")  # running → paused → running (0)
    write_control(root, "pause", 7)
    step("wait-resume", "--max-wait", "1")  # running → paused (10)
    ctl_path(root).write_text("{", "utf-8")
    snap = control_snapshot(root)
    step("wait-resume", "--max-wait", "1")  # paused → running (2)
    step("loop-end", "done", "--done", "2")  # running → ended
    assert seen == [
        ("loop-start", 0, "running"),
        ("loop-check", 0, "running"),
        ("wait-resume", 10, "paused"),
        ("wait-resume", 10, "paused"),
        ("loop-end", 0, "ended"),
        ("loop-start", 0, "running"),
        ("loop-check", 10, "running"),
        ("wait-resume", 10, "paused"),
        ("wait-resume", 0, "running"),
        ("wait-resume", 0, "running"),
        ("wait-resume", 10, "paused"),
        ("wait-resume", 2, "running"),
        ("loop-end", 0, "ended"),
    ]
    assert control_snapshot(root) == snap


def test_cli_source_never_writes_control_file() -> None:
    """R-10 코드 점검: CLI 의 쓰기 대상은 loop-status 하나 — control 경로는 read_control 에만 쓰인다."""
    src = LOOP_CONTROL_PATH.read_text("utf-8")
    assert src.count("control_path") == src.count("read_control(env.control_path)") + 1
    assert "write_status(" in src and "def write_control" not in src


# ---------------------------------------------------------------- 실제 서브프로세스 (aidlc.py 등록 블록)
@pytest.fixture
def repo_copy(tmp_path: Path) -> Path:
    root = tmp_path / "repo copy 한글"
    (root / "aidlc" / "scripts").mkdir(parents=True)
    (root / "workspace" / "memory").mkdir(parents=True)
    for name in ("aidlc.py", "loop_control.py"):
        shutil.copy2(REPO_ROOT / "aidlc" / "scripts" / name, root / "aidlc" / "scripts")
    return root


def _sub(root: Path, *argv: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(root / "aidlc" / "scripts" / "aidlc.py"), *argv],
        cwd=str(root.parent),  # cwd 비의존
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=False,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": ""},
    )


def test_subprocess_exit_codes_and_single_line(repo_copy: Path) -> None:
    root = repo_copy
    write_control(root, "running", 7)
    cases = [
        (["loop-start", "3"], 0, "STARTED"),
        (["loop-check", "1"], 0, "CONTINUE"),
        (["loop-start", "x"], 64, None),
        (["wait-resume", "--max-wait", "999"], 64, None),
        (["loop-end", "nope"], 64, None),
    ]
    for argv, code, result in cases:
        p = _sub(root, *argv)
        assert p.returncode == code, (argv, p.returncode, p.stderr)
        if result:
            lines = p.stdout.splitlines()
            assert len(lines) == 1 and lines[0].split()[:3] == [
                "AIDLC-LOOP",
                argv[0],
                result,
            ]
        else:
            assert p.stdout == ""
        for text in (p.stdout, p.stderr):
            assert str(root) not in text and "workspace" not in text
            assert "Traceback" not in text
    write_control(root, "pause", 8)
    assert _sub(root, "loop-check", "2").returncode == 10
    p = _sub(root, "wait-resume", "--max-wait", "1")
    assert p.returncode == 10 and "STILL_PAUSED" in p.stdout
    ctl_path(root).write_text("[]", "utf-8")
    assert _sub(root, "wait-resume", "--max-wait", "2").returncode == 2
    assert _sub(root, "loop-end", "done", "--done", "2").returncode == 0
    p = _sub(root, "loop-check", "1")
    assert p.returncode == 0 and "NO_LOOP" in p.stdout
    assert not list(root.rglob("__pycache__"))
    assert (
        schema_errors(json.loads(status_path(root).read_text("utf-8")), "loop-status")
        == []
    )


def test_subprocess_unexpected_error_exit_1(repo_copy: Path) -> None:
    """status 경로가 디렉터리 → 읽기는 broken(NO_LOOP), loop-start 의 쓰기 실패는 경고만."""
    status_path(repo_copy).mkdir(parents=True)
    p = _sub(repo_copy, "loop-start", "2")
    assert p.returncode == 0 and "could not write" in p.stderr
    # 모듈 import 실패 → exit 1, 예외 종류만
    (repo_copy / "aidlc" / "scripts" / "loop_control.py").write_text(
        "raise ValueError('SECRET')\n"
    )
    p = _sub(repo_copy, "loop-check", "1")
    assert p.returncode == 1
    assert p.stderr.strip() == "aidlc-loop: unexpected error: ValueError"
