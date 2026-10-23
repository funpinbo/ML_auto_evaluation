"""루프 제어 서비스 — `.control.json` 쓰기(대시보드의 유일한 쓰기)와 화면 상태 판정 (FR-005, ADR-004).

- 판독 규칙·엄격 정수 술어(loop-cli §2.1)는 CLI(`aidlc/scripts/loop_control.py`)와 **같은 술어**다.
  CLI 는 표준 라이브러리 단독 스크립트이고 대시보드는 다른 저장소(`AIDLC_ROOT`)를 볼 수 있어 import 를
  공유하지 않는다. 대신 backend 테스트(`test_loop_strict_parity.py`)가 같은 입력에 대해 두 구현의
  판정이 같은지 교차 검증한다 — 한쪽을 고치면 다른 쪽도 고친다.
- seq 발급(§7.1, D-39): `next = max(prev, baseline) + 1`, 두 파일을 매번 새로 읽는다(캐시 없음).
- 쓰기(§7.3, D-40): 프로세스 락 1개(획득 타임아웃 2 s) 안에서 "두 파일 읽기 → 계산 → 임시 파일 →
  os.replace(PermissionError 재시도 5×50 ms)" 만 한다. 실패 시 임시 파일은 finally 에서 지운다.
- `loop-status.json` 은 읽기만 한다(R-10). 디렉터리를 만들지 않는다(쓰기 경로 = `.control.json` 하나).
- 프레임워크(FastAPI)에 의존하지 않는다. 요청 오류는 도메인 예외로 올리고 라우터가 HTTP 로 바꾼다.
"""

from __future__ import annotations

import json
import logging
import os
import re
import tempfile
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from app.models.control import ControlData, ScreenState, ViewId
from app.models.envelope import SourceErrorCode
from app.services.panel import Panel

log = logging.getLogger("aidlc_monitor.control")

# ------------------------------------------------------------------ 계약 상수 (loop-cli.md, 스키마 2종)
SEQ_MAX = 9007199254740991  # 2^53 - 1
MAX_PAUSE_MIN, MAX_PAUSE_MAX, MAX_PAUSE_DEFAULT = 600, 86400, 7200
ITER_MAX = 10
HEARTBEAT_STALE_SEC = 120  # paused 에서만 적용 (D-11, QS-11)
READ_LIMIT = 64 * 1024
INT_DIGITS_MAX = 16
LOCK_TIMEOUT_SEC = 2.0
REPLACE_TRIES, REPLACE_GAP_SEC = 5, 0.05
END_REASONS = ("done", "blocked", "no_task", "pause_timeout")

_TS_RE = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?(Z|[+-][0-9]{2}:[0-9]{2})"
)
_RUN_ID_RE = re.compile(r"[0-9a-f]{32}")
CONTROL_KEYS = frozenset({"schema", "seq", "state", "requested_at", "max_pause_sec"})
STATUS_KEYS = frozenset(
    {
        "schema",
        "run_id",
        "state",
        "baseline_seq",
        "iterations_total",
        "iterations_done",
        "started_at",
        "heartbeat_at",
        "paused_since",
        "ended_reason",
    }
)

# ------------------------------------------------------------------ 화면 문구 (stories/FR-005 §2.1·§2.3, D-22)
LABELS: dict[str, str] = {
    "V1": "루프 없음",
    "V2": "일시정지 요청됨 (현재 Task 진행 중)",
    "V3": "실행 중",
    "V4": "일시정지됨 (세션 대기 중)",
    "V5": "재개 요청됨",
    "V6": "세션 없음",
}
MSG_CONTROL_BROKEN = "제어 파일을 읽을 수 없음 — 일시정지를 다시 누르면 새로 씁니다"
MSG_LOOP_BROKEN = "루프 상태를 읽을 수 없음"
MSG_NO_LOOP = "실행 중인 루프가 없습니다"


def ended_message(
    reason: str | None, total: int, remaining: int, max_pause: int
) -> str | None:
    if reason == "done":
        return f"완료 — {total}회 반복을 모두 마쳤습니다"
    if reason == "blocked":
        return "막힘으로 종료 — STM 의 blocker 를 확인하세요"
    if reason == "no_task":
        return "선택 가능한 Task 가 없어 종료"
    if reason == "pause_timeout":
        hours = f"{round(max_pause / 3600, 2):g}"
        return (
            f"일시정지 상한({hours}시간) 초과로 종료 — 남은 반복 {remaining}회: "
            f"/aidlc-run {remaining}"
        )
    return None


# ------------------------------------------------------------------ 엄격 판독 (CLI 와 같은 술어)
def is_strict_int(x: object, lo: int, hi: int) -> bool:
    """JSON 정수 리터럴만: bool(int 하위형)·float(7.0, 7e0) 거부, 범위 포함."""
    return type(x) is int and lo <= x <= hi


class _Rejected(ValueError):
    pass


def _parse_int(text: str) -> int:
    if len(text.lstrip("-")) > INT_DIGITS_MAX:
        raise _Rejected("integer literal too long")
    return int(text)


def _parse_constant(text: str) -> Any:
    raise _Rejected("non-finite number")


def loads_strict(raw: bytes) -> Any:
    """UTF-8(BOM 없음) JSON. 어떤 손상 입력도 ValueError 하나로 끝난다(500 고착 방지)."""
    try:
        text = raw.decode("utf-8")
        return json.loads(text, parse_int=_parse_int, parse_constant=_parse_constant)
    except (UnicodeDecodeError, RecursionError) as exc:
        raise _Rejected(type(exc).__name__) from None


def parse_ts(value: object) -> datetime | None:
    if type(value) is not str or not _TS_RE.fullmatch(value):
        return None
    try:
        ts = datetime.fromisoformat(value)
    except ValueError:
        return None
    return ts if ts.tzinfo is not None else None


def valid_control(doc: object) -> bool:
    """control.schema.json + 엄격 정수 판정."""
    return (
        type(doc) is dict
        and set(doc) == CONTROL_KEYS
        and is_strict_int(doc["schema"], 1, 1)
        and is_strict_int(doc["seq"], 1, SEQ_MAX)
        and type(doc["state"]) is str
        and doc["state"] in ("running", "pause")
        and parse_ts(doc["requested_at"]) is not None
        and is_strict_int(doc["max_pause_sec"], MAX_PAUSE_MIN, MAX_PAUSE_MAX)
    )


def valid_loop_status(doc: object) -> bool:
    """loop-status.schema.json(조건부 규칙 포함) + 엄격 정수 + done <= total."""
    if type(doc) is not dict or set(doc) != STATUS_KEYS:
        return False
    state, reason, since = doc["state"], doc["ended_reason"], doc["paused_since"]
    if not (
        is_strict_int(doc["schema"], 1, 1)
        and type(doc["run_id"]) is str
        and _RUN_ID_RE.fullmatch(doc["run_id"]) is not None
        and type(state) is str
        and state in ("running", "paused", "ended")
        and is_strict_int(doc["baseline_seq"], 0, SEQ_MAX)
        and is_strict_int(doc["iterations_total"], 1, ITER_MAX)
        and is_strict_int(doc["iterations_done"], 0, ITER_MAX)
        and doc["iterations_done"] <= doc["iterations_total"]
        and parse_ts(doc["started_at"]) is not None
        and parse_ts(doc["heartbeat_at"]) is not None
        and (since is None or parse_ts(since) is not None)
        and (reason is None or (type(reason) is str and reason in END_REASONS))
    ):
        return False
    if (state == "ended") != (reason is not None):
        return False
    if state == "paused" and since is None:
        return False
    if state == "running" and since is not None:
        return False
    return not (reason == "pause_timeout" and since is None)


FileStatus = Literal["ok", "missing", "broken", "unreadable"]


@dataclass(frozen=True)
class ControlFile:
    status: FileStatus
    seq: int = 0
    state: str = "running"
    max_pause_sec: int = MAX_PAUSE_DEFAULT
    requested_at: str | None = None

    @property
    def ok(self) -> bool:
        return self.status == "ok"


@dataclass(frozen=True)
class LoopFile:
    status: FileStatus
    doc: dict[str, Any] | None = None

    @property
    def active(self) -> bool:
        return self.doc is not None and self.doc["state"] in ("running", "paused")

    @property
    def baseline(self) -> int:
        return self.doc["baseline_seq"] if self.doc is not None else 0


def _read_raw(path: Path) -> bytes | None:
    """없으면 None. 크기 초과는 손상(ValueError), 그 밖의 OS 오류는 그대로 올린다."""
    try:
        with open(path, "rb") as fh:
            raw = fh.read(READ_LIMIT + 1)
    except FileNotFoundError:
        return None
    if len(raw) > READ_LIMIT:
        raise _Rejected("file too large")
    return raw


def read_control(path: Path) -> ControlFile:
    try:
        raw = _read_raw(path)
    except ValueError:
        return ControlFile("broken")
    except OSError:
        return ControlFile("unreadable")
    if raw is None:
        return ControlFile("missing")
    try:
        doc = loads_strict(raw)
    except ValueError:
        return ControlFile("broken")
    if not valid_control(doc):
        return ControlFile("broken")
    return ControlFile(
        "ok", doc["seq"], doc["state"], doc["max_pause_sec"], doc["requested_at"]
    )


def read_loop_status(path: Path) -> LoopFile:
    try:
        raw = _read_raw(path)
    except ValueError:
        return LoopFile("broken")
    except OSError:
        return LoopFile("unreadable")
    if raw is None:
        return LoopFile("missing")
    try:
        doc = loads_strict(raw)
    except ValueError:
        return LoopFile("broken")
    return LoopFile("ok", doc) if valid_loop_status(doc) else LoopFile("broken")


# ------------------------------------------------------------------ 도메인 예외 (라우터가 HTTP 로 바꾼다)
class NoActiveLoop(Exception):
    """pause 요청인데 loop-status 가 running/paused 가 아니다 → 409 NO_ACTIVE_LOOP."""


class ControlWriteFailed(Exception):
    """락 타임아웃·seq 상한·파일 쓰기 실패 → 500 CONTROL_WRITE_FAILED (고정 문구)."""


# ------------------------------------------------------------------ 서비스
_STATE_TO_VIEW: dict[str, ViewId] = {
    "running": "V3",
    "pause_requested": "V2",
    "paused": "V4",
    "resume_requested": "V5",
    "no_session": "V6",
    "ended": "V1",
}


class ControlService:
    def __init__(
        self,
        root: Path,
        clock: Callable[[], datetime],
        *,
        lock_timeout: float = LOCK_TIMEOUT_SEC,
        replace: Callable[[str, str], None] = os.replace,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.root = root
        self.clock = clock
        self.lock = threading.Lock()
        self.lock_timeout = lock_timeout
        self.replace = replace
        self.sleep = sleep

    @property
    def memory_dir(self) -> Path:
        return self.root / "workspace" / "memory"

    @property
    def control_path(self) -> Path:
        return self.memory_dir / ".control.json"

    @property
    def status_path(self) -> Path:
        return self.memory_dir / ".monitor" / "loop-status.json"

    # -------------------------------------------------------------- 읽기 (GET /control)
    def read(self) -> Panel:
        panel = Panel()
        ctl = read_control(self.control_path)
        loop = read_loop_status(self.status_path)
        panel.touch(self.control_path, self.status_path)
        now = self.clock()
        panel.data = build_view(ctl, loop, now)
        if loop.status == "broken":
            panel.fail(SourceErrorCode.SOURCE_PARSE_ERROR, MSG_LOOP_BROKEN)
        elif loop.status == "unreadable":
            panel.fail(SourceErrorCode.SOURCE_UNREADABLE, MSG_LOOP_BROKEN)
        elif loop.status == "missing":
            panel.empty(MSG_NO_LOOP)
        if ctl.status in ("broken", "unreadable"):
            panel.warn(MSG_CONTROL_BROKEN)
        return panel

    # -------------------------------------------------------------- 쓰기 (POST /control/pause|resume)
    def pause(self, max_pause_sec: int | None = None) -> Panel:
        self._write("pause", max_pause_sec)
        return self.read()

    def resume(self) -> Panel:
        self._write("running", None)
        return self.read()

    def _write(self, state: str, max_pause_sec: int | None) -> None:
        if not self.lock.acquire(timeout=self.lock_timeout):
            log.error("제어 파일 쓰기 실패: %s", "LockTimeout")
            raise ControlWriteFailed
        try:
            ctl = read_control(self.control_path)
            loop = read_loop_status(self.status_path)
            if state == "pause" and not loop.active:
                raise NoActiveLoop
            prev = ctl.seq if ctl.ok else 0
            next_seq = max(prev, loop.baseline) + 1
            if next_seq > SEQ_MAX:
                log.error("제어 파일 쓰기 실패: %s", "SeqOverflow")
                raise ControlWriteFailed
            if state == "pause":
                limit = MAX_PAUSE_DEFAULT if max_pause_sec is None else max_pause_sec
            else:
                limit = ctl.max_pause_sec if ctl.ok else MAX_PAUSE_DEFAULT
            doc = {
                "schema": 1,
                "seq": next_seq,
                "state": state,
                "requested_at": self.clock()
                .astimezone(UTC)
                .replace(microsecond=0)
                .isoformat(),
                "max_pause_sec": limit,
            }
            if not valid_control(
                doc
            ):  # 작성자 검증 (범위 밖 max_pause_sec 등 — 라우터가 먼저 막는다)
                raise ControlWriteFailed
            self._atomic_write(doc)
        finally:
            self.lock.release()

    def _atomic_write(self, doc: dict[str, Any]) -> None:
        payload = json.dumps(doc, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
        tmp: str | None = None
        try:
            fd, tmp_name = tempfile.mkstemp(
                prefix=".control.json.", suffix=".tmp", dir=self.memory_dir
            )
            tmp = tmp_name
            with os.fdopen(fd, "wb") as fh:
                fh.write(payload)
                fh.flush()
                os.fsync(fh.fileno())
            for attempt in range(REPLACE_TRIES):
                try:
                    self.replace(tmp_name, str(self.control_path))
                    tmp = None
                    return
                except PermissionError:
                    if attempt == REPLACE_TRIES - 1:
                        raise
                    self.sleep(REPLACE_GAP_SEC)
        except OSError as exc:
            log.error("제어 파일 쓰기 실패: %s", type(exc).__name__)
            raise ControlWriteFailed from None
        finally:
            if tmp is not None:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass


def _age(now: datetime, ts: str | None) -> int | None:
    parsed = parse_ts(ts)
    if parsed is None:
        return None
    return max(0, int((now - parsed).total_seconds()))


def screen_state(ctl: ControlFile, loop: LoopFile, now: datetime) -> ScreenState:
    """ADR-004 §4 표. control 은 seq > baseline 인 최신 요청만 본다. heartbeat 는 paused 에서만(D-11)."""
    doc = loop.doc
    if doc is None or doc["state"] == "ended":
        return "ended"
    request = ctl.state if ctl.ok and ctl.seq > doc["baseline_seq"] else None
    if doc["state"] == "running":
        return "pause_requested" if request == "pause" else "running"
    age = _age(now, doc["heartbeat_at"])
    if age is not None and age > HEARTBEAT_STALE_SEC:
        return "no_session"
    return "resume_requested" if request == "running" else "paused"


_BUTTONS: dict[str, tuple[bool, bool]] = {
    "V1": (False, False),
    "V2": (False, True),
    "V3": (True, False),
    "V4": (False, True),
    "V5": (True, False),
    "V6": (False, False),
}


def build_view(ctl: ControlFile, loop: LoopFile, now: datetime) -> ControlData:
    state = screen_state(ctl, loop, now)
    view = _STATE_TO_VIEW[state]
    can_pause, can_resume = _BUTTONS[view]
    doc = loop.doc
    limit = ctl.max_pause_sec if ctl.ok else MAX_PAUSE_DEFAULT
    total: int | None = doc["iterations_total"] if doc else None
    done: int | None = doc["iterations_done"] if doc else None
    remaining = total - done if total is not None and done is not None else None
    paused_since = doc["paused_since"] if doc else None
    elapsed = _age(now, paused_since) if doc and doc["state"] == "paused" else None
    hint: str | None = None
    if view == "V6" and remaining is not None:
        hint = f"대기하던 세션이 사라졌습니다 — `/aidlc-run {remaining}` 로 다시 실행하세요"
    elif view == "V1" and remaining:
        hint = f"`/aidlc-run {remaining}` 로 이어서 실행"
    reason = doc["ended_reason"] if doc else None
    return ControlData(
        state=state,
        view=view,
        label=LABELS[view],
        hint=hint,
        can_pause=can_pause,
        can_resume=can_resume,
        requested_state=("pause" if ctl.state == "pause" else "running")
        if ctl.ok
        else None,
        requested_at=ctl.requested_at if ctl.ok else None,
        control_seq=ctl.seq if ctl.ok else None,
        baseline_seq=doc["baseline_seq"] if doc else None,
        control_file=ctl.status,
        loop_file=loop.status,
        loop_state=doc["state"] if doc else None,
        paused_since=paused_since,
        heartbeat_at=doc["heartbeat_at"] if doc else None,
        heartbeat_age_sec=_age(now, doc["heartbeat_at"]) if doc else None,
        iterations_done=done,
        iterations_total=total,
        remaining_iterations=remaining,
        max_pause_sec=limit,
        pause_elapsed_sec=elapsed,
        remaining_pause_sec=max(0, limit - elapsed) if elapsed is not None else None,
        ended_reason=reason,
        ended_message=ended_message(reason, total or 0, remaining or 0, limit)
        if view == "V1"
        else None,
    )
