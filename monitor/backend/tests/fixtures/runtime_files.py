"""런타임 파일 3종(.control.json, loop-status.json, claude-status.json)의 작성 도우미.

대시보드/CLI/status line 이 실제로 쓰는 파일을 흉내 낸다. 모든 빌더는 계약 스키마
(contracts/*.schema.json)를 통과하는 dict 를 돌려주고, 시나리오 이름으로 FR-005 상태를 만든다.
시각은 `FIXED_NOW` 기준이라 시계 의존이 없다.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path

from .jsonl_gen import FIXED_NOW

PAUSE_LIMIT_SEC = 7200  # control.schema max_pause_sec 기본값
HEARTBEAT_EXPIRY_SEC = 120  # QS-11: 만료 감지 <= 2분


def iso(ts: datetime) -> str:
    """RFC 3339 UTC, 초 단위, `+00:00` (contracts/README §2)."""
    return ts.replace(microsecond=0).isoformat()


def write_json(path: Path, obj: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2), encoding="utf-8")
    return path


# ---- .control.json ---------------------------------------------------------
def control_doc(
    state: str = "running", seq: int = 1, *, now: datetime = FIXED_NOW, max_pause_sec: int = PAUSE_LIMIT_SEC
) -> dict:
    return {"schema": 1, "seq": seq, "state": state, "requested_at": iso(now), "max_pause_sec": max_pause_sec}


# ---- loop-status.json ------------------------------------------------------
RUN_ID = "3f2b9c1e8a7d4e6f9b0c1d2e3f4a5b6c"


def loop_status_doc(scenario: str, *, now: datetime = FIXED_NOW) -> dict:
    """FR-005 시나리오별 loop-status.

    running           사이클 실행 중, heartbeat 신선
    paused            일시정지 30분째 (한도 7200 s 이내)
    resumed           재개 직후: paused_since 가 null 로 돌아온 running
    pause_over_limit  일시정지 2시간 초과(아직 state=paused, 다음 wait-resume 이 종료시킬 상태)
    pause_timeout     2시간 초과로 정상 종료 (ended / pause_timeout, paused_since 유지)
    done              모든 반복 완료
    heartbeat_expired running 으로 남아 있지만 heartbeat 가 만료 한도를 넘음(세션 사라짐)
    """
    base = {
        "schema": 1,
        "run_id": RUN_ID,
        "state": "running",
        "baseline_seq": 6,
        "iterations_total": 3,
        "iterations_done": 1,
        "started_at": iso(now - timedelta(hours=3)),
        "heartbeat_at": iso(now - timedelta(seconds=10)),
        "paused_since": None,
        "ended_reason": None,
    }
    if scenario == "running":
        return base
    if scenario == "paused":
        return base | {"state": "paused", "paused_since": iso(now - timedelta(minutes=30))}
    if scenario == "resumed":
        return base | {"iterations_done": 2}
    if scenario == "pause_over_limit":
        since = now - timedelta(seconds=PAUSE_LIMIT_SEC + 60)
        return base | {"state": "paused", "paused_since": iso(since)}
    if scenario == "pause_timeout":
        since = now - timedelta(seconds=PAUSE_LIMIT_SEC + 60)
        return base | {"state": "ended", "ended_reason": "pause_timeout", "paused_since": iso(since)}
    if scenario == "done":
        return base | {"state": "ended", "ended_reason": "done", "iterations_done": 3}
    if scenario == "heartbeat_expired":
        return base | {"heartbeat_at": iso(now - timedelta(seconds=HEARTBEAT_EXPIRY_SEC + 60))}
    raise ValueError(f"unknown loop scenario: {scenario!r}")


LOOP_SCENARIOS = (
    "running",
    "paused",
    "resumed",
    "pause_over_limit",
    "pause_timeout",
    "done",
    "heartbeat_expired",
)


# ---- claude-status.json ----------------------------------------------------
def session_hash(session_id: str) -> str:
    """스냅샷에는 원문 session_id 대신 sha256 앞 12자만 저장한다 (ADR-003)."""
    return hashlib.sha256(session_id.encode()).hexdigest()[:12]


SNAPSHOT_KINDS = ("normal", "no_rate_limits", "none", "stale", "broken")
STALE_AFTER_SEC = 600  # captured_at 이 10분보다 오래되면 SNAPSHOT_STALE


def claude_status_doc(
    kind: str = "normal", *, now: datetime = FIXED_NOW, transcript_dir_name: str | None = None
) -> dict | None:
    """status line 스냅샷 dict. `none`/`broken` 은 파일 자체가 없거나 깨진 경우라 None."""
    if kind in ("none", "broken"):
        return None
    captured = now - timedelta(seconds=STALE_AFTER_SEC + 1200 if kind == "stale" else 5)
    doc = {
        "schema": 1,
        "captured_at": iso(captured),
        "claude_version": "0.0.0-fake",
        "model_id": "claude-fake-opus",
        "session_hash": session_hash("fake-session"),
        "transcript_dir_name": transcript_dir_name,
        "rate_limits": {
            "five_hour": {"used_percentage": 23.5, "resets_at": int((now + timedelta(hours=2)).timestamp())},
            "seven_day": {"used_percentage": 41, "resets_at": int((now + timedelta(days=3)).timestamp())},
        },
        "cost": {"total_cost_usd": 0.12, "total_duration_ms": 345000},
        "context_window": {"used_percentage": 8, "context_window_size": 200000},
    }
    if kind == "no_rate_limits":  # 비구독 / 첫 응답 전
        doc["rate_limits"] = None
    return doc


def write_claude_status(path: Path, kind: str = "normal", **kwargs: object) -> Path:
    """스냅샷 fixture 를 쓴다. `none` 은 파일을 만들지 않고, `broken` 은 잘린 JSON 을 쓴다."""
    if kind not in SNAPSHOT_KINDS:
        raise ValueError(f"unknown snapshot kind: {kind!r} (expected one of {SNAPSHOT_KINDS})")
    doc = claude_status_doc(kind, **kwargs)  # type: ignore[arg-type]
    if kind == "broken":
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{"schema": 1, "captured_at": "2026-10-23T08:5', encoding="utf-8")
    elif doc is not None:
        write_json(path, doc)
    return path


# transcript_dir_name 재검증 입력 (privacy.md P-26, contracts/README §3)
VALID_DIR_NAMES = ("-home-user-chatbot", "a", "a.b_c-d", "..a", "a..", "A" * 255)
INVALID_DIR_NAMES = (
    "..",
    ".",
    "a/b",
    "a\\b",
    "/abs",
    "C:x",
    "",
    "A" * 256,
    "name\n",  # 끝 개행 (Python `$` 함정)
    "a\x00b",
    "a\x01b",
    " lead",
    "trail ",
)
