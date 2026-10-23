"""GET /api/v1/control, POST /control/pause·resume + loop-cli §7.4 SQ-1~SQ-21 (FR-005, ADR-004, D-39·D-40).

CLI 는 같은 workspace 루트에 대해 in-process 로 실행한다(`run_cli`, 시계 주입). "POST" 는 실제 앱 라우트.
모든 시나리오에서 쓰인 `.control.json` 을 계약 스키마로 검증하고, 대시보드가 `loop-status.json` 을 쓰지
않는지(R-10, SQ-15) 확인한다.
"""

from __future__ import annotations

import json
import os
import threading
import time
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from backend_support import assert_error, client_for, make_client, make_settings
from fixtures.contracts import schema_errors
from fixtures.jsonl_gen import FIXED_NOW
from fixtures.runtime_files import control_doc, loop_status_doc, write_json
from loop_support import SimClock, run_cli

from app.main import create_app
from app.services import control as control_service

PAUSE, RESUME, CONTROL = (
    "/api/v1/control/pause",
    "/api/v1/control/resume",
    "/api/v1/control",
)
FIXED_MSG = "제어 파일을 쓰지 못했습니다."


class Ws:
    """workspace 1개 + 대시보드(재시작 가능) + CLI."""

    def __init__(self, info: Any) -> None:
        self.info = info
        self.root: Path = info.root
        self.ctl: Path = info.control_file
        self.status: Path = info.loop_status_file
        self.restart()

    def restart(self, **kwargs: Any) -> None:
        self.app = create_app(make_settings(self.root), **kwargs)
        self.client = make_client(self.app)

    def post(self, path: str, body: Any = None) -> Any:
        return self.client.post(path, json={} if body is None else body)

    def cli(self, *argv: str, clock: SimClock | None = None) -> Any:
        before = self.ctl_bytes()
        r = run_cli(self.root, *argv, clock=clock)
        assert self.ctl_bytes() == before  # SQ-15: CLI 는 제어 파일을 쓰지 않는다
        return r

    def ctl_bytes(self) -> bytes | None:
        return self.ctl.read_bytes() if self.ctl.exists() else None

    def control(self) -> dict[str, Any]:
        doc = json.loads(self.ctl.read_text("utf-8"))
        assert schema_errors(doc, "control") == []
        assert type(doc["seq"]) is int
        return doc

    def set_control(self, state: str, seq: int) -> None:
        write_json(self.ctl, control_doc(state, seq))

    def start_loop(self, baseline: int = 7) -> None:
        self.set_control("running", baseline)
        r = self.cli("loop-start", "3")
        assert r.code == 0 and r.keys["baseline"] == str(baseline)

    def status_bytes(self) -> bytes | None:
        return self.status.read_bytes() if self.status.exists() else None

    def tmp_files(self) -> list[str]:
        return sorted(p.name for p in self.ctl.parent.glob(".control.json.*"))


@pytest.fixture
def ws(engine_workspace) -> Ws:
    return Ws(engine_workspace("full"))


def dash_post(ws: Ws, path: str, body: Any = None) -> Any:
    """대시보드 POST — loop-status 를 건드리지 않는다(SQ-15)."""
    before = ws.status_bytes()
    resp = ws.post(path, body)
    assert ws.status_bytes() == before
    return resp


# ---------------------------------------------------------------- SQ-1 ~ SQ-15
def test_sq01_sq02_deleted_control_then_pause(ws: Ws) -> None:
    ws.start_loop()
    ws.set_control("running", 9)
    ws.ctl.unlink()
    r = ws.cli("loop-check", "1")
    assert (r.code, r.result, r.err) == (0, "CONTINUE", "")
    assert dash_post(ws, PAUSE).status_code == 200
    assert (ws.control()["seq"], ws.control()["state"]) == (8, "pause")
    assert ws.cli("loop-check", "1").code == 10


def test_sq03_sq04_delete_during_wait_then_resume(ws: Ws) -> None:
    ws.start_loop()
    assert dash_post(ws, PAUSE).status_code == 200
    assert ws.control()["seq"] == 8
    assert ws.cli("loop-check", "1").code == 10
    clock = SimClock()
    states: list[str] = []

    def on_tick(n: int) -> None:
        states.append(json.loads(ws.status.read_text("utf-8"))["state"])
        if n == 1:
            ws.ctl.unlink()
        if n == 4:  # 3 tick 대기 후 POST resume
            resp = ws.post(RESUME)
            assert resp.status_code == 200
            assert (ws.control()["seq"], ws.control()["state"]) == (8, "running")

    clock.on_tick = on_tick
    r = run_cli(ws.root, "wait-resume", clock=clock)
    assert r.code == 0 and r.result == "RESUMED"
    assert clock.ticks == 4  # resume 이 쓰인 tick 직후 판독에서 반환 (1초 안)
    assert states[:4] == ["paused"] * 4


def test_sq05_sq06_broken_during_wait_then_recover(ws: Ws) -> None:
    ws.start_loop()
    dash_post(ws, PAUSE)
    ws.cli("loop-check", "1")
    clock = SimClock()
    clock.on_tick = lambda n: (
        ws.ctl.write_text('{"seq": 8', "utf-8") if n == 1 else None
    )
    r = run_cli(ws.root, "wait-resume", clock=clock)
    assert r.code == 2 and r.result == "CONTROL_BROKEN"
    st = json.loads(ws.status.read_text("utf-8"))
    assert st["state"] == "running" and st["paused_since"] is None
    assert ws.cli("loop-check", "2").code == 2
    view = ws.client.get(CONTROL).json()
    assert view["meta"]["status"] == "partial"
    assert control_service.MSG_CONTROL_BROKEN in view["meta"]["warnings"]
    assert dash_post(ws, RESUME).status_code == 200
    assert (ws.control()["seq"], ws.control()["state"]) == (8, "running")
    r = ws.cli("loop-check", "2")
    assert (r.code, r.result) == (0, "CONTINUE")


def test_sq07_broken_control_then_pause(ws: Ws) -> None:
    ws.start_loop()
    ws.ctl.write_text("[]", "utf-8")
    assert dash_post(ws, PAUSE).status_code == 200
    assert (ws.control()["seq"], ws.control()["state"]) == (8, "pause")
    assert ws.cli("loop-check", "1").code == 10


def test_sq08_restart_no_memory_state(ws: Ws) -> None:
    ws.start_loop()
    ws.set_control("running", 9)
    ws.restart()
    assert dash_post(ws, PAUSE).status_code == 200
    assert (ws.control()["seq"], ws.control()["state"]) == (10, "pause")


def test_sq09_restart_missing_control(ws: Ws) -> None:
    ws.start_loop()
    ws.ctl.unlink()
    ws.restart()
    assert dash_post(ws, PAUSE).status_code == 200
    assert ws.control()["seq"] == 8
    assert ws.cli("loop-check", "1").code == 10


def test_sq10_pause_then_resume_sequential(ws: Ws) -> None:
    ws.start_loop()
    ws.set_control("running", 9)
    assert dash_post(ws, PAUSE).json()["data"]["control_seq"] == 10
    assert dash_post(ws, RESUME).json()["data"]["control_seq"] == 11
    assert ws.control()["state"] == "running"
    assert ws.cli("loop-check", "1").code == 0


def test_sq10_sq11_concurrent_posts(ws: Ws) -> None:
    ws.start_loop()
    ws.set_control("running", 9)
    seqs: list[int] = []
    barrier = threading.Barrier(2)

    def worker(path: str) -> None:
        barrier.wait()
        resp = ws.post(path)
        assert resp.status_code == 200
        seqs.append(resp.json()["data"]["control_seq"])

    for paths in ((PAUSE, RESUME), (PAUSE, PAUSE)):
        seqs.clear()
        start = ws.control()["seq"]
        threads = [threading.Thread(target=worker, args=(p,)) for p in paths]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert sorted(seqs) == [
            start + 1,
            start + 2,
        ]  # 서로 다른 연속 seq, 유실·중복 없음
        assert ws.control()["seq"] == start + 2
    assert ws.control()["state"] == "pause"


def test_sq12_resume_without_loop_then_start(ws: Ws) -> None:
    assert not ws.status.exists() and not ws.ctl.exists()
    resp = dash_post(ws, RESUME)
    assert resp.status_code == 200
    assert (ws.control()["seq"], ws.control()["state"]) == (1, "running")
    r = ws.cli("loop-start", "2")
    assert r.keys["baseline"] == "1"
    ws.cli("loop-end", "done")
    before = ws.ctl_bytes()
    assert_error(dash_post(ws, PAUSE), 409, "NO_ACTIVE_LOOP")
    assert ws.ctl_bytes() == before


def test_sq13_manual_lower_seq(ws: Ws) -> None:
    ws.start_loop()
    ws.set_control("running", 3)
    dash_post(ws, PAUSE)
    assert ws.control()["seq"] == 8
    assert ws.cli("loop-check", "1").code == 10


def test_sq14_broken_at_start_baseline_zero(ws: Ws) -> None:
    ws.ctl.write_text("{", "utf-8")
    r = ws.cli("loop-start", "3")
    assert (r.code, r.keys["baseline"]) == (2, "0")
    dash_post(ws, PAUSE)
    assert ws.control()["seq"] == 1
    assert ws.cli("loop-check", "1").code == 10


# ---------------------------------------------------------------- SQ-16 ~ SQ-21
BAD_BASELINES = {
    "neg": "-1",
    "string": '"7"',
    "true": "true",
    "float": "7.0",
    "over": "9007199254740992",
    "4301": "9" * 4301,
}


@pytest.mark.parametrize("case", [*sorted(BAD_BASELINES), "schema"])
def test_sq16_bad_baseline_is_zero_and_no_loop(ws: Ws, case: str) -> None:
    ws.set_control("running", 9)
    doc = loop_status_doc("running")
    if case == "schema":
        doc.pop("run_id")
        raw = json.dumps(doc)
    else:
        raw = json.dumps(doc).replace(
            '"baseline_seq": 6', f'"baseline_seq": {BAD_BASELINES[case]}'
        )
    ws.status.parent.mkdir(parents=True, exist_ok=True)
    ws.status.write_text(raw, "utf-8")
    resp = dash_post(ws, RESUME)
    assert resp.status_code == 200
    assert '"seq": 10,' in ws.ctl.read_text("utf-8")  # 10.0 아님
    assert (ws.control()["seq"], ws.control()["state"]) == (10, "running")
    before = ws.ctl_bytes()
    assert_error(dash_post(ws, PAUSE), 409, "NO_ACTIVE_LOOP")
    assert ws.ctl_bytes() == before
    view = ws.client.get(CONTROL)
    assert view.status_code == 200
    assert view.json()["meta"]["status"] == "error"


BAD_SEQS = ["7.0", "true", "9007199254740992", "8e0", "9" * 4301]


@pytest.mark.parametrize(
    "literal", BAD_SEQS, ids=["float", "true", "over", "exp", "4301"]
)
def test_sq17_bad_control_seq_cli_and_dashboard_agree(ws: Ws, literal: str) -> None:
    ws.start_loop()
    text = json.dumps(control_doc("pause", 8)).replace('"seq": 8', f'"seq": {literal}')
    ws.ctl.write_text(text, "utf-8")
    r = ws.cli("loop-check", "1")
    assert (r.code, r.result) == (2, "CONTROL_BROKEN")
    body = ws.client.get(CONTROL).json()
    assert body["data"]["control_file"] == "broken"
    assert body["meta"]["status"] == "partial"
    assert dash_post(ws, PAUSE).status_code == 200
    assert (ws.control()["seq"], ws.control()["state"]) == (8, "pause")
    assert ws.cli("loop-check", "1").code == 10


def test_sq18_seq_overflow_not_written(ws: Ws) -> None:
    doc = loop_status_doc("running") | {"baseline_seq": control_service.SEQ_MAX}
    write_json(ws.status, doc)
    body = assert_error(dash_post(ws, PAUSE), 500, "CONTROL_WRITE_FAILED")
    assert body["error"]["message"] == FIXED_MSG
    assert not ws.ctl.exists() and ws.tmp_files() == []


def test_sq19_fifty_concurrent_posts(ws: Ws) -> None:
    ws.start_loop()
    ws.set_control("running", 9)
    results: list[tuple[int, int | None, float]] = []
    lock = threading.Lock()
    barrier = threading.Barrier(50)

    def worker(i: int) -> None:
        barrier.wait()
        t0 = time.monotonic()
        resp = ws.post(PAUSE if i % 2 else RESUME)
        took = time.monotonic() - t0
        seq = resp.json()["data"]["control_seq"] if resp.status_code == 200 else None
        if resp.status_code == 500:
            assert resp.json()["error"] == {
                "code": "CONTROL_WRITE_FAILED",
                "message": FIXED_MSG,
            }
        with lock:
            results.append((resp.status_code, seq, took))

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(50)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert {s for s, _, _ in results} <= {200, 500}
    assert max(took for _, _, took in results) <= 2.5
    ok = sorted(seq for s, seq, _ in results if s == 200)  # type: ignore[type-var]
    # 응답 본문의 seq 는 응답 시점 재판독이라 겹칠 수 있다 — 파일 기준으로 연속성 확인
    assert len(ok) >= 1
    assert ws.control()["seq"] == 9 + len(ok)
    assert not ws.app.state.services.control.lock.locked()
    assert ws.tmp_files() == []
    t0 = time.monotonic()
    assert ws.post(PAUSE).status_code == 200
    assert time.monotonic() - t0 < 1.0


def test_sq19_service_level_seq_distinct_and_contiguous(ws: Ws) -> None:
    """응답 seq 가 아니라 쓰기마다 발급된 seq 를 기록해 연속·고유를 직접 확인."""
    ws.start_loop()
    ws.set_control("running", 9)
    service = ws.app.state.services.control
    issued: list[int] = []
    real_write = service._atomic_write

    def spy(doc: dict[str, Any]) -> None:
        issued.append(doc["seq"])
        real_write(doc)

    service._atomic_write = spy
    barrier = threading.Barrier(50)

    def worker(i: int) -> None:
        barrier.wait()
        try:
            service.pause() if i % 2 else service.resume()
        except control_service.ControlWriteFailed:
            pass

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(50)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert issued == list(range(10, 10 + len(issued)))
    assert ws.control()["seq"] == 9 + len(issued)


def test_sq20_replace_permission_error_retries_then_500(ws: Ws) -> None:
    ws.set_control("running", 9)
    before = (ws.ctl.read_bytes(), ws.ctl.stat().st_mtime_ns)
    service = ws.app.state.services.control
    attempts: list[int] = []
    sleeps: list[float] = []

    def deny(src: str, dst: str) -> None:
        attempts.append(1)
        raise PermissionError(13, f"denied {dst}")

    service.replace, service.sleep = deny, sleeps.append
    resp = ws.post(RESUME)
    body = assert_error(resp, 500, "CONTROL_WRITE_FAILED")
    assert body["error"]["message"] == FIXED_MSG
    assert "denied" not in resp.text and str(ws.root) not in resp.text
    assert len(attempts) == 5 and sleeps == [0.05] * 4
    assert (ws.ctl.read_bytes(), ws.ctl.stat().st_mtime_ns) == before
    assert ws.tmp_files() == []
    service.replace = os.replace
    assert ws.post(RESUME).status_code == 200
    assert ws.control()["seq"] == 10


def test_sq20_other_write_errors_cleanup(
    ws: Ws, monkeypatch: pytest.MonkeyPatch
) -> None:
    ws.set_control("running", 9)
    before = ws.ctl_bytes()

    def boom(fd: int) -> None:
        raise OSError(28, "No space left")

    monkeypatch.setattr(control_service.os, "fsync", boom)
    assert_error(ws.post(RESUME), 500, "CONTROL_WRITE_FAILED")
    assert ws.ctl_bytes() == before and ws.tmp_files() == []


def test_sq21_lock_timeout_2s(ws: Ws) -> None:
    ws.start_loop()
    ws.set_control("running", 9)
    service = ws.app.state.services.control
    assert service.lock_timeout == 2.0
    before_files = sorted(p.name for p in ws.ctl.parent.iterdir())
    before = ws.ctl_bytes()
    service.lock.acquire()
    try:
        t0 = time.monotonic()
        resp = ws.post(PAUSE)
        took = time.monotonic() - t0
    finally:
        service.lock.release()
    body = assert_error(resp, 500, "CONTROL_WRITE_FAILED")
    assert body["error"]["message"] == FIXED_MSG
    assert 1.9 <= took <= 2.5
    assert ws.ctl_bytes() == before
    assert sorted(p.name for p in ws.ctl.parent.iterdir()) == before_files


def test_lock_released_after_exception(ws: Ws) -> None:
    assert_error(ws.post(PAUSE), 409, "NO_ACTIVE_LOOP")
    assert not ws.app.state.services.control.lock.locked()


# ---------------------------------------------------------------- 요청 검증 · 409 · max_pause_sec
@pytest.mark.parametrize(
    "body",
    [
        {"max_pause_sec": 599},
        {"max_pause_sec": 86401},
        {"max_pause_sec": True},
        {"max_pause_sec": 600.0},
        {"max_pause_sec": "600"},
        {"other": 1},
        [],
    ],
)
def test_pause_body_validation_422_no_write(ws: Ws, body: Any) -> None:
    ws.start_loop()
    before = ws.ctl_bytes()
    assert_error(ws.post(PAUSE, body), 422, "VALIDATION_ERROR")
    assert ws.ctl_bytes() == before


def test_resume_rejects_max_pause_sec(ws: Ws) -> None:
    assert_error(ws.post(RESUME, {"max_pause_sec": 600}), 422, "VALIDATION_ERROR")


def test_pause_without_body_uses_default(ws: Ws) -> None:
    ws.start_loop()
    resp = ws.client.post(PAUSE, headers={"content-type": "application/json"})
    assert resp.status_code == 200
    assert ws.control()["max_pause_sec"] == 7200


def test_max_pause_sec_set_and_kept_on_resume(ws: Ws) -> None:
    """AC-15 / §7.1: pause 는 본문 값, resume 은 이전 값 유지, 다음 pause 는 다시 본문(기본 7200)."""
    ws.start_loop()
    data = ws.post(PAUSE, {"max_pause_sec": 600}).json()["data"]
    assert ws.control()["max_pause_sec"] == 600 and data["max_pause_sec"] == 600
    ws.post(RESUME)
    assert ws.control()["max_pause_sec"] == 600
    ws.post(PAUSE)
    assert ws.control()["max_pause_sec"] == 7200
    ws.post(PAUSE, {"max_pause_sec": 86400})
    assert ws.control()["max_pause_sec"] == 86400


@pytest.mark.parametrize("scenario", ["missing", "ended", "broken"])
def test_pause_409_without_active_loop(ws: Ws, scenario: str) -> None:
    """AC-11 / AC-19."""
    if scenario == "ended":
        write_json(ws.status, loop_status_doc("done"))
    elif scenario == "broken":
        ws.status.parent.mkdir(parents=True, exist_ok=True)
        ws.status.write_text('{"schema": 1, "run_id": ', "utf-8")
    body = assert_error(ws.post(PAUSE), 409, "NO_ACTIVE_LOOP")
    assert body["error"]["message"] == "활성 루프가 없습니다."
    assert not ws.ctl.exists()
    assert ws.post(RESUME).status_code == 200  # 멱등 (AC-10)
    assert ws.post(RESUME).status_code == 200
    assert ws.control()["seq"] == (
        8 if scenario == "ended" else 2
    )  # ended 의 baseline 6 이 하한


def test_pause_idempotent_ac10(ws: Ws) -> None:
    ws.start_loop()
    a = ws.post(PAUSE).json()["data"]
    b = ws.post(PAUSE).json()["data"]
    assert (a["state"], b["state"]) == ("pause_requested", "pause_requested")
    assert b["control_seq"] == a["control_seq"] + 1


def test_pause_allowed_while_paused(ws: Ws) -> None:
    write_json(ws.status, loop_status_doc("paused"))
    assert ws.post(PAUSE).status_code == 200


def test_control_directory_not_created(engine_workspace) -> None:
    """쓰기 경로는 `.control.json` 하나 — memory 디렉터리가 없으면 만들지 않고 500."""
    info = engine_workspace("empty")
    client = client_for(info.root)
    assert_error(client.post(RESUME, json={}), 500, "CONTROL_WRITE_FAILED")
    assert not info.memory.exists()


# ---------------------------------------------------------------- GET /control 화면 판정 (V1~V6, D-11)
def _view(
    engine_workspace, status_doc: dict | None, ctl: dict | None, *, now=FIXED_NOW
):
    info = engine_workspace("full")
    if status_doc is not None:
        write_json(info.loop_status_file, status_doc)
    if ctl is not None:
        write_json(info.control_file, ctl)
    client = client_for(info.root, clock=lambda: now)
    resp = client.get(CONTROL)
    assert resp.status_code == 200
    return resp.json()


def test_v1_no_loop_empty(engine_workspace) -> None:
    body = _view(engine_workspace, None, None)
    d = body["data"]
    assert body["meta"]["status"] == "empty"
    assert (d["state"], d["view"], d["label"]) == ("ended", "V1", "루프 없음")
    assert (d["can_pause"], d["can_resume"]) == (False, False)
    assert d["loop_file"] == "missing" and d["control_file"] == "missing"


@pytest.mark.parametrize(
    ("scenario", "message", "hint"),
    [
        ("done", "완료 — 3회 반복을 모두 마쳤습니다", None),
        (
            "pause_timeout",
            "일시정지 상한(2시간) 초과로 종료 — 남은 반복 2회: /aidlc-run 2",
            "`/aidlc-run 2` 로 이어서 실행",
        ),
    ],
)
def test_v1_ended_messages(engine_workspace, scenario, message, hint) -> None:
    body = _view(engine_workspace, loop_status_doc(scenario), None)
    d = body["data"]
    assert body["meta"]["status"] == "ok"
    assert (d["view"], d["label"], d["ended_message"], d["hint"]) == (
        "V1",
        "루프 없음",
        message,
        hint,
    )


@pytest.mark.parametrize(
    ("reason", "message"),
    [
        ("blocked", "막힘으로 종료 — STM 의 blocker 를 확인하세요"),
        ("no_task", "선택 가능한 Task 가 없어 종료"),
    ],
)
def test_v1_other_reasons(engine_workspace, reason, message) -> None:
    doc = loop_status_doc("done") | {"ended_reason": reason}
    assert _view(engine_workspace, doc, None)["data"]["ended_message"] == message


def test_ended_message_hours_formatting() -> None:
    assert "상한(0.17시간)" in control_service.ended_message("pause_timeout", 3, 1, 600)
    assert "상한(24시간)" in control_service.ended_message("pause_timeout", 3, 1, 86400)


def test_v2_pause_requested(engine_workspace) -> None:
    d = _view(engine_workspace, loop_status_doc("running"), control_doc("pause", 7))[
        "data"
    ]
    assert (d["state"], d["label"]) == (
        "pause_requested",
        "일시정지 요청됨 (현재 Task 진행 중)",
    )
    assert (d["can_pause"], d["can_resume"]) == (False, True)
    assert (d["iterations_done"], d["iterations_total"]) == (1, 3)


@pytest.mark.parametrize(
    "ctl", [None, control_doc("running", 7), control_doc("pause", 6)]
)
def test_v3_running(engine_workspace, ctl) -> None:
    """control 없음 / running / baseline 이하의 오래된 pause(AC-12) → 실행 중."""
    d = _view(engine_workspace, loop_status_doc("running"), ctl)["data"]
    assert (d["state"], d["label"]) == ("running", "실행 중")
    assert (d["can_pause"], d["can_resume"]) == (True, False)


def test_v3_running_stale_heartbeat_not_no_session(engine_workspace) -> None:
    """AC-17 / D-11: running 은 heartbeat 가 30분 지나도 실행 중."""
    doc = loop_status_doc("running") | {
        "heartbeat_at": (FIXED_NOW - timedelta(minutes=30)).isoformat()
    }
    d = _view(engine_workspace, doc, None)["data"]
    assert d["state"] == "running" and d["heartbeat_age_sec"] == 1800


def test_v4_paused_with_remaining(engine_workspace) -> None:
    d = _view(engine_workspace, loop_status_doc("paused"), control_doc("pause", 7))[
        "data"
    ]
    assert (d["state"], d["label"]) == ("paused", "일시정지됨 (세션 대기 중)")
    assert d["pause_elapsed_sec"] == 1800
    assert d["remaining_pause_sec"] == 7200 - 1800
    assert (d["can_pause"], d["can_resume"]) == (False, True)


def test_v4_custom_cap(engine_workspace) -> None:
    ctl = control_doc("pause", 7, max_pause_sec=3600)
    d = _view(engine_workspace, loop_status_doc("paused"), ctl)["data"]
    assert (d["max_pause_sec"], d["remaining_pause_sec"]) == (3600, 1800)


def test_v5_resume_requested(engine_workspace) -> None:
    d = _view(engine_workspace, loop_status_doc("paused"), control_doc("running", 8))[
        "data"
    ]
    assert (d["state"], d["label"]) == ("resume_requested", "재개 요청됨")
    assert (d["can_pause"], d["can_resume"]) == (True, False)


@pytest.mark.parametrize(("age", "state"), [(120, "paused"), (121, "no_session")])
def test_v6_heartbeat_boundary(engine_workspace, age: int, state: str) -> None:
    doc = loop_status_doc("paused") | {
        "heartbeat_at": (FIXED_NOW - timedelta(seconds=age)).isoformat()
    }
    d = _view(engine_workspace, doc, control_doc("pause", 7))["data"]
    assert d["state"] == state
    if state == "no_session":
        assert d["label"] == "세션 없음"
        assert (
            d["hint"]
            == "대기하던 세션이 사라졌습니다 — `/aidlc-run 2` 로 다시 실행하세요"
        )
        assert (d["can_pause"], d["can_resume"]) == (False, False)


def test_control_broken_partial_and_unreadable(engine_workspace) -> None:
    info = engine_workspace("full")
    write_json(info.loop_status_file, loop_status_doc("running"))
    info.control_file.write_text("{", "utf-8")
    body = client_for(info.root, clock=lambda: FIXED_NOW).get(CONTROL).json()
    assert body["meta"]["status"] == "partial"
    assert body["data"]["state"] == "running"


def test_broken_workspace_kind(engine_workspace) -> None:
    """qa broken workspace: loop-status 잘림 + 제어 파일 `[]` → error, HTTP 200, 500 없음 (AC-19)."""
    info = engine_workspace("broken")
    client = client_for(info.root)
    body = client.get(CONTROL).json()
    assert body["meta"]["status"] == "error"
    assert body["meta"]["error"]["code"] == "SOURCE_PARSE_ERROR"
    assert body["meta"]["error"]["message"] == "루프 상태를 읽을 수 없음"
    assert body["data"]["can_pause"] is False
    assert_error(client.post(PAUSE, json={}), 409, "NO_ACTIVE_LOOP")


def test_get_control_never_writes(ws: Ws) -> None:
    from fixtures.hashing import hash_tree

    ws.start_loop()
    before = hash_tree(ws.root)
    for _ in range(3):
        assert ws.client.get(CONTROL).status_code == 200
    assert hash_tree(ws.root) == before


def test_end_to_end_cycle_ac1_to_ac5(ws: Ws) -> None:
    """AC-1~AC-5: 1회 완료 후 일시정지·재개, 정확히 3회."""
    ws.set_control("running", 4)
    ws.cli("loop-start", "3")
    cycles = 1
    assert ws.client.get(CONTROL).json()["data"]["state"] == "running"
    ws.post(PAUSE)
    assert ws.client.get(CONTROL).json()["data"]["state"] == "pause_requested"
    assert ws.cli("loop-check", "1").code == 10
    clock = SimClock(now_at=FIXED_NOW)
    ws.restart(clock=lambda: clock.now())

    def on_tick(n: int) -> None:
        if n == 2:
            assert ws.client.get(CONTROL).json()["data"]["state"] == "paused"
            ws.post(RESUME)

    clock.on_tick = on_tick
    assert run_cli(ws.root, "wait-resume", clock=clock).code == 0
    assert ws.client.get(CONTROL).json()["data"]["state"] == "running"
    cycles += 1
    assert ws.cli("loop-check", "2").code == 0
    cycles += 1
    ws.cli("loop-end", "done", "--done", "3")
    d = ws.client.get(CONTROL).json()["data"]
    assert cycles == 3 and d["iterations_done"] == 3 and d["ended_reason"] == "done"
    assert d["ended_message"] == "완료 — 3회 반복을 모두 마쳤습니다"
