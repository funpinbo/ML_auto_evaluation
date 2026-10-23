"""가짜 AI-DLC workspace 빌더 (AIDLC_ROOT 로 주입할 루트를 만든다).

종류(kind):
- empty      workspace/ 디렉터리만 있고 memory·project 내용 없음 (패널 `empty`)
- partial    short-term.md(idle)와 tasks.md 만 있음 (long-term·plan·archive 없음)
- full       4계층 메모리 + 아카이브 + user/project/teams 문서가 모두 있는 정상 상태
- broken     파일마다 다른 방식으로 깨짐 (frontmatter 미종결, UTF-8 아님, 빈 파일, 숫자 아님)
- closed_stm full 과 같되 short-term.md 가 `status: closed`. Hook 이 읽으면 보관·초기화로 파일을
             바꿀 수 있는 상태라 "조회 전후 해시 불변" 검증(CON-03, QS-07)에 반드시 쓴다.

task_count 로 Task 수를 바꾼다 (성능 fixture 는 100).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

KINDS = ("empty", "partial", "full", "broken", "closed_stm")
TEAMS = ("backend", "frontend", "qa", "security", "ops", "architecture")


@dataclass(frozen=True)
class WorkspaceInfo:
    root: Path  # AIDLC_ROOT 로 주입한다
    kind: str
    task_count: int

    @property
    def memory(self) -> Path:
        return self.root / "workspace" / "memory"

    @property
    def monitor_dir(self) -> Path:
        return self.memory / ".monitor"

    @property
    def control_file(self) -> Path:
        return self.memory / ".control.json"

    @property
    def loop_status_file(self) -> Path:
        return self.monitor_dir / "loop-status.json"

    @property
    def claude_status_file(self) -> Path:
        return self.monitor_dir / "claude-status.json"


def _doc(meta: dict[str, object], body: str) -> str:
    front = "\n".join(f"{k}: {v}" for k, v in meta.items())
    return f"---\n{front}\n---\n{body}"


def _write(path: Path, text: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(text, bytes):
        path.write_bytes(text)
    else:
        path.write_text(text, encoding="utf-8")


def stm_text(
    status: str, task: str = "T-003", team: str = "qa", outcome: str = "none"
) -> str:
    meta = {
        "status": status,
        "task": task,
        "team": team,
        "outcome": outcome,
        "opened_at": "2026-10-23T08:30:00+00:00",
    }
    return _doc(meta, "# Short-term Memory\n\n## 1. 목표\n- Task: fake\n")


def tasks_text(task_count: int, *, rev: int = 4, synced: int = 4) -> str:
    """P1 60% / P2 40% 로 나누고, P1 앞쪽 절반을 완료([x]) 처리한다."""
    p1 = max(1, round(task_count * 0.6))
    lines = ["# Tasks", ""]
    for phase, ids in (("P1", range(1, p1 + 1)), ("P2", range(p1 + 1, task_count + 1))):
        if not ids:
            continue
        lines.append(f"## {phase} — fake phase")
        for i in ids:
            done = "x" if phase == "P1" and i <= p1 // 2 else " "
            team = TEAMS[i % len(TEAMS)]
            dep = f"T-{i - 1:03d}" if i > 1 else "-"
            lines.append(
                f"- [{done}] T-{i:03d} [{team}] fake task {i} — FR-{i % 10 + 1:03d} | deps: {dep} | DoD: fake"
            )
        lines.append("")
    lines += ["## 부록", "- [ ] 이 체크박스는 Phase 섹션 밖이라 집계 대상이 아니다", ""]
    return _doc({"rev": rev, "synced_ltm_rev": synced}, "\n".join(lines))


def _plan_text() -> str:
    body = "# Plan\n\n## 1. 전체 목표\n- fake\n\n## 2. Phase 로드맵\n| Phase | 이름 | 상태 |\n|---|---|---|\n| P1 | MVP | 진행중 |\n| P2 | 운영 | 대기 |\n"
    return _doc({"current_phase": "P1", "completed_phases": "[]"}, body)


def _ltm_text(merged: int) -> str:
    body = "# Long-term Memory\n\n## 1. 결정 사항 (Decisions)\n| ID | 결정 |\n|---|---|\n| D-01 | fake |\n"
    return _doc({"rev": 3, "last_merged_stm": merged}, body)


def _stub_docs(root: Path) -> None:
    """user/project/teams/aidlc 최소 문서. 내용은 가짜이며 표식 문자열을 넣지 않는다."""
    for name in (
        "01-project-overview",
        "02-development-standards",
        "03-architecture-philosophy",
    ):
        _write(root / "workspace" / "user" / f"{name}.md", f"# {name}\n\nfake\n")
    for name in (
        "00-interpretation",
        "20-architecture-analysis",
        "40-team-composition",
    ):
        _write(
            root / "workspace" / "project" / f"{name}.md",
            _doc({"doc": name, "layer": "project"}, "# fake\n"),
        )
    for team in ("backend", "qa"):
        _write(
            root / "workspace" / "teams" / team / "charter.md",
            _doc({"team": team, "status": "draft"}, "# fake\n"),
        )
    _write(
        root / "aidlc" / "templates" / "memory" / "short-term.md",
        stm_text("idle", "none", "none"),
    )
    _write(root / "aidlc" / "teams" / "catalog.json", '{"teams": []}\n')


def _full(root: Path, task_count: int, stm_status: str) -> None:
    mem = root / "workspace" / "memory"
    _stub_docs(root)
    outcome = "done" if stm_status == "closed" else "none"
    _write(mem / "short-term.md", stm_text(stm_status, outcome=outcome))
    _write(mem / "long-term.md", _ltm_text(merged=2))
    _write(mem / "tasks.md", tasks_text(task_count, rev=4, synced=3))
    _write(mem / "plan.md", _plan_text())
    for seq, task in ((1, "T-001"), (2, "T-002")):
        meta = {
            "status": "closed",
            "task": task,
            "team": "architecture",
            "outcome": "done",
            "seq": seq,
        }
        _write(
            mem / "archive" / f"STM-{seq:04d}_{task}.md",
            _doc(meta, "# Short-term Memory\n"),
        )


def _broken(root: Path, task_count: int) -> None:
    mem = root / "workspace" / "memory"
    _write(
        mem / "short-term.md", "---\nstatus: active\ntask: T-003\n# 닫는 --- 가 없다\n"
    )
    _write(
        mem / "long-term.md",
        _doc({"rev": "abc", "last_merged_stm": "x"}, "# 숫자가 아닌 rev\n"),
    )
    _write(
        mem / "tasks.md",
        tasks_text(task_count).encode("utf-8") + b"\n\xff\xfe\xfa broken tail\n",
    )
    _write(mem / "plan.md", "")
    _write(mem / "archive" / "STM-xxxx_bad-name.md", "not an archive name\n")
    _write(mem / "archive" / "STM-0001_T-001.md", b"\x00\x01\x02 binary")
    _write(
        mem / ".monitor" / "loop-status.json", '{"schema": 1, "run_id": '
    )  # 잘린 JSON
    _write(mem / ".control.json", "[]")  # JSON 이지만 객체가 아님


def build_workspace(
    parent: Path, kind: str = "full", *, task_count: int = 12, name: str | None = None
) -> WorkspaceInfo:
    """`parent/<name or kind>` 에 workspace 를 만들고 정보를 돌려준다."""
    if kind not in KINDS:
        raise ValueError(f"unknown workspace kind: {kind!r} (expected one of {KINDS})")
    root = parent / (name or kind)
    root.mkdir(parents=True, exist_ok=False)
    mem = root / "workspace" / "memory"
    if kind == "empty":
        (root / "workspace").mkdir()
    elif kind == "partial":
        _write(mem / "short-term.md", stm_text("idle", "none", "none"))
        _write(mem / "tasks.md", tasks_text(min(task_count, 5)))
    elif kind == "full":
        _full(root, task_count, "active")
    elif kind == "closed_stm":
        _full(root, task_count, "closed")
    else:
        _broken(root, task_count)
    return WorkspaceInfo(root=root, kind=kind, task_count=task_count)
