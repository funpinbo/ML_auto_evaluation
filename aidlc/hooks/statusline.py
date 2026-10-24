#!/usr/bin/env python3
"""AI-DLC status line 스크립트 (ADR-003 Decision 3, contracts/claude-status.schema.json). 표준 라이브러리만.

Claude Code 가 statusLine 명령으로 실행한다(stdin = 세션 상태 JSON). 순서:
1. stdin 전체 읽기 → JSON 파싱(실패하면 스냅샷 없이 체이닝만).
2. **스냅샷 먼저 저장**(Claude Code 가 느린 체이닝을 취소해도 데이터 보존): 허용 필드만 골라
   `<저장소>/workspace/memory/.monitor/claude-status.json` 에 같은 디렉터리 임시 파일 → `os.replace`.
   저장소 루트는 이 파일 위치 기준(환경 변수에 의존하지 않음). `transcript_path`·`cwd`·session_id 원문은
   저장하지 않는다 — `session_hash` = sha256(session_id) 앞 12자, `transcript_dir_name` = transcript 파일이
   든 디렉터리 이름 한 조각(계약 pattern 통과분만).
3. 체이닝: 사용자 전역 `settings.json`(`$CLAUDE_CONFIG_DIR` 또는 `~/.claude`)에서 `statusLine` 키만 읽어
   `command` 를 같은 stdin 으로 실행(timeout 2 s). 명령에 `aidlc/hooks/statusline` 이 있으면 재귀 방지로 생략.
   출력은 그대로 먼저 내보낸다. 명령 문자열·다른 키는 저장·로그하지 않는다(privacy P-23·P-24).
4. 자기 한 줄 출력: `AI-DLC 5h 23% · 7d 41% · $0.12` (한도 없으면 `AI-DLC ctx 8%`).
5. 어떤 오류에도 exit 0 (세션 표시를 깨지 않는다). 오류 메시지도 출력하지 않는다.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import math
import os
import re
import signal
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / "workspace" / "memory" / ".monitor" / "claude-status.json"
MAX_STDIN = 1 << 20
CHAIN_TIMEOUT_SEC = 2.0
SELF_MARKERS = ("aidlc/hooks/statusline", "aidlc\\hooks\\statusline")
# contracts/claude-status.schema.json 의 transcript_dir_name pattern 과 같다
DIR_NAME_RE = re.compile(r"^(?!\.{1,2}(?![\s\S]))[A-Za-z0-9._-]{1,255}(?![\s\S])")
LABEL = "AI-DLC"


# ---------------------------------------------------------------- 허용 필드 추출
def _dict(value: object) -> dict:
    return value if isinstance(value, dict) else {}


def _text(value: object, limit: int) -> str | None:
    return value if isinstance(value, str) and 0 < len(value) <= limit else None


def _number(value: object, lo: float | None = None, hi: float | None = None) -> float | int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if (lo is not None and value < lo) or (hi is not None and value > hi):
        return None
    return value


def _int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, float) and math.isfinite(value) and value.is_integer():
        value = int(value)
    return value if isinstance(value, int) and value >= 0 else None


def _window(value: object) -> dict | None:
    if not isinstance(value, dict):
        return None
    return {
        "used_percentage": _number(value.get("used_percentage"), 0, 100),
        "resets_at": _int(value.get("resets_at")),
    }


def transcript_dir_name(path: object) -> str | None:
    """transcript_path 의 상위 디렉터리 이름 한 조각만 (원문 경로는 버린다)."""
    if not isinstance(path, str) or not path or len(path) > 4096:
        return None
    parts = [p for p in re.split(r"[\\/]", path) if p]
    if len(parts) < 2:
        return None
    name = parts[-2]
    return name if DIR_NAME_RE.match(name) else None


def session_hash(session_id: object) -> str | None:
    if not isinstance(session_id, str) or not session_id:
        return None
    return hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:12]


def build_snapshot(data: dict, now: datetime | None = None) -> dict:
    """stdin dict → 스키마 1 스냅샷 (허용 필드만, additionalProperties false)."""
    now = now or datetime.now(timezone.utc)  # noqa: UP017 — 런처는 3.10+ 허용 (datetime.UTC 는 3.11)
    limits = data.get("rate_limits")
    rate_limits = None
    if isinstance(limits, dict):
        rate_limits = {
            "five_hour": _window(limits.get("five_hour")),
            "seven_day": _window(limits.get("seven_day")),
        }
    cost_in = data.get("cost")
    cost = None
    if isinstance(cost_in, dict):
        cost = {
            "total_cost_usd": _number(cost_in.get("total_cost_usd"), 0),
            "total_duration_ms": _int(cost_in.get("total_duration_ms")),
        }
    ctx_in = data.get("context_window")
    context = None
    if isinstance(ctx_in, dict):
        context = {
            "used_percentage": _number(ctx_in.get("used_percentage"), 0, 100),
            "context_window_size": _int(ctx_in.get("context_window_size")),
        }
    return {
        "schema": 1,
        "captured_at": now.astimezone(timezone.utc).replace(microsecond=0).isoformat(),  # noqa: UP017
        "claude_version": _text(data.get("version"), 64),
        "model_id": _text(_dict(data.get("model")).get("id"), 128),
        "session_hash": session_hash(data.get("session_id")),
        "transcript_dir_name": transcript_dir_name(data.get("transcript_path")),
        "rate_limits": rate_limits,
        "cost": cost,
        "context_window": context,
    }


def write_snapshot(doc: dict, target: Path = SNAPSHOT) -> bool:
    """같은 디렉터리 임시 파일 → fsync → os.replace. workspace/memory 가 없으면 쓰지 않는다."""
    memory = target.parent.parent
    if not memory.is_dir():
        return False
    target.parent.mkdir(exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(target.parent), prefix=".claude-status.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(doc, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, target)
        return True
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


# ---------------------------------------------------------------- 체이닝
def global_settings_path() -> Path:
    base = os.environ.get("CLAUDE_CONFIG_DIR")
    return Path(base) / "settings.json" if base else Path.home() / ".claude" / "settings.json"


def global_command() -> str | None:
    """전역 settings.json 의 `statusLine.command` 만. 자기 자신이면 None (재귀 방지)."""
    path = global_settings_path()
    try:
        if path.stat().st_size > MAX_STDIN:
            return None
        settings = json.loads(path.read_bytes())
    except (OSError, ValueError):
        return None
    status_line = settings.get("statusLine") if isinstance(settings, dict) else None
    if not isinstance(status_line, dict):
        return None
    command = status_line.get("command")
    if status_line.get("type", "command") != "command" or not isinstance(command, str):
        return None
    if not command.strip() or any(m in command for m in SELF_MARKERS):
        return None
    return command


def run_chained(command: str, stdin: bytes, timeout: float = CHAIN_TIMEOUT_SEC) -> bytes:
    """같은 stdin 으로 셸 실행. timeout 이면 프로세스 그룹을 죽이고 빈 출력."""
    kwargs: dict = {}
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    else:
        kwargs["start_new_session"] = True
    # 사용자 자신의 전역 statusLine 명령을 Claude Code 와 같은 방식(셸)으로 실행한다
    proc = subprocess.Popen(
        command,
        shell=True,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        **kwargs,
    )
    try:
        out, _ = proc.communicate(stdin, timeout=timeout)
        return out or b""
    except subprocess.TimeoutExpired:
        _kill(proc)
        return b""


def _kill(proc: subprocess.Popen) -> None:
    try:
        if os.name == "nt":
            proc.kill()
        else:
            os.killpg(proc.pid, signal.SIGKILL)
    except OSError:
        pass
    try:
        proc.communicate(timeout=1)
    except (subprocess.TimeoutExpired, OSError, ValueError):
        pass


# ---------------------------------------------------------------- 출력
def _pct(value: object) -> str | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return f"{math.floor(value + 0.5)}%"  # 0.5 는 올림 (FR-004 AC-2)


def own_line(doc: dict | None) -> str:
    if doc is None:
        return LABEL
    parts: list[str] = []
    limits = doc.get("rate_limits") or {}
    for label, key in (("5h", "five_hour"), ("7d", "seven_day")):
        pct = _pct((limits.get(key) or {}).get("used_percentage"))
        if pct is not None:
            parts.append(f"{label} {pct}")
    if not parts:
        ctx = _pct((doc.get("context_window") or {}).get("used_percentage"))
        if ctx is not None:
            parts.append(f"ctx {ctx}")
    cost = (doc.get("cost") or {}).get("total_cost_usd")
    if isinstance(cost, (int, float)) and not isinstance(cost, bool):
        parts.append(f"${cost:.2f}")
    return LABEL + (" " + " · ".join(parts) if parts else "")


def _emit(text: bytes) -> None:
    out = getattr(sys.stdout, "buffer", None)
    if out is not None:
        out.write(text)
        out.flush()


def main() -> int:
    raw = b""
    doc: dict | None = None
    # 각 단계는 실패해도 다음 단계로 간다 — 세션 표시를 깨지 않는다 (오류 출력 없음)
    with contextlib.suppress(Exception):
        raw = sys.stdin.buffer.read(MAX_STDIN)
        data = json.loads(raw) if raw.strip() else None
        if isinstance(data, dict):
            doc = build_snapshot(data)
            write_snapshot(doc)
    with contextlib.suppress(Exception):
        command = global_command()
        if command is not None:
            chained = run_chained(command, raw).rstrip(b"\r\n")
            if chained:
                _emit(chained + b"\n")
    with contextlib.suppress(Exception):
        _emit((own_line(doc) + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    with contextlib.suppress(BaseException):  # KeyboardInterrupt·SystemExit 포함, 항상 exit 0
        main()
    sys.exit(0)
