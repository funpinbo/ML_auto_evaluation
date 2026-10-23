#!/usr/bin/env python3
"""AI-DLC memory cascade hook.

계층: Plan > Tasks > Long-term memory(LTM) > Short-term memory(STM)

STM 이 닫히면(status: closed) -> 보관(archive) 후 LTM 갱신을 요구
LTM 이 갱신되면(rev 증가)    -> Tasks 갱신을 요구
Phase 의 Task 가 모두 완료되면 -> Plan 갱신을 요구

판정은 전부 파일의 frontmatter 값으로 결정되므로 결정적(deterministic)이다.
  short-term.md : status(idle|active|closed), task, team, outcome
  long-term.md  : rev, last_merged_stm
  tasks.md      : rev, synced_ltm_rev  (+ "## P1 ..." 섹션의 체크박스)
  plan.md       : completed_phases

사용법: memory_cascade.py <session-start|post-tool-use|stop|pre-compact|status>
Hook 입력 JSON 은 stdin 으로 받는다. 어떤 오류가 나도 세션을 깨지 않도록 exit 0.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

MAX_STOP_BLOCKS = 3
FM_RE = re.compile(r"\A---\n(.*?)\n---\n?", re.S)
ARCHIVE_RE = re.compile(r"^STM-(\d{4,})_.*\.md$")
PHASE_RE = re.compile(r"^##\s+(P\d+)\b")
CHECKBOX_RE = re.compile(r"^\s*[-*]\s+\[( |x|X)\]\s+")


# ---------------------------------------------------------------- frontmatter
def _parse_value(raw: str):
    v = raw.strip()
    if v.startswith("[") and v.endswith("]"):
        inner = v[1:-1].strip()
        return [_parse_value(x) for x in inner.split(",")] if inner else []
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1]
    if re.fullmatch(r"-?\d+", v):
        return int(v)
    return v


def _dump_value(v) -> str:
    if isinstance(v, list):
        return "[" + ", ".join(_dump_value(x) for x in v) + "]"
    return str(v)


def read_doc(path: Path) -> tuple[dict, str]:
    if not path.is_file():
        return {}, ""
    text = path.read_text(encoding="utf-8")
    m = FM_RE.match(text)
    if not m:
        return {}, text
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.lstrip().startswith("#"):
            k, v = line.split(":", 1)
            meta[k.strip()] = _parse_value(v.split(" #", 1)[0])
    return meta, text[m.end():]


def write_doc(path: Path, meta: dict, body: str) -> None:
    fm = "\n".join(f"{k}: {_dump_value(v)}" for k, v in meta.items())
    path.write_text(f"---\n{fm}\n---\n{body}", encoding="utf-8")


def as_int(v, default=0) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


# ---------------------------------------------------------------- memory model
@dataclass
class Step:
    level: str  # ltm | tasks | plan
    message: str


class Memory:
    def __init__(self, root: Path):
        self.root = root
        self.dir = root / "workspace" / "memory"
        self.stm = self.dir / "short-term.md"
        self.ltm = self.dir / "long-term.md"
        self.tasks = self.dir / "tasks.md"
        self.plan = self.dir / "plan.md"
        self.archive = self.dir / "archive"
        self.snapshots = self.archive / "snapshots"
        self.state_file = self.dir / ".cascade-state.json"
        self.stm_template = root / "aidlc" / "templates" / "memory" / "short-term.md"

    def exists(self) -> bool:
        return self.dir.is_dir() and self.stm.is_file()

    def rel(self, p: Path) -> str:
        try:
            return str(p.relative_to(self.root))
        except ValueError:
            return str(p)

    # -- state (stop-hook loop guard)
    def load_state(self) -> dict:
        try:
            return json.loads(self.state_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def save_state(self, state: dict) -> None:
        self.state_file.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")

    # -- archive
    def archived(self) -> list[tuple[int, Path]]:
        if not self.archive.is_dir():
            return []
        out = []
        for p in self.archive.iterdir():
            m = ARCHIVE_RE.match(p.name)
            if m:
                out.append((int(m.group(1)), p))
        return sorted(out)

    def latest_seq(self) -> int:
        items = self.archived()
        return items[-1][0] if items else 0

    def reset_stm(self) -> None:
        if self.stm_template.is_file():
            meta, body = read_doc(self.stm_template)
        else:
            meta, body = {}, "\n# Short-term Memory\n"
        meta["status"] = "idle"
        write_doc(self.stm, meta, body)

    def archive_stm_if_closed(self) -> Path | None:
        meta, body = read_doc(self.stm)
        if str(meta.get("status", "")).lower() != "closed":
            return None
        self.archive.mkdir(parents=True, exist_ok=True)
        seq = self.latest_seq() + 1
        task = re.sub(r"[^A-Za-z0-9_-]", "", str(meta.get("task") or "none")) or "none"
        meta["seq"] = seq
        meta["archived_at"] = now()
        dest = self.archive / f"STM-{seq:04d}_{task}.md"
        write_doc(dest, meta, body)
        self.reset_stm()
        return dest

    def snapshot_stm(self) -> Path | None:
        meta, body = read_doc(self.stm)
        if str(meta.get("status", "")).lower() != "active":
            return None
        self.snapshots.mkdir(parents=True, exist_ok=True)
        stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        dest = self.snapshots / f"SNAP-{stamp}_{meta.get('task', 'none')}.md"
        write_doc(dest, meta, body)
        return dest

    # -- tasks
    def phases(self) -> dict[str, tuple[int, int]]:
        """phase -> (total, checked)"""
        _, body = read_doc(self.tasks)
        result: dict[str, list[int]] = {}
        current = None
        for line in body.splitlines():
            pm = PHASE_RE.match(line)
            if pm:
                current = pm.group(1)
                result.setdefault(current, [0, 0])
                continue
            if line.startswith("## "):
                current = None
                continue
            cm = CHECKBOX_RE.match(line)
            if current and cm:
                result[current][0] += 1
                if cm.group(1) in "xX":
                    result[current][1] += 1
        return {k: (v[0], v[1]) for k, v in result.items()}

    # -- cascade evaluation (가장 아래 계층의 미처리 단계 하나만 반환)
    def pending(self) -> Step | None:
        ltm_meta, _ = read_doc(self.ltm)
        merged = as_int(ltm_meta.get("last_merged_stm"))
        unmerged = [p for seq, p in self.archived() if seq > merged]
        if unmerged:
            latest = self.latest_seq()
            files = "\n".join(f"  - {self.rel(p)}" for p in unmerged)
            return Step("ltm", (
                "[AI-DLC cascade 1/3] Short-term memory 가 종료되었습니다. Long-term memory 를 갱신하세요.\n"
                f"미반영 STM 아카이브:\n{files}\n"
                f"절차: (1) {self.rel(self.ltm)} 를 먼저 읽는다 "
                "(2) 아카이브의 결정/패턴/이슈/교훈을 기존 항목과 비교해 추가·수정·폐기한다(중복 금지, 근거로 STM 번호 표기) "
                f"(3) frontmatter 를 rev: {as_int(ltm_meta.get('rev')) + 1}, last_merged_stm: {latest} 로 갱신한다. "
                "memory-curator 서브에이전트에 위임해도 된다."
            ))

        tasks_meta, _ = read_doc(self.tasks)
        ltm_rev = as_int(ltm_meta.get("rev"))
        synced = as_int(tasks_meta.get("synced_ltm_rev"))
        if ltm_rev > synced:
            return Step("tasks", (
                "[AI-DLC cascade 2/3] Long-term memory 가 갱신되었습니다(rev "
                f"{synced} -> {ltm_rev}). Task 목록을 갱신하세요.\n"
                f"절차: (1) {self.rel(self.ltm)} 의 변경분과 최근 STM 아카이브의 outcome 을 읽는다 "
                f"(2) {self.rel(self.tasks)} 에서 완료 Task 체크, 새로 발견된 Task 추가, 막힌 Task 에 blocker 표기, 우선순위/의존성 재조정 "
                f"(3) frontmatter 를 rev: {as_int(tasks_meta.get('rev')) + 1}, synced_ltm_rev: {ltm_rev} 로 갱신한다."
            ))

        plan_meta, _ = read_doc(self.plan)
        done_in_plan = {str(x) for x in (plan_meta.get("completed_phases") or [])}
        finished = [p for p, (total, checked) in self.phases().items()
                    if total > 0 and total == checked and p not in done_in_plan]
        if finished:
            return Step("plan", (
                f"[AI-DLC cascade 3/3] Phase {', '.join(finished)} 의 모든 Task 가 완료되었습니다. Plan 을 갱신하세요.\n"
                f"절차: (1) {self.rel(self.plan)} 의 해당 Phase 상태를 완료로 바꾸고 회고(목표 대비 결과, LTM 핵심 교훈)를 진행 로그에 남긴다 "
                "(2) 다음 Phase 의 범위/일정을 LTM 기준으로 재검토한다 "
                f"(3) frontmatter completed_phases 에 {', '.join(finished)} 를 추가하고 current_phase 를 다음 Phase 로 바꾼다."
            ))
        return None

    def summary(self) -> str:
        stm, _ = read_doc(self.stm)
        ltm, _ = read_doc(self.ltm)
        tasks, _ = read_doc(self.tasks)
        plan, _ = read_doc(self.plan)
        phases = self.phases()
        phase_txt = ", ".join(f"{p} {c}/{t}" for p, (t, c) in phases.items()) or "(Task 없음)"
        step = self.pending()
        lines = [
            "## AI-DLC 상태",
            f"- Plan: current_phase={plan.get('current_phase', '-')}, completed={plan.get('completed_phases', [])}",
            f"- Tasks: rev={tasks.get('rev', 0)}, synced_ltm_rev={tasks.get('synced_ltm_rev', 0)} | {phase_txt}",
            f"- LTM: rev={ltm.get('rev', 0)}, last_merged_stm={ltm.get('last_merged_stm', 0)}",
            f"- STM: status={stm.get('status', '-')}, task={stm.get('task', '-')}, team={stm.get('team', '-')}",
            f"- STM 아카이브: {self.latest_seq()}건",
            f"- 미처리 cascade: {step.level if step else '없음'}",
        ]
        if step:
            lines += ["", step.message]
        elif str(stm.get("status")) == "active":
            lines += ["", f"진행 중인 STM 이 있습니다({stm.get('task')}). {self.rel(self.stm)} 를 읽고 이어서 작업하세요."]
        return "\n".join(lines)


# ---------------------------------------------------------------- hook events
def _emit(obj: dict) -> None:
    print(json.dumps(obj, ensure_ascii=False))


def _touches_memory(mem: Memory, payload: dict) -> bool:
    ti = payload.get("tool_input") or {}
    fp = ti.get("file_path") or ti.get("path") or ""
    if not fp:
        return False
    try:
        Path(fp).resolve().relative_to(mem.dir.resolve())
        return True
    except ValueError:
        return False


def handle(event: str, payload: dict, root: Path) -> int:
    mem = Memory(root)
    if event == "status":
        if not mem.exists():
            print("workspace/memory 가 없습니다. 먼저 /aidlc-init 을 실행하세요.")
            return 0
        mem.archive_stm_if_closed()
        print(mem.summary())
        return 0

    if not mem.exists():
        return 0
    archived = mem.archive_stm_if_closed()
    note = f"STM 을 {mem.rel(archived)} 로 보관하고 short-term.md 를 초기화했습니다.\n" if archived else ""

    if event == "session-start":
        _emit({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": note + mem.summary()}})
    elif event == "post-tool-use":
        if not (_touches_memory(mem, payload) or archived):
            return 0
        step = mem.pending()
        if step or note:
            _emit({"hookSpecificOutput": {"hookEventName": "PostToolUse",
                                          "additionalContext": note + (step.message if step else "")}})
    elif event == "stop":
        state = mem.load_state()
        step = mem.pending()
        if step is None:
            if state.get("stop_blocks"):
                mem.save_state({"stop_blocks": 0})
            return 0
        blocks = as_int(state.get("stop_blocks")) + 1
        if blocks > MAX_STOP_BLOCKS:
            mem.save_state({"stop_blocks": 0})
            _emit({"systemMessage": f"AI-DLC cascade 가 {MAX_STOP_BLOCKS}회 연속 미완료되어 종료를 허용합니다. "
                                    f"남은 단계: {step.level}. /aidlc-status 로 확인하세요."})
            return 0
        mem.save_state({"stop_blocks": blocks})
        _emit({"decision": "block", "reason": note + step.message})
    elif event == "pre-compact":
        snap = mem.snapshot_stm()
        if snap:
            _emit({"systemMessage": f"컨텍스트 압축 전 STM 스냅샷 저장: {mem.rel(snap)}"})
    return 0


def main(argv: list[str]) -> int:
    event = argv[1] if len(argv) > 1 else "status"
    payload: dict = {}
    if event != "status" and not sys.stdin.isatty():
        try:
            raw = sys.stdin.read()
            payload = json.loads(raw) if raw.strip() else {}
        except ValueError:
            payload = {}
    root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or Path(__file__).resolve().parents[2])
    try:
        return handle(event, payload, root)
    except Exception as exc:  # hook 오류로 세션을 막지 않는다
        print(f"[aidlc memory_cascade] {type(exc).__name__}: {exc}", file=sys.stderr)
        return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
