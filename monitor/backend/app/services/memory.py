"""메모리 상태 (FR-003, ADR-009).

미처리 cascade 판정은 Hook `Memory(root).pending().level` 만 쓴다. 읽기만 하며 Hook 쓰기 함수를
부르지 않는다. 파일별로 실패를 격리해 읽을 수 있는 값은 계속 보여 준다 (AC-13).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from app.models.envelope import SourceErrorCode
from app.models.memory import MemoryData, StmView
from app.services.aidlc_reader import (
    EngineUnavailable,
    HookEngine,
    HookLoader,
    SourceProblem,
)
from app.services.panel import Panel

STM_STATUSES = {"idle", "active", "closed"}
MSG_NO_MEMORY = "메모리 파일이 없습니다 — `/aidlc-init` 을 실행하세요"
MSG_ENGINE = "AI-DLC 엔진을 찾을 수 없음"
MSG_STM_BROKEN = "STM 을 읽을 수 없음"
MSG_STM_STATUS = "STM status 값이 idle·active·closed 가 아닙니다"
MSG_OPENED_AT = "STM opened_at 이 없거나 RFC 3339 가 아니거나 미래 시각입니다"
MSG_FILE_BROKEN = "{name} 을 읽을 수 없음"
MSG_FILE_MISSING = "{name} 이 없습니다"
MSG_NOT_INT = "{name} {key} 값이 숫자가 아니어서 0 으로 해석했습니다"
MSG_CASCADE = "미처리 cascade 를 판정할 수 없음"
MSG_ARCHIVE = "STM 아카이브 목록을 읽을 수 없음"


def _text(value: Any) -> str | None:
    if value is None or value == "":
        return None
    return str(value)


def _empty_stm(code: SourceErrorCode) -> StmView:
    return StmView(
        status=None,
        task=None,
        team=None,
        outcome=None,
        opened_at=None,
        elapsed_sec=None,
        error_code=code,
    )


def parse_rfc3339(value: Any) -> datetime | None:
    """시간대가 있는 ISO 8601/RFC 3339 만 허용."""
    if not isinstance(value, str) or "T" not in value.upper():
        return None
    text = value.strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def elapsed_seconds(opened_at: Any, now: datetime) -> int | None:
    opened = parse_rfc3339(opened_at)
    if opened is None:
        return None
    delta = (now - opened).total_seconds()
    return None if delta < 0 else int(delta)


class MemoryService:
    def __init__(
        self, root: Path, loader: HookLoader, clock: Callable[[], datetime]
    ) -> None:
        self.root = root
        self.loader = loader
        self.clock = clock
        self.dir = root / "workspace" / "memory"

    def _int_field(
        self,
        panel: Panel,
        engine: HookEngine,
        meta: dict[str, Any],
        key: str,
        name: str,
    ) -> int:
        raw = meta.get(key)
        value = engine.as_int(raw)
        if raw is not None and not isinstance(raw, int):
            try:
                int(raw)
            except (TypeError, ValueError):
                panel.warn(MSG_NOT_INT.format(name=name, key=key))
        return value

    def _doc_meta(
        self, panel: Panel, engine: HookEngine, filename: str
    ) -> dict[str, Any] | None:
        path = self.dir / filename
        if not path.is_file():
            panel.warn(MSG_FILE_MISSING.format(name=filename))
            return None
        panel.touch(path)
        try:
            return engine.read_doc(path).meta
        except SourceProblem:
            panel.warn(MSG_FILE_BROKEN.format(name=filename))
            return None

    def read(self) -> Panel:
        panel = Panel()
        if not self.dir.is_dir():
            panel.empty(MSG_NO_MEMORY)
            return panel
        try:
            engine = self.loader.load(self.root)
        except EngineUnavailable:
            panel.fail(SourceErrorCode.SOURCE_MISSING, MSG_ENGINE)
            return panel
        now = self.clock()
        stm = self._stm(panel, engine, now)

        ltm = self._doc_meta(panel, engine, "long-term.md")
        tasks = self._doc_meta(panel, engine, "tasks.md")
        plan = self._doc_meta(panel, engine, "plan.md")

        ltm_rev = (
            None
            if ltm is None
            else self._int_field(panel, engine, ltm, "rev", "long-term.md")
        )
        merged = (
            None
            if ltm is None
            else self._int_field(panel, engine, ltm, "last_merged_stm", "long-term.md")
        )
        tasks_rev = (
            None
            if tasks is None
            else self._int_field(panel, engine, tasks, "rev", "tasks.md")
        )
        synced = (
            None
            if tasks is None
            else self._int_field(panel, engine, tasks, "synced_ltm_rev", "tasks.md")
        )
        current_phase: str | None = None
        completed: list[str] | None = None
        if plan is not None:
            current_phase = _text(plan.get("current_phase"))
            raw_done = plan.get("completed_phases")
            if isinstance(raw_done, list):
                completed = [str(x) for x in raw_done]
            elif raw_done not in (None, ""):
                completed = [str(raw_done)]
            else:
                completed = []

        view = engine.memory(self.root)
        archive_count: int | None
        latest: int | None
        try:
            archive_count, latest = view.archived_count(), view.latest_seq()
        except SourceProblem:
            archive_count = latest = None
            panel.warn(MSG_ARCHIVE)
        try:
            level = view.pending_level() or "none"
        except SourceProblem:
            level = "unknown"
            panel.warn(MSG_CASCADE)
        try:
            state = view.load_state()
            stop_blocks: int | None = engine.as_int(state.get("stop_blocks"))
        except SourceProblem:
            stop_blocks = None
        panel.touch(self.dir / "archive", self.dir / ".cascade-state.json")

        panel.data = MemoryData(
            stm=stm,
            ltm_rev=ltm_rev,
            last_merged_stm=merged,
            tasks_rev=tasks_rev,
            synced_ltm_rev=synced,
            current_phase=current_phase,
            completed_phases=completed,
            archive_count=archive_count,
            latest_archive_seq=latest,
            pending_cascade=level,  # type: ignore[arg-type]
            stop_blocks=stop_blocks,
        )
        return panel

    def _stm(self, panel: Panel, engine: HookEngine, now: datetime) -> StmView:
        path = self.dir / "short-term.md"
        if not path.is_file():
            panel.warn(MSG_FILE_MISSING.format(name="short-term.md"))
            return _empty_stm(SourceErrorCode.SOURCE_MISSING)
        panel.touch(path)
        try:
            meta = engine.read_doc(path).meta
        except SourceProblem as problem:
            panel.warn(MSG_STM_BROKEN)
            return _empty_stm(problem.code)
        raw_status = str(meta.get("status", "")).strip().lower()
        status = raw_status if raw_status in STM_STATUSES else "unknown"
        if status == "unknown":
            panel.warn(MSG_STM_STATUS)
        opened_at = _text(meta.get("opened_at"))
        elapsed: int | None = None
        if status == "active":
            elapsed = elapsed_seconds(opened_at, now)
            if elapsed is None:
                panel.warn(MSG_OPENED_AT)
        return StmView(
            status=status,  # type: ignore[arg-type]
            task=_text(meta.get("task")),
            team=_text(meta.get("team")),
            outcome=_text(meta.get("outcome")),
            opened_at=opened_at,
            elapsed_sec=elapsed,
        )
