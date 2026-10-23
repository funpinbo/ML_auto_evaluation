"""파이프라인 단계 0~6 판정 + Gate 3종 (FR-001 §2, D-21 — A11 가정).

각 단계는 자기 조건으로만 판정한다(R1). 조건 값은 3값(True/False/None=확인 불가)이며
깨진 판정 파일은 그 단계만 `unknown` 으로 만든다(R6, NFR-002).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from app.models.pipeline import Gate, PipelineData, Stage, StageState
from app.services.aidlc_reader import (
    EngineUnavailable,
    HookEngine,
    HookLoader,
    SourceProblem,
)
from app.services.gates import GateOutcome, GateService
from app.services.panel import Panel

Tri = bool | None

STAGES: tuple[tuple[str, str], ...] = (
    ("init", "/aidlc-init"),
    ("interpret", "/aidlc-interpret"),
    ("analyze", "/aidlc-analyze"),
    ("teams", "/aidlc-teams"),
    ("plan", "/aidlc-plan"),
    ("run", "/aidlc-run"),
    ("docs", "/aidlc-docs"),
)
USER_DOCS_FALLBACK = (
    "01-project-overview.md",
    "02-development-standards.md",
    "03-architecture-philosophy.md",
    "04-data-definition.md",
)
MEMORY_DOCS = ("short-term.md", "long-term.md", "plan.md", "tasks.md")
ANALYSIS_DOCS = (
    "10-business-analysis.md",
    "20-architecture-analysis.md",
    "30-data-analysis.md",
)
INTERPRETATION = "00-interpretation.md"
SECTION6_RE = re.compile(r"^##\s+6\b")
DECISION_RE = re.compile(r"^\s*-\s*결정:(.*)$")

MSG_NO_WORKSPACE = "AI-DLC workspace 를 찾을 수 없음 — `/aidlc-init` 을 실행하세요"
MSG_UNKNOWN_STAGE = "일부 파일을 읽을 수 없어 확인 불가 단계가 있습니다"
MSG_ENGINE = "AI-DLC 엔진을 찾을 수 없음"
MSG_GATE_UNKNOWN = "{layer} Gate 를 확인할 수 없습니다"


def all3(*values: Tri) -> Tri:
    if any(v is False for v in values):
        return False
    if any(v is None for v in values):
        return None
    return True


def any3(*values: Tri) -> Tri:
    if any(v is True for v in values):
        return True
    if any(v is None for v in values):
        return None
    return False


def stage_state(done: Tri, started: Tri) -> StageState:
    if done is True:
        return "done"
    if done is None:
        return "unknown"
    if started is True:
        return "in_progress"
    if started is None:
        return "unknown"
    return "waiting"


def decision_of(body: str) -> str | None:
    """00 §6 의 첫 `- 결정:` 줄 → GO | HOLD | None(미결정) (R3)."""
    in_section = False
    for line in body.splitlines():
        if line.startswith("## "):
            in_section = bool(SECTION6_RE.match(line))
            continue
        if not in_section:
            continue
        m = DECISION_RE.match(line)
        if m:
            words = m.group(1).replace("*", " ").split()
            word = words[0] if words else ""
            return word if word in ("GO", "HOLD") else None
    return None


@dataclass
class _Ctx:
    root: Path
    engine: HookEngine | None
    gates: dict[str, GateOutcome]

    @property
    def ws(self) -> Path:
        return self.root / "workspace"

    def is_file(self, rel: str) -> bool:
        return (self.root / rel).is_file()

    def meta(self, path: Path) -> dict[str, object] | None:
        """frontmatter. 엔진 없음·깨짐 → None (확인 불가)."""
        if self.engine is None:
            return None
        try:
            return self.engine.read_doc(path).meta
        except SourceProblem:
            return None

    def gate_pass(self, layer: str) -> Tri:
        result = self.gates[layer].result
        return None if result == "UNKNOWN" else result == "PASS"


def _stage0(c: _Ctx) -> tuple[Tri, Tri]:
    tpl = c.root / "aidlc" / "templates" / "user"
    names = (
        sorted(p.name for p in tpl.glob("*.md"))
        if tpl.is_dir()
        else list(USER_DOCS_FALLBACK)
    )
    present = [(c.ws / "user" / n).is_file() for n in names]
    present += [(c.ws / "memory" / n).is_file() for n in MEMORY_DOCS]
    return all(present), any(present)


def _stage1(c: _Ctx) -> tuple[Tri, Tri]:
    path = c.ws / "project" / INTERPRETATION
    exists = path.is_file()
    if not exists:
        return False, False
    project = c.gates["project"]
    placeholders: Tri
    if project.result == "UNKNOWN":
        placeholders = None
    else:
        count = project.file_unwritten.get(f"project/{INTERPRETATION}")
        placeholders = None if count is None else count == 0
    go: Tri
    try:
        go = decision_of(path.read_text(encoding="utf-8")) == "GO"
    except (OSError, UnicodeDecodeError):
        go = None
    return all3(True, placeholders, go, c.gate_pass("user")), True


def _stage2(c: _Ctx) -> tuple[Tri, Tri]:
    present = [(c.ws / "project" / n).is_file() for n in ANALYSIS_DOCS]
    return all(present), any(present)


def _stage3(c: _Ctx) -> tuple[Tri, Tri]:
    path = c.ws / "project" / "40-team-composition.md"
    exists = path.is_file()
    teams_dir = c.ws / "teams"
    any_charter = teams_dir.is_dir() and any(teams_dir.glob("*/charter.md"))
    started = exists or any_charter
    if not exists:
        return False, started
    meta = c.meta(path)
    if meta is None:
        return None, started
    teams = meta.get("teams")
    if not isinstance(teams, list) or not teams:
        return False, started
    charters = all((teams_dir / str(t) / "charter.md").is_file() for t in teams)
    return charters, started


@dataclass
class _TasksInfo:
    rev: int
    phases: dict[str, tuple[int, int]]
    pending: str | None


def _tasks_info(c: _Ctx) -> _TasksInfo | None:
    if c.engine is None:
        return None
    try:
        rev = c.engine.as_int(
            c.engine.read_doc(c.ws / "memory" / "tasks.md").meta.get("rev")
        )
        view = c.engine.memory(c.root)
        return _TasksInfo(rev, view.phases(), view.pending_level())
    except SourceProblem:
        return None


def _stage4(info: _TasksInfo | None) -> tuple[Tri, Tri]:
    if info is None:
        return None, None
    started = info.rev >= 1
    has_tasks = any(total >= 1 for total, _ in info.phases.values())
    return started and has_tasks, started


def _stage5(c: _Ctx, info: _TasksInfo | None, d4: Tri) -> tuple[Tri, Tri]:
    if info is None:
        # tasks.md(또는 엔진)를 못 읽으면 4·5 는 확인 불가 (FR-001 AC-16, §4 엔진 로드 실패)
        return None, None
    stm = c.meta(c.ws / "memory" / "short-term.md")
    stm_status: str | None = None if stm is None else str(stm.get("status", "")).lower()
    archived: Tri
    try:
        archived = (
            c.engine is not None and c.engine.memory(c.root).archived_count() >= 1
        )
    except SourceProblem:
        archived = None
    with_tasks = [(t, k) for t, k in info.phases.values() if t > 0]
    phases_done = bool(with_tasks) and all(t == k for t, k in with_tasks)
    any_checked = any(k >= 1 for _, k in info.phases.values())
    no_pending = info.pending is None
    stm_inactive: Tri = None if stm_status is None else stm_status != "active"
    stm_started: Tri = (
        None if stm_status is None else stm_status in ("active", "closed")
    )
    done = all3(d4, phases_done, no_pending, stm_inactive)
    started = any3(any_checked, stm_started, archived)
    return done, started


def _stage6(c: _Ctx) -> tuple[Tri, Tri]:
    docs = c.root / "docs"
    readme = (docs / "README.md").is_file()
    started = docs.is_dir() and any(
        p.relative_to(docs).parts[0] != "aidlc" for p in docs.rglob("*.md")
    )
    return all3(c.gate_pass("docs"), readme), started


def _gate_model(g: GateOutcome) -> Gate:
    return Gate(
        layer=g.layer,  # type: ignore[arg-type]
        result=g.result,  # type: ignore[arg-type]
        unwritten=g.unwritten,
        missing=g.missing,
        target_missing=g.target_missing,
        no_documents=g.no_documents,
        error_code=g.error_code,
        checked_at=g.checked_at,
    )


class PipelineService:
    def __init__(self, root: Path, loader: HookLoader, gates: GateService) -> None:
        self.root = root
        self.loader = loader
        self.gates = gates

    def read(self) -> Panel:
        panel = Panel()
        if not (self.root / "workspace").is_dir():
            panel.empty(MSG_NO_WORKSPACE)
            return panel
        engine: HookEngine | None
        try:
            engine = self.loader.load(self.root)
        except EngineUnavailable:
            engine = None
            panel.warn(MSG_ENGINE)
        gates = {
            layer: self.gates.check(self.root, layer)
            for layer in ("user", "project", "docs")
        }
        for layer, g in gates.items():
            if g.result == "UNKNOWN":
                panel.warn(MSG_GATE_UNKNOWN.format(layer=layer))
        c = _Ctx(self.root, engine, gates)
        info = _tasks_info(c)
        d4, s4 = _stage4(info)
        results = [_stage0(c), _stage1(c), _stage2(c), _stage3(c), (d4, s4)]
        results.append(_stage5(c, info, d4))
        results.append(_stage6(c))
        stages = [
            Stage(
                index=i,
                name=STAGES[i][0],
                command=STAGES[i][1],
                state=stage_state(d, s),
            )
            for i, (d, s) in enumerate(results)
        ]
        if any(s.state == "unknown" for s in stages):
            panel.warn(MSG_UNKNOWN_STAGE)
        not_done = [s for s in stages if s.state != "done"]
        current = not_done[0] if not_done else stages[-1]
        panel.touch(
            self.root / "workspace" / "memory" / "tasks.md",
            self.root / "workspace" / "memory" / "short-term.md",
            self.root / "workspace" / "memory" / "plan.md",
        )
        panel.data = PipelineData(
            current_stage=current.index,
            current_stage_name=current.name,
            next_command=current.command if not_done else None,
            all_done=not not_done,
            stages=stages,
            gates=[_gate_model(gates[layer]) for layer in ("user", "project", "docs")],
        )
        return panel
