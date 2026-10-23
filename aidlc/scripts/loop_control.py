"""루프 제어 CLI — `aidlc.py loop-start / loop-check / wait-resume / loop-end` (ADR-004, contracts/loop-cli.md).

계약 요약 (변경은 architecture 리뷰 + ADR-004 갱신):
- 표준 라이브러리만 쓴다. 파일 경로는 이 스크립트 위치 기준 저장소 루트에서 계산한다(환경 변수·cwd 비의존).
- 쓰는 파일은 `workspace/memory/.monitor/loop-status.json` 하나(임시 파일 → os.replace).
  `workspace/memory/.control.json` 은 읽기만 한다(R-10, 단일 작성자).
- exit code: 0 정상/재개, 10 일시정지(대기 계속), 20 일시정지 상한 초과, 2 제어 파일 broken(계속 진행),
  64 사용법 오류, 1 예기치 못한 예외. stdout 은 `AIDLC-LOOP <sub> <RESULT> k=v ...` 한 줄뿐,
  경고·진단은 stderr. 어디에도 파일 경로·내용을 쓰지 않는다(02 §7).
- 엄격 정수 판정(§2.1)은 대시보드(`monitor/backend/app/services/control.py`)와 같은 술어다.
  두 구현이 같은 판정을 내는지는 backend 테스트(test_loop_strict_parity.py)가 교차 검증한다.
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

EXIT_OK = 0
EXIT_PAUSED = 10
EXIT_PAUSE_TIMEOUT = 20
EXIT_CONTROL_BROKEN = 2
EXIT_USAGE = 64
EXIT_UNEXPECTED = 1

SEQ_MAX = 9007199254740991  # 2^53 - 1
MAX_PAUSE_MIN, MAX_PAUSE_MAX, MAX_PAUSE_DEFAULT = 600, 86400, 7200
ITER_MAX = 10
MAX_WAIT_MIN, MAX_WAIT_MAX, MAX_WAIT_DEFAULT = 1, 580, 540
HEARTBEAT_SEC = 30
TICK_SEC = 1.0
READ_LIMIT = 64 * 1024  # 정상 파일은 수백 바이트 — 이보다 크면 손상으로 본다
INT_DIGITS_MAX = 16  # SEQ_MAX 는 16자리 — 더 긴 리터럴은 int 변환 전에 거부(4300자리 ValueError 회피)
REPLACE_TRIES, REPLACE_GAP_SEC = 5, 0.05
END_REASONS = ("done", "blocked", "no_task")

_TS_RE = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?(Z|[+-][0-9]{2}:[0-9]{2})"
)
_RUN_ID_RE = re.compile(r"[0-9a-f]{32}")
_DEC_RE = re.compile(r"[0-9]{1,6}")
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


# ------------------------------------------------------------------ 엄격 판독 (§2.1, 대시보드와 같은 술어)
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
    """UTF-8(BOM 없음) JSON. 실패는 ValueError 하나로 모은다(밖으로 다른 예외가 나가지 않게)."""
    try:
        text = raw.decode("utf-8")
        return json.loads(text, parse_int=_parse_int, parse_constant=_parse_constant)
    except (UnicodeDecodeError, RecursionError) as exc:
        raise _Rejected(type(exc).__name__) from None


def parse_ts(value: object) -> datetime | None:
    """계약 패턴(RFC 3339, 오프셋 필수)에 맞고 실제 날짜로 해석될 때만 aware datetime."""
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
        and doc["state"] in ("running", "pause")
        and type(doc["state"]) is str
        and parse_ts(doc["requested_at"]) is not None
        and is_strict_int(doc["max_pause_sec"], MAX_PAUSE_MIN, MAX_PAUSE_MAX)
    )


def valid_loop_status(doc: object) -> bool:
    """loop-status.schema.json(조건부 규칙 포함) + 엄격 정수 + done <= total 불변식."""
    if type(doc) is not dict or set(doc) != STATUS_KEYS:
        return False
    state, reason, since = doc["state"], doc["ended_reason"], doc["paused_since"]
    base_ok = (
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
        and (
            reason is None
            or (type(reason) is str and reason in (*END_REASONS, "pause_timeout"))
        )
    )
    if not base_ok:
        return False
    if state == "ended" and reason is None:
        return False
    if state != "ended" and reason is not None:
        return False
    if state == "paused" and since is None:
        return False
    if state == "running" and since is not None:
        return False
    return not (reason == "pause_timeout" and since is None)


@dataclass
class Control:
    status: str  # ok | missing | broken
    seq: int = 0
    state: str = "running"
    max_pause_sec: int = MAX_PAUSE_DEFAULT


def _read_bytes(path: Path) -> bytes:
    with open(path, "rb") as fh:
        raw = fh.read(READ_LIMIT + 1)
    if len(raw) > READ_LIMIT:
        raise _Rejected("file too large")
    return raw


def read_control(path: Path) -> Control:
    """§2.1 판독 규칙. 없음 = seq 0 running(정상), 그 밖의 실패 = broken."""
    try:
        raw = _read_bytes(path)
    except FileNotFoundError:
        return Control("missing")
    except (OSError, ValueError):
        return Control("broken")
    try:
        doc = loads_strict(raw)
    except ValueError:
        return Control("broken")
    if not valid_control(doc):
        return Control("broken")
    return Control("ok", doc["seq"], doc["state"], doc["max_pause_sec"])


def read_loop_status(path: Path) -> dict[str, Any] | None:
    """계약에 맞는 loop-status 만 돌려준다. 없음·깨짐·위반은 None(= 활성 루프 없음)."""
    try:
        doc = loads_strict(_read_bytes(path))
    except (OSError, ValueError):
        return None
    return doc if valid_loop_status(doc) else None


# ------------------------------------------------------------------ 실행 문맥
@dataclass
class Env:
    root: Path = ROOT
    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))
    monotonic: Callable[[], float] = time.monotonic
    sleep: Callable[[float], None] = time.sleep
    replace: Callable[[str, str], None] = os.replace
    out: Any = None
    err: Any = None

    @property
    def control_path(self) -> Path:
        return self.root / "workspace" / "memory" / ".control.json"

    @property
    def status_path(self) -> Path:
        return self.root / "workspace" / "memory" / ".monitor" / "loop-status.json"

    def stdout(self, sub: str, result: str, **keys: object) -> None:
        stream = self.out or sys.stdout
        tail = " ".join(f"{k}={v}" for k, v in keys.items())
        stream.write(f"AIDLC-LOOP {sub} {result}{' ' + tail if tail else ''}\n")
        stream.flush()

    def warn(self, message: str) -> None:
        stream = self.err or sys.stderr
        stream.write(f"aidlc-loop: {message}\n")
        stream.flush()


def iso(ts: datetime) -> str:
    return ts.astimezone(UTC).replace(microsecond=0).isoformat()


def write_status(env: Env, doc: dict[str, Any]) -> bool:
    """원자적 쓰기. 실패는 stderr 경고만(exit code 불변, §2). 계약 위반 문서는 버그 → 예외."""
    if not valid_loop_status(doc):
        raise AssertionError("refusing to write invalid loop-status")
    target = env.status_path
    tmp: str | None = None
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            prefix=".loop-status.json.", suffix=".tmp", dir=target.parent
        )
        tmp = tmp_name
        with os.fdopen(fd, "wb") as fh:
            fh.write(
                json.dumps(doc, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
            )
            fh.flush()
            os.fsync(fh.fileno())
        for attempt in range(REPLACE_TRIES):
            try:
                env.replace(tmp_name, str(target))
                tmp = None
                break
            except PermissionError:
                if attempt == REPLACE_TRIES - 1:
                    raise
                env.sleep(REPLACE_GAP_SEC)
        return True
    except OSError as exc:
        env.warn(
            f"warning: could not write loop status ({type(exc).__name__}); continuing"
        )
        return False
    finally:
        if tmp is not None:
            try:
                os.unlink(tmp)
            except OSError:
                pass


# ------------------------------------------------------------------ 인자 파싱 (usage 오류 = 64)
class UsageError(Exception):
    pass


USAGE = (
    "usage: aidlc.py loop-start <N 1..10> | loop-check <done 0..N> | "
    "wait-resume [--max-wait <1..580>] | loop-end <done|blocked|no_task> [--done <n>]"
)


def _int_arg(text: str, lo: int, hi: int) -> int:
    if not _DEC_RE.fullmatch(text):
        raise UsageError("not a decimal integer")
    value = int(text)
    if not lo <= value <= hi:
        raise UsageError("out of range")
    return value


def _split_option(args: list[str], name: str) -> tuple[list[str], str | None]:
    """`--name v` / `--name=v` 를 한 번만 허용. 나머지 위치 인자를 돌려준다."""
    rest: list[str] = []
    value: str | None = None
    seen = False
    i = 0
    while i < len(args):
        a = args[i]
        if a == name or a.startswith(name + "="):
            if seen:
                raise UsageError("option repeated")
            seen = True
            if a == name:
                if i + 1 >= len(args):
                    raise UsageError("option needs a value")
                value = args[i + 1]
                i += 2
                continue
            value = a[len(name) + 1 :]
        elif a.startswith("-"):
            raise UsageError("unknown option")
        else:
            rest.append(a)
        i += 1
    return rest, value


def _progress(doc: dict[str, Any] | None, done: int | None = None) -> str:
    if doc is None:
        return f"{'-' if done is None else done}/-"
    return (
        f"{doc['iterations_done'] if done is None else done}/{doc['iterations_total']}"
    )


def _active(doc: dict[str, Any] | None) -> bool:
    return doc is not None and doc["state"] in ("running", "paused")


# ------------------------------------------------------------------ 서브커맨드
def cmd_loop_start(env: Env, args: list[str]) -> int:
    if len(args) != 1:
        raise UsageError("loop-start takes exactly one argument")
    total = _int_arg(args[0], 1, ITER_MAX)
    ctl = read_control(env.control_path)
    baseline = ctl.seq if ctl.status == "ok" else 0
    now = iso(env.now())
    run_id = uuid.uuid4().hex
    write_status(
        env,
        {
            "schema": 1,
            "run_id": run_id,
            "state": "running",
            "baseline_seq": baseline,
            "iterations_total": total,
            "iterations_done": 0,
            "started_at": now,
            "heartbeat_at": now,
            "paused_since": None,
            "ended_reason": None,
        },
    )
    keys = {"run": run_id[:8], "total": total, "baseline": baseline}
    if ctl.status == "broken":
        env.warn("warning: control file is broken - baseline 0, continuing")
        env.stdout("loop-start", "CONTROL_BROKEN", **keys)
        return EXIT_CONTROL_BROKEN
    env.stdout("loop-start", "STARTED", **keys)
    return EXIT_OK


def cmd_loop_check(env: Env, args: list[str]) -> int:
    if len(args) != 1:
        raise UsageError("loop-check takes exactly one argument")
    done = _int_arg(args[0], 0, ITER_MAX)
    doc = read_loop_status(env.status_path)
    if not _active(doc):
        env.warn(
            "warning: no active loop (loop status missing, broken or ended); nothing written"
        )
        env.stdout(
            "loop-check", "NO_LOOP", done=_progress(None, done), seq="-", baseline="-"
        )
        return EXIT_OK
    assert doc is not None
    if done > doc["iterations_total"]:
        raise UsageError("done exceeds total")
    ctl = read_control(env.control_path)
    doc.update(
        iterations_done=done,
        heartbeat_at=iso(env.now()),
        state="running",
        paused_since=None,
    )
    write_status(env, doc)
    keys = {
        "done": _progress(doc),
        "seq": ctl.seq if ctl.status != "broken" else "-",
        "baseline": doc["baseline_seq"],
    }
    if ctl.status == "broken":
        env.warn("warning: control file is broken - not pausing, continuing")
        env.stdout("loop-check", "CONTROL_BROKEN", **keys)
        return EXIT_CONTROL_BROKEN
    if ctl.seq > doc["baseline_seq"] and ctl.state == "pause":
        env.stdout("loop-check", "PAUSE", **keys)
        return EXIT_PAUSED
    env.stdout("loop-check", "CONTINUE", **keys)
    return EXIT_OK


def cmd_wait_resume(env: Env, args: list[str]) -> int:
    rest, raw = _split_option(args, "--max-wait")
    if rest:
        raise UsageError("wait-resume takes no positional arguments")
    max_wait = (
        MAX_WAIT_DEFAULT if raw is None else _int_arg(raw, MAX_WAIT_MIN, MAX_WAIT_MAX)
    )
    doc = read_loop_status(env.status_path)
    if not _active(doc):
        env.warn(
            "warning: no active loop (loop status missing, broken or ended); nothing to wait for"
        )
        env.stdout(
            "wait-resume",
            "NO_LOOP",
            paused_sec=0,
            remaining_sec=0,
            done=_progress(None),
        )
        return EXIT_OK
    assert doc is not None
    now = env.now()
    since_text = doc["paused_since"] or iso(now)
    since = parse_ts(since_text)
    assert since is not None
    doc.update(state="paused", paused_since=since_text, heartbeat_at=iso(now))
    write_status(env, doc)
    started = env.monotonic()
    last_beat = started
    baseline = doc["baseline_seq"]

    def keys(at: datetime, limit: int) -> dict[str, object]:
        elapsed = max(0, int((at - since).total_seconds()))
        return {
            "paused_sec": elapsed,
            "remaining_sec": max(0, limit - elapsed),
            "done": _progress(doc),
        }

    while True:
        ctl = read_control(env.control_path)
        now = env.now()
        limit = ctl.max_pause_sec if ctl.status == "ok" else MAX_PAUSE_DEFAULT
        if ctl.status == "ok" and ctl.state == "running" and ctl.seq > baseline:
            doc.update(state="running", paused_since=None, heartbeat_at=iso(now))
            write_status(env, doc)
            env.stdout("wait-resume", "RESUMED", **keys(now, limit))
            return EXIT_OK
        if ctl.status == "broken":
            doc.update(state="running", paused_since=None, heartbeat_at=iso(now))
            write_status(env, doc)
            env.warn("warning: control file is broken - resuming the loop")
            env.stdout("wait-resume", "CONTROL_BROKEN", **keys(now, limit))
            return EXIT_CONTROL_BROKEN
        if (now - since).total_seconds() > limit:
            doc.update(
                state="ended", ended_reason="pause_timeout", heartbeat_at=iso(now)
            )
            write_status(env, doc)
            env.stdout("wait-resume", "PAUSE_TIMEOUT", **keys(now, limit))
            return EXIT_PAUSE_TIMEOUT
        tick = env.monotonic()
        if tick - started >= max_wait:
            doc["heartbeat_at"] = iso(now)
            write_status(env, doc)
            env.stdout("wait-resume", "STILL_PAUSED", **keys(now, limit))
            return EXIT_PAUSED
        if tick - last_beat >= HEARTBEAT_SEC:
            doc["heartbeat_at"] = iso(now)
            write_status(env, doc)
            last_beat = tick
        env.sleep(TICK_SEC)


def cmd_loop_end(env: Env, args: list[str]) -> int:
    rest, raw = _split_option(args, "--done")
    if len(rest) != 1 or rest[0] not in END_REASONS:
        raise UsageError("loop-end needs one reason: done, blocked or no_task")
    reason = rest[0]
    done = None if raw is None else _int_arg(raw, 0, ITER_MAX)
    doc = read_loop_status(env.status_path)
    if doc is None:
        env.warn("warning: no active loop; nothing written")
        env.stdout("loop-end", "NO_LOOP", reason=reason, done=_progress(None, done))
        return EXIT_OK
    if doc["state"] == "ended":
        env.stdout(
            "loop-end", "ALREADY_ENDED", reason=doc["ended_reason"], done=_progress(doc)
        )
        return EXIT_OK
    if done is not None:
        if done > doc["iterations_total"]:
            raise UsageError("done exceeds total")
        doc["iterations_done"] = done
    doc.update(
        state="ended",
        ended_reason=reason,
        paused_since=None,
        heartbeat_at=iso(env.now()),
    )
    write_status(env, doc)
    env.stdout("loop-end", "ENDED", reason=reason, done=_progress(doc))
    return EXIT_OK


SUBCOMMANDS: dict[str, Callable[[Env, list[str]], int]] = {
    "loop-start": cmd_loop_start,
    "loop-check": cmd_loop_check,
    "wait-resume": cmd_wait_resume,
    "loop-end": cmd_loop_end,
}


def main(argv: list[str], env: Env | None = None) -> int:
    """`argv[0]` = 서브커맨드. 예외는 밖으로 내보내지 않고 exit code 로 바꾼다."""
    env = env or Env()
    try:
        if not argv or argv[0] not in SUBCOMMANDS:
            raise UsageError("unknown subcommand")
        return SUBCOMMANDS[argv[0]](env, list(argv[1:]))
    except UsageError as exc:
        env.warn(f"usage error: {exc}")
        env.warn(USAGE)
        return EXIT_USAGE
    except Exception as exc:  # noqa: BLE001 — 계약: 예외 종류만 stderr, exit 1
        env.warn(f"unexpected error: {type(exc).__name__}")
        return EXIT_UNEXPECTED


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
