#!/usr/bin/env python3
"""AI-DLC CLI.

  aidlc.py init [--force]          템플릿으로 workspace/ 생성 (user, project, teams, memory)
  aidlc.py check [user|project]    Gate 검사: 미작성 {{ }} 플레이스홀더 탐지 (실패 시 exit 1)
  aidlc.py new-team <id> [제목]     팀 문서 + 팀 Agent 생성
  aidlc.py status                  Plan/Task/LTM/STM 상태와 미처리 cascade 출력
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = ROOT / "aidlc" / "templates"
WS = ROOT / "workspace"
PLACEHOLDER_RE = re.compile(r"\{\{(.*?)\}\}")
COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
TEAM_ID_RE = re.compile(r"^[a-z][a-z0-9-]{1,30}$")


def copy_tree(src: Path, dst: Path, force: bool) -> list[Path]:
    created = []
    dst.mkdir(parents=True, exist_ok=True)
    for f in sorted(src.iterdir()):
        target = dst / f.name
        if f.is_file() and (force or not target.exists()):
            shutil.copy2(f, target)
            created.append(target)
    return created


def cmd_init(args: list[str]) -> int:
    force = "--force" in args
    created = []
    created += copy_tree(TEMPLATES / "user", WS / "user", force)
    created += copy_tree(TEMPLATES / "memory", WS / "memory", force)
    for d in ("project/adr", "project/eda", "teams", "memory/archive", "data"):
        (WS / d).mkdir(parents=True, exist_ok=True)
    for p in created:
        print(f"  created {p.relative_to(ROOT)}")
    print("\n다음 단계: workspace/user/ 의 문서 4개를 작성한 뒤 /aidlc-interpret 를 실행하세요.")
    return 0


def find_placeholders(path: Path) -> list[tuple[int, str]]:
    text = COMMENT_RE.sub(lambda m: "\n" * m.group(0).count("\n"), path.read_text(encoding="utf-8"))
    hits = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for m in PLACEHOLDER_RE.finditer(line):
            hits.append((lineno, m.group(1).strip()))
    return hits


def cmd_check(args: list[str]) -> int:
    layer = args[0] if args else "user"
    target = WS / layer
    if not target.is_dir():
        print(f"{target.relative_to(ROOT)} 가 없습니다. /aidlc-init 을 먼저 실행하세요.")
        return 1
    files = sorted(target.glob("*.md"))
    if layer == "project":
        expected = {p.name for p in (TEMPLATES / "project").glob("*.md")}
        missing = sorted(expected - {f.name for f in files})
        for name in missing:
            print(f"MISSING  {layer}/{name}")
    else:
        missing = []
    total = 0
    for f in files:
        hits = find_placeholders(f)
        total += len(hits)
        status = "OK  " if not hits else "TODO"
        print(f"{status}  {f.relative_to(WS)}  ({len(hits)}개 미작성)")
        for lineno, label in hits[:50]:
            print(f"        L{lineno}: {{{{{label}}}}}")
    ok = total == 0 and not missing
    print(f"\nGATE {'PASS' if ok else 'FAIL'} — {layer} layer: 미작성 {total}개, 누락 문서 {len(missing)}개")
    return 0 if ok else 1


def cmd_new_team(args: list[str]) -> int:
    if not args or not TEAM_ID_RE.match(args[0]):
        print("사용법: aidlc.py new-team <id: 소문자/숫자/-> [팀 제목]")
        return 1
    team = args[0]
    title = " ".join(args[1:]) or team.upper()
    team_dir = WS / "teams" / team
    agent_file = ROOT / ".claude" / "agents" / f"team-{team}.md"
    team_dir.mkdir(parents=True, exist_ok=True)

    def render(src: Path, dst: Path) -> None:
        if dst.exists():
            print(f"  exists  {dst.relative_to(ROOT)} (건너뜀)")
            return
        text = src.read_text(encoding="utf-8").replace("__TEAM_TITLE__", title).replace("__TEAM__", team)
        dst.write_text(text, encoding="utf-8")
        print(f"  created {dst.relative_to(ROOT)}")

    render(TEMPLATES / "team" / "charter.md", team_dir / "charter.md")
    render(TEMPLATES / "team" / "agent.md", agent_file)
    return 0


def cmd_status(_: list[str]) -> int:
    hook = ROOT / "aidlc" / "hooks" / "memory_cascade.py"
    return subprocess.call([sys.executable, str(hook), "status"], stdin=subprocess.DEVNULL)


COMMANDS = {"init": cmd_init, "check": cmd_check, "new-team": cmd_new_team, "status": cmd_status}


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] not in COMMANDS:
        print(__doc__)
        return 1
    return COMMANDS[argv[1]](argv[2:])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
