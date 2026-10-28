#!/usr/bin/env python3
"""DS-01 (workspace/memory), DS-02 (aidlc.py status/check), DS-05 (teams) 프로파일러.

- DS-01 은 Hook 엔진(aidlc/hooks/memory_cascade.py)의 **읽기 전용** 함수(read_doc, Memory.phases,
  Memory.archived, Memory.pending)를 그대로 재사용해 Hook 과 동일한 규칙으로 판정한다.
- DS-02 는 sys.executable 로 서브프로세스 실행, exit code·소요 시간·출력 줄 형식을 집계한다.
  실행 전후 workspace/ 파일 해시를 비교해 읽기 전용인지 확인한다(00 해석서 A17).
사용법: python3 profile_workspace.py <repo_root>
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "aidlc" / "hooks"))
import memory_cascade as mc  # noqa: E402

TASK_RE = re.compile(r"^\s*[-*]\s+\[( |x|X)\]\s+(T-\d+)\s+\[([a-z][a-z0-9-]*)\]\s+(.*)$")
ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?")
CHECK_LINE_RE = re.compile(r"^(OK|FAIL|MISSING|WARN)\s+(\S+)(?:\s+\((\d+)개 미작성\))?")
GATE_RE = re.compile(r"^GATE (PASS|FAIL) — (\w+) layer: 미작성 (\d+)개, 누락 문서 (\d+)개")


def tree_hash(p: Path) -> str:
    h = hashlib.sha256()
    for f in sorted(p.rglob("*")):
        if f.is_file():
            h.update(str(f.relative_to(p)).encode())
            h.update(f.read_bytes())
    return h.hexdigest()[:16]


def profile_memory() -> dict:
    mem = mc.Memory(ROOT)
    out: dict = {"exists": mem.exists(), "files": {}}
    for name, p in (("plan", mem.plan), ("tasks", mem.tasks), ("long-term", mem.ltm), ("short-term", mem.stm)):
        meta, body = mc.read_doc(p)
        out["files"][name] = {
            "bytes": p.stat().st_size if p.is_file() else None,
            "frontmatter": meta,
            "frontmatter_types": {k: type(v).__name__ for k, v in meta.items()},
            "body_lines": len(body.splitlines()),
            "h2_sections": [l[3:].strip() for l in body.splitlines() if l.startswith("## ")],
        }
    stm = out["files"]["short-term"]["frontmatter"]
    out["stm_opened_at_iso"] = bool(ISO_RE.match(str(stm.get("opened_at", ""))))
    out["stm_none_values"] = [k for k, v in stm.items() if str(v) == "none"]
    # tasks 체크박스와 Task 형식 적합도
    _, body = mc.read_doc(mem.tasks)
    cb, fmt_ok, teams = 0, 0, {}
    outside_phase = 0
    current = None
    for line in body.splitlines():
        if mc.PHASE_RE.match(line):
            current = mc.PHASE_RE.match(line).group(1)
            continue
        if line.startswith("## "):
            current = None
            continue
        if mc.CHECKBOX_RE.match(line):
            cb += 1
            if current is None:
                outside_phase += 1
            m = TASK_RE.match(line)
            if m:
                fmt_ok += 1
                teams[m.group(3)] = teams.get(m.group(3), 0) + 1
    out["tasks"] = {"phases_hook": {k: {"total": t, "checked": c} for k, (t, c) in mem.phases().items()},
                    "checkbox_lines": cb, "format_conformant": fmt_ok, "outside_phase_checkboxes": outside_phase,
                    "team_tags": teams}
    out["archive"] = {"dir_exists": mem.archive.is_dir(), "stm_count": len(mem.archived()),
                      "snapshots": len(list(mem.snapshots.glob("*.md"))) if mem.snapshots.is_dir() else 0}
    out["cascade_state_file"] = mem.state_file.is_file()
    step = mem.pending()
    out["pending_cascade"] = step.level if step else None
    out["control_file_exists"] = (mem.dir / ".control.json").is_file()
    return out


def run_cli(args: list[str]) -> dict:
    t = time.perf_counter()
    p = subprocess.run([sys.executable, str(ROOT / "aidlc" / "scripts" / "aidlc.py"), *args],
                       cwd=ROOT, capture_output=True, text=True)
    sec = time.perf_counter() - t
    lines = p.stdout.splitlines()
    parsed = {"exit": p.returncode, "sec": round(sec, 3), "stdout_lines": len(lines), "stderr_lines": len(p.stderr.splitlines())}
    if args[0] == "check":
        items = [CHECK_LINE_RE.match(l) for l in lines]
        items = [m for m in items if m]
        parsed["items"] = [{"state": m.group(1), "doc": m.group(2), "placeholders": int(m.group(3)) if m.group(3) else None} for m in items]
        g = next((GATE_RE.match(l) for l in lines if GATE_RE.match(l)), None)
        parsed["gate"] = {"result": g.group(1), "placeholders": int(g.group(3)), "missing": int(g.group(4))} if g else None
        parsed["unparsed_nonblank"] = sum(1 for l in lines if l.strip() and not CHECK_LINE_RE.match(l) and not GATE_RE.match(l))
    else:
        parsed["kv_lines"] = sum(1 for l in lines if l.startswith("- "))
    return parsed


def profile_teams() -> dict:
    tdir = ROOT / "workspace" / "teams"
    cat = ROOT / "aidlc" / "teams" / "catalog.json"
    n_cat = None
    if cat.is_file():
        data = json.loads(cat.read_text(encoding="utf-8"))
        teams = data.get("teams", data) if isinstance(data, dict) else data
        n_cat = len(teams)
    return {"teams_dir_exists": tdir.is_dir(),
            "charters": len(list(tdir.glob("*/charter.md"))) if tdir.is_dir() else 0,
            "team_composition_doc": (ROOT / "workspace" / "project" / "40-team-composition.md").is_file(),
            "team_agents": len(list((ROOT / ".claude" / "agents").glob("team-*.md"))),
            "catalog_teams": n_cat}


def main() -> int:
    before = tree_hash(ROOT / "workspace" / "memory")
    cli = {" ".join(a): run_cli(a) for a in (["status"], ["check", "user"], ["check", "project"], ["check", "docs"])}
    after = tree_hash(ROOT / "workspace" / "memory")
    res = {"ds01_memory": profile_memory(), "ds02_cli": cli,
           "ds02_memory_unchanged_by_cli": before == after, "ds05_teams": profile_teams()}
    Path(__file__).with_name("summary_workspace.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
