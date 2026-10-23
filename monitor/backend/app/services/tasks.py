"""Plan·Task 집계 (FR-002, ADR-009 §4).

Phase 집계는 Hook `Memory.phases()` 결과를 그대로 쓴다(규칙 단일 출처). Task 줄 상세(T-ID·팀·제목·
refs·deps)와 `## Blocked` 섹션은 Hook 에 없어 같은 `PHASE_RE`·`CHECKBOX_RE` 로 여기서 파싱한다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from app.models.envelope import SourceErrorCode
from app.models.tasks import PhaseProgress, PlanData, TaskItem, TasksData, TaskStatus
from app.services.aidlc_reader import (
    Doc,
    EngineUnavailable,
    HookEngine,
    HookLoader,
    SourceProblem,
)
from app.services.panel import Panel

TEAM_RE = re.compile(r"^[a-z][a-z0-9-]{1,30}$")
TASK_HEAD_RE = re.compile(r"^(T-\d+)\b\s*(.*)$")
TEAM_TAG_RE = re.compile(r"^\[([^\]]*)\]\s*(.*)$")
REF_RE = re.compile(r"\b[A-Z]{1,8}-\d{1,4}\b")
TASK_ID_RE = re.compile(r"\bT-\d+\b")
BLOCKED_HEAD_RE = re.compile(r"^##\s+Blocked\b", re.IGNORECASE)
BLOCKED_ITEM_RE = re.compile(r"^\s*[-*]\s+(?:\[[ xX]\]\s+)?(T-\d+)\b")
TITLE_SEP = " — "

MSG_ENGINE = "AI-DLC 엔진을 찾을 수 없음"
MSG_NO_WORKSPACE = "AI-DLC workspace 를 찾을 수 없음 — `/aidlc-init` 을 실행하세요"
MSG_NO_TASKS = "Task 목록이 없습니다 — `/aidlc-plan` 을 실행하세요"
MSG_TASKS_BROKEN = "Task 목록을 읽을 수 없음"
MSG_PLAN_MISSING = "plan.md 가 없어 현재·완료 Phase 를 표시하지 않습니다"
MSG_PLAN_BROKEN = "plan.md 를 읽을 수 없어 현재·완료 Phase 를 표시하지 않습니다"
MSG_STM_BROKEN = (
    "short-term.md 를 읽을 수 없어 진행 중·STM 기반 막힘 판정을 생략했습니다"
)
MSG_DUP_ID = "같은 T-ID 가 여러 번 나옵니다"


@dataclass
class ParsedTask:
    phase: str
    checked: bool
    raw: str
    id: str | None
    team: str | None
    title: str
    refs: list[str]
    deps: list[str]
    well_formed: bool


@dataclass
class ParsedTasks:
    titles: dict[str, str] = field(default_factory=dict)
    tasks: list[ParsedTask] = field(default_factory=list)
    blocked_ids: set[str] = field(default_factory=set)


def parse_task_text(
    text: str,
) -> tuple[str | None, str | None, str, list[str], list[str], bool]:
    """체크박스 뒤 텍스트 → (id, team, title, refs, deps, well_formed).

    형식: `T-001 [team] 제목 — FR-001 | deps: T-000 | DoD: ...`
    """
    head_match = TASK_HEAD_RE.match(text.strip())
    if head_match is None:
        return None, None, text.strip(), [], [], False
    task_id, rest = head_match.group(1), head_match.group(2)
    team: str | None = None
    tag = TEAM_TAG_RE.match(rest)
    if tag and TEAM_RE.match(tag.group(1)):
        team, rest = tag.group(1), tag.group(2)
    segments = rest.split(" | ")
    head = segments[0]
    if TITLE_SEP in head:
        title, ref_text = head.rsplit(TITLE_SEP, 1)
        refs = REF_RE.findall(ref_text)
    else:
        title, refs = head, []
    deps: list[str] = []
    for seg in segments[1:]:
        seg = seg.strip()
        if seg.lower().startswith("deps:"):
            deps = TASK_ID_RE.findall(seg)
            break
    return task_id, team, title.strip(), refs, deps, team is not None


def parse_tasks_body(engine: HookEngine, body: str) -> ParsedTasks:
    """Hook `Memory.phases()` 와 같은 섹션 규칙으로 Task 줄과 Blocked 항목을 모은다."""
    out = ParsedTasks()
    current: str | None = None
    in_blocked = False
    for line in body.splitlines():
        pm = engine.phase_re.match(line)
        if pm:
            current = pm.group(1)
            in_blocked = False
            out.titles.setdefault(current, line[pm.end() :].strip(" —-:\t") or current)
            continue
        if line.startswith("## "):
            current = None
            in_blocked = bool(BLOCKED_HEAD_RE.match(line))
            continue
        if in_blocked:
            bm = BLOCKED_ITEM_RE.match(line)
            if bm:
                out.blocked_ids.add(bm.group(1))
            continue
        cm = engine.checkbox_re.match(line)
        if current and cm:
            text = line[cm.end() :]
            tid, team, title, refs, deps, ok = parse_task_text(text)
            out.tasks.append(
                ParsedTask(
                    phase=current,
                    checked=cm.group(1) in "xX",
                    raw=text,
                    id=tid,
                    team=team,
                    title=title,
                    refs=refs,
                    deps=deps,
                    well_formed=ok,
                )
            )
    return out


def task_status(
    task: ParsedTask, blocked_ids: set[str], stm: dict[str, object] | None
) -> TaskStatus:
    """우선순위: done > blocked > active > open (FR-002 §2)."""
    if task.checked:
        return TaskStatus.done
    stm_active = (
        stm is not None
        and str(stm.get("status", "")).lower() == "active"
        and task.id is not None
        and str(stm.get("task", "")) == task.id
    )
    if task.id is not None and task.id in blocked_ids:
        return TaskStatus.blocked
    if (
        stm_active
        and stm is not None
        and str(stm.get("outcome", "")).lower() == "blocked"
    ):
        return TaskStatus.blocked
    if stm_active:
        return TaskStatus.active
    return TaskStatus.open


class TasksService:
    def __init__(self, root: Path, loader: HookLoader) -> None:
        self.root = root
        self.loader = loader
        self.memory_dir = root / "workspace" / "memory"

    def _load(
        self, panel: Panel
    ) -> tuple[HookEngine, Doc, dict[str, tuple[int, int]]] | None:
        """공통: workspace·엔진·tasks.md. 실패하면 panel 을 empty/error 로 두고 None."""
        if not (self.root / "workspace").is_dir():
            panel.empty(MSG_NO_WORKSPACE)
            return None
        tasks_path = self.memory_dir / "tasks.md"
        if not tasks_path.is_file():
            panel.empty(MSG_NO_TASKS)
            return None
        try:
            engine = self.loader.load(self.root)
        except EngineUnavailable:
            panel.fail(SourceErrorCode.SOURCE_MISSING, MSG_ENGINE)
            return None
        panel.touch(tasks_path)
        try:
            doc = engine.read_doc(tasks_path)
            phases = engine.memory(self.root).phases()
        except SourceProblem as problem:
            panel.fail(problem.code, MSG_TASKS_BROKEN)
            return None
        return engine, doc, phases

    def plan(self) -> Panel:
        panel = Panel()
        loaded = self._load(panel)
        if loaded is None:
            return panel
        engine, doc, phases = loaded
        parsed = parse_tasks_body(engine, doc.body)
        current: str | None = None
        completed: list[str] | None = None
        plan_path = self.memory_dir / "plan.md"
        if not plan_path.is_file():
            panel.warn(MSG_PLAN_MISSING)
        else:
            panel.touch(plan_path)
            try:
                plan_meta = engine.read_doc(plan_path).meta
            except SourceProblem:
                panel.warn(MSG_PLAN_BROKEN)
            else:
                if (
                    "current_phase" not in plan_meta
                    and "completed_phases" not in plan_meta
                ):
                    panel.warn(MSG_PLAN_BROKEN)
                else:
                    raw_current = plan_meta.get("current_phase")
                    current = (
                        str(raw_current) if raw_current not in (None, "") else None
                    )
                    raw_done = plan_meta.get("completed_phases") or []
                    if isinstance(raw_done, list):
                        completed = [str(x) for x in raw_done]
                    else:
                        completed = [str(raw_done)]
        items = [
            PhaseProgress(
                phase=name,
                title=parsed.titles.get(name, name),
                total=total,
                checked=checked,
                percent=(checked * 100 // total) if total else 0,
                completed=None if completed is None else name in completed,
                current=None
                if current is None and completed is None
                else name == current,
            )
            for name, (total, checked) in phases.items()
        ]
        panel.data = PlanData(
            current_phase=current, completed_phases=completed, phases=items
        )
        return panel

    def tasks(
        self,
        *,
        team: str | None = None,
        status: TaskStatus | None = None,
        phase: str | None = None,
    ) -> Panel:
        panel = Panel()
        loaded = self._load(panel)
        if loaded is None:
            return panel
        engine, doc, _phases = loaded
        parsed = parse_tasks_body(engine, doc.body)
        stm: dict[str, object] | None
        stm_path = self.memory_dir / "short-term.md"
        try:
            stm = engine.read_doc(stm_path).meta
            panel.touch(stm_path)
        except SourceProblem:
            stm = None
            panel.warn(MSG_STM_BROKEN)
        ids = [t.id for t in parsed.tasks if t.id]
        if len(ids) != len(set(ids)):
            panel.warn(MSG_DUP_ID)
        items: list[TaskItem] = []
        for t in parsed.tasks:
            st = task_status(t, parsed.blocked_ids, stm)
            if team is not None and t.team != team:
                continue
            if status is not None and st != status:
                continue
            if phase is not None and t.phase != phase:
                continue
            items.append(
                TaskItem(
                    id=t.id,
                    team=t.team,
                    title=t.title,
                    refs=t.refs,
                    deps=t.deps,
                    phase=t.phase,
                    checked=t.checked,
                    status=st,
                    well_formed=t.well_formed,
                )
            )
        panel.data = TasksData(total=len(parsed.tasks), items=items)
        return panel
