"""상태 스냅샷 리더 — `workspace/memory/.monitor/claude-status.json` (ADR-003 Decision 4, contracts/README §2·§3).

- 읽기만 한다(작성자는 status line 스크립트 하나). 없음·깨짐·스키마 버전 불일치에 견딘다.
- 관대한 읽기와 별개로 보안 필드 `transcript_dir_name` 은 계약 pattern 으로 **재검증**한다(P-25). 실패하면
  힌트를 버린다. 이 값은 해석기(resolver)에만 넘기고 API 응답·로그에 넣지 않는다(D-13).
- 파일 크기 상한·정규 파일 확인으로 FIFO·거대 파일에 막히지 않는다.
"""

from __future__ import annotations

import json
import math
import os
import stat
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from app.services.usage.privacy_filter import parse_timestamp
from app.services.usage.resolver import valid_dir_name

MAX_SNAPSHOT_BYTES = 64 * 1024
STALE_AFTER_SEC = 600  # ADR-003 §4: 10분 초과 = SNAPSHOT_STALE (600 s 는 경고 없음)

SnapshotState = Literal["ok", "missing", "broken", "unreadable"]


@dataclass(frozen=True)
class Window:
    used_percentage: float | None
    resets_at: int | None


@dataclass(frozen=True)
class Snapshot:
    state: SnapshotState
    captured_at: datetime | None = None
    model_id: str | None = None
    rate_limits_present: bool = False
    five_hour: Window | None = None
    seven_day: Window | None = None
    total_cost_usd: float | None = None
    total_duration_ms: int | None = None
    context_used_percentage: float | None = None
    context_window_size: int | None = None
    transcript_dir_name: str | None = None  # 재검증 통과한 힌트만. 노출 금지
    mtime: float | None = None

    def age_sec(self, now: datetime) -> int | None:
        if self.captured_at is None:
            return None
        return max(0, int((now - self.captured_at).total_seconds()))

    def stale(self, now: datetime) -> bool:
        age = self.age_sec(now)
        return age is not None and age > STALE_AFTER_SEC


def _number(
    value: Any, lo: float | None = None, hi: float | None = None
) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    number = float(value)
    if not math.isfinite(number):
        return None
    if (lo is not None and number < lo) or (hi is not None and number > hi):
        return None
    return number


def _int(value: Any, lo: int = 0) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < lo:
        return None
    return value


def _text(value: Any, limit: int) -> str | None:
    return value if isinstance(value, str) and 0 < len(value) <= limit else None


def _window(value: Any) -> Window | None:
    if not isinstance(value, dict):
        return None
    return Window(
        used_percentage=_number(value.get("used_percentage"), 0, 100),
        resets_at=_int(value.get("resets_at")),
    )


def parse_snapshot(doc: Any, mtime: float | None = None) -> Snapshot:
    """스키마 1 dict → Snapshot. 형식이 다르면 broken (README §3 버전 불일치 = SOURCE_PARSE_ERROR)."""
    if (
        not isinstance(doc, dict)
        or doc.get("schema") != 1
        or type(doc.get("schema")) is not int
    ):
        return Snapshot("broken", mtime=mtime)
    captured = parse_timestamp(doc.get("captured_at"))
    if captured is None:
        return Snapshot("broken", mtime=mtime)
    limits = doc.get("rate_limits")
    five = seven = None
    if isinstance(limits, dict):
        five, seven = _window(limits.get("five_hour")), _window(limits.get("seven_day"))
    raw_cost, raw_ctx = doc.get("cost"), doc.get("context_window")
    cost: dict[str, Any] = raw_cost if isinstance(raw_cost, dict) else {}
    ctx: dict[str, Any] = raw_ctx if isinstance(raw_ctx, dict) else {}
    hint = doc.get("transcript_dir_name")
    return Snapshot(
        state="ok",
        captured_at=captured,
        model_id=_text(doc.get("model_id"), 128),
        rate_limits_present=isinstance(limits, dict),
        five_hour=five,
        seven_day=seven,
        total_cost_usd=_number(cost.get("total_cost_usd"), 0),
        total_duration_ms=_int(cost.get("total_duration_ms")),
        context_used_percentage=_number(ctx.get("used_percentage"), 0, 100),
        context_window_size=_int(ctx.get("context_window_size")),
        transcript_dir_name=hint if valid_dir_name(hint) else None,
        mtime=mtime,
    )


class StatuslineReader:
    def __init__(self, root: Path) -> None:
        self.path = root / "workspace" / "memory" / ".monitor" / "claude-status.json"

    def read(self) -> Snapshot:
        try:
            st = os.stat(self.path)
        except (FileNotFoundError, NotADirectoryError):
            return Snapshot("missing")
        except (OSError, ValueError):
            return Snapshot("unreadable")
        if not stat.S_ISREG(st.st_mode):
            return Snapshot("unreadable")
        if st.st_size > MAX_SNAPSHOT_BYTES:
            return Snapshot("broken", mtime=st.st_mtime)
        try:
            fd = os.open(self.path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0))
            with os.fdopen(fd, "rb") as fh:
                raw = fh.read(MAX_SNAPSHOT_BYTES + 1)
        except (OSError, ValueError):
            return Snapshot("unreadable")
        try:
            doc = json.loads(raw)
        except (ValueError, RecursionError):
            return Snapshot("broken", mtime=st.st_mtime)
        return parse_snapshot(doc, st.st_mtime)

    def hint(self) -> str | None:
        """해석기용 `transcript_dir_name` (재검증 통과분만)."""
        return self.read().transcript_dir_name
