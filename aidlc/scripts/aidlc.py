#!/usr/bin/env python3
"""AI-DLC CLI.

  aidlc.py init [--force]          템플릿으로 workspace/ 생성 (user, project, teams, memory)
  aidlc.py check [user|project|docs]  Gate 검사: 미작성 {{ }} 플레이스홀더 탐지 (실패 시 exit 1)
  aidlc.py teams                   팀 카탈로그 목록 (core / conditional)
  aidlc.py new-team <id...|--core> 카탈로그 기반 팀 charter + 팀 Agent 생성 (카탈로그 밖 id 도 허용)
  aidlc.py status                  Plan/Task/LTM/STM 상태와 미처리 cascade 출력
"""
from __future__ import annotations

import json
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
CATALOG = ROOT / "aidlc" / "teams" / "catalog.json"
TBD = "- (team-architect 가 분석서 근거로 작성)"


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
            label = m.group(1).strip()
            if label:  # 빈 `{{ }}` 는 안내문의 표기 설명이지 미작성 항목이 아니다
                hits.append((lineno, label))
    return hits


def cmd_check(args: list[str]) -> int:
    layer = args[0] if args else "user"
    if layer == "docs":
        # 프로젝트 문서: docs/ 전체 (프레임워크 문서 docs/aidlc 와 자동 생성 레퍼런스 제외)
        target, base = ROOT / "docs", ROOT / "docs"
        files = sorted(p for p in target.rglob("*.md")
                       if not p.relative_to(target).parts[0] == "aidlc" and p.name != "reference.md") if target.is_dir() else []
    else:
        target, base = WS / layer, WS
        files = sorted(target.glob("*.md")) if target.is_dir() else []
    if not target.is_dir():
        hint = "/aidlc-docs" if layer == "docs" else "/aidlc-init"
        print(f"{target.relative_to(ROOT)} 가 없습니다. {hint} 을 먼저 실행하세요.")
        return 1
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
        print(f"{status}  {f.relative_to(base)}  ({len(hits)}개 미작성)")
        for lineno, label in hits[:50]:
            print(f"        L{lineno}: {{{{{label}}}}}")
    ok = total == 0 and not missing
    print(f"\nGATE {'PASS' if ok else 'FAIL'} — {layer} layer: 미작성 {total}개, 누락 문서 {len(missing)}개")
    return 0 if ok else 1


def load_catalog() -> dict:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    return {t["id"]: t for t in data["teams"]}


def _bullets(items) -> str:
    return "\n".join(f"- {x}" for x in items) if items else TBD


def team_fields(team: str, title: str | None, catalog: dict) -> dict:
    t = catalog.get(team, {})
    gate = t.get("review_gate")
    gate_txt = (f"- 대상: {gate['applies_to']}\n- 확인 항목:\n" + "\n".join(f"  - [ ] {c}" for c in gate["checks"])
                if gate else "- 없음 (리뷰 게이트를 운영하지 않는 팀)")
    return {
        "__TEAM_TITLE__": title or t.get("title") or team.upper(),
        "__TEAM__": team,
        "__GROUP__": t.get("group", "custom"),
        "__TIER__": t.get("tier", "custom"),
        "__MISSION__": t.get("mission", "(team-architect 가 작성)"),
        "__CREATE_WHEN__": t.get("create_when", "(카탈로그 밖 팀 — 40-team-composition.md 에 근거 기록)"),
        "__OWNS__": _bullets(t.get("owns")),
        "__NOT_OWNS__": _bullets(t.get("not_owns")),
        "__DELIVERABLES__": _bullets(t.get("deliverables")),
        "__INPUTS__": _bullets(t.get("inputs")),
        "__COLLAB__": _bullets(t.get("collaborates")),
        "__DOD__": "\n".join(f"- [ ] {x}" for x in t.get("dod", [])) or TBD,
        "__METRICS__": _bullets(t.get("metrics")),
        "__REVIEW_GATE__": gate_txt,
        "__GUIDANCE__": _bullets(t.get("guidance")),
    }


def render_team(team: str, title: str | None, catalog: dict) -> None:
    fields = team_fields(team, title, catalog)
    team_dir = WS / "teams" / team
    team_dir.mkdir(parents=True, exist_ok=True)
    targets = [(TEMPLATES / "team" / "charter.md", team_dir / "charter.md"),
               (TEMPLATES / "team" / "agent.md", ROOT / ".claude" / "agents" / f"team-{team}.md")]
    for src, dst in targets:
        if dst.exists():
            print(f"  exists  {dst.relative_to(ROOT)} (건너뜀)")
            continue
        text = src.read_text(encoding="utf-8")
        # __TEAM_TITLE__ 이 __TEAM__ 보다 먼저 치환되도록 긴 키부터
        for key in sorted(fields, key=len, reverse=True):
            text = text.replace(key, fields[key])
        dst.write_text(text, encoding="utf-8")
        print(f"  created {dst.relative_to(ROOT)}")


def cmd_teams(_: list[str]) -> int:
    catalog = load_catalog()
    groups = json.loads(CATALOG.read_text(encoding="utf-8"))["groups"]
    print(f"{'id':<12} {'tier':<12} {'그룹':<10} 팀 / 생성 조건")
    for t in catalog.values():
        gate = "  [리뷰 게이트]" if t.get("review_gate") else ""
        print(f"{t['id']:<12} {t['tier']:<12} {groups[t['group']]:<10} {t['title']}{gate}")
        print(f"{'':<36} └ {t['create_when']}")
    return 0


def cmd_new_team(args: list[str]) -> int:
    catalog = load_catalog()
    if args == ["--core"]:
        ids, title = [t["id"] for t in catalog.values() if t["tier"] == "core"], None
    elif len(args) == 2 and not TEAM_ID_RE.match(args[1]):
        ids, title = [args[0]], args[1]  # new-team <id> "<제목>"
    else:
        ids, title = args, None
    bad = [i for i in ids if not TEAM_ID_RE.match(i)]
    if not ids or bad:
        print("사용법: aidlc.py new-team <id...> | --core | <custom-id> \"<팀 제목>\"   (id: 소문자/숫자/-)")
        return 1
    for team in ids:
        if team not in catalog:
            print(f"  note    '{team}' 은 카탈로그에 없는 팀입니다 — 빈 항목은 team-architect 가 채워야 합니다.")
        render_team(team, title, catalog)
    return 0


def cmd_status(_: list[str]) -> int:
    hook = ROOT / "aidlc" / "hooks" / "memory_cascade.py"
    return subprocess.call([sys.executable, str(hook), "status"], stdin=subprocess.DEVNULL)


COMMANDS = {"init": cmd_init, "check": cmd_check, "teams": cmd_teams, "new-team": cmd_new_team, "status": cmd_status}

# ---- loop-* 서브커맨드 등록 블록 (backend 소유, contracts/loop-cli.md, ADR-004) ----------------
#   aidlc.py loop-start <N> | loop-check <done> | wait-resume [--max-wait <sec>] | loop-end <reason> [--done <n>]
# 인자 파싱·exit code(0/10/20/2/64/1)·stdout 한 줄은 loop_control.py 가 전부 맡는다.
LOOP_SUBCOMMANDS = ("loop-start", "loop-check", "wait-resume", "loop-end")


def _loop_command(sub: str):
    def run(args: list[str]) -> int:
        import importlib.util

        sys.dont_write_bytecode = True  # 저장소에 __pycache__ 를 만들지 않는다 (쓰기는 loop-status.json 하나)
        try:
            name = "aidlc_loop_control"
            spec = importlib.util.spec_from_file_location(name, Path(__file__).resolve().parent / "loop_control.py")
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module  # dataclass 가 모듈을 찾는다
            spec.loader.exec_module(module)
        except Exception as exc:  # 계약: 예외 종류만 stderr, exit 1 (경로·traceback 없음)
            print(f"aidlc-loop: unexpected error: {type(exc).__name__}", file=sys.stderr)
            return 1
        return module.main([sub, *args])

    return run


COMMANDS.update({sub: _loop_command(sub) for sub in LOOP_SUBCOMMANDS})
# ---- loop-* 등록 블록 끝 ------------------------------------------------------------------------


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] not in COMMANDS:
        print(__doc__)
        return 1
    return COMMANDS[argv[1]](argv[2:])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
