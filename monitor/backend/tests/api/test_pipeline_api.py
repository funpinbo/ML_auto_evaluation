"""GET /api/v1/pipeline — FR-001 AC-1~AC-17 (D-21 단계 판정, A11 가정) + Gate 서브프로세스 계약."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest
from backend_support import client_for, install_engine, write_doc
from fixtures.hashing import hash_tree

from app.services.gates import RunOutput, subprocess_runner


def _run_init(root: Path) -> None:
    install_engine(root)
    subprocess.run(
        [sys.executable, str(root / "aidlc" / "scripts" / "aidlc.py"), "init"],
        check=True,
        capture_output=True,
        cwd=root,
    )


@pytest.fixture
def init_root(tmp_path: Path) -> Path:
    """`aidlc.py init` 직후와 같은 구성 (AC-2)."""
    root = tmp_path / "init-root"
    root.mkdir()
    _run_init(root)
    return root


def _get(root: Path, **kwargs) -> dict:
    resp = client_for(root, **kwargs).get("/api/v1/pipeline")
    assert resp.status_code == 200
    return resp.json()


def _states(body: dict) -> list[str]:
    return [s["state"] for s in body["data"]["stages"]]


def _gate(body: dict, layer: str) -> dict:
    return next(g for g in body["data"]["gates"] if g["layer"] == layer)


def _fill_user(root: Path) -> None:
    for p in (root / "workspace" / "user").glob("*.md"):
        p.write_text(f"# {p.stem}\n\n작성 완료\n", encoding="utf-8")


def _write_00(root: Path, decision: str) -> None:
    path = root / "workspace" / "project" / "00-interpretation.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"# 00\n\n## 1. 요약\n- 요약\n\n## 6. 분석 단계 진행 판단\n- 결정: {decision}\n",
        encoding="utf-8",
    )


def _tasks(root: Path, rev: int, lines: list[str], synced: int = 0) -> None:
    write_doc(
        root / "workspace" / "memory" / "tasks.md",
        {"rev": rev, "synced_ltm_rev": synced},
        "# Tasks\n\n" + "\n".join(lines) + "\n",
    )


def _stm(root: Path, status: str) -> None:
    write_doc(
        root / "workspace" / "memory" / "short-term.md",
        {"status": status, "task": "T-001", "team": "qa", "outcome": "none"},
    )


def _plan(root: Path, completed: str) -> None:
    write_doc(
        root / "workspace" / "memory" / "plan.md",
        {"current_phase": "P1", "completed_phases": completed},
    )


def test_ac1_empty_workspace_all_waiting(tmp_path: Path) -> None:
    root = tmp_path / "r"
    (root / "workspace").mkdir(parents=True)
    install_engine(root)
    body = _get(root)
    assert _states(body) == ["waiting"] * 7
    assert body["data"]["current_stage"] == 0
    assert body["data"]["next_command"] == "/aidlc-init"


def test_no_workspace_dir_is_empty_panel(tmp_path: Path) -> None:
    body = _get(tmp_path)
    assert body["meta"]["status"] == "empty"
    assert body["data"] is None
    assert any("aidlc-init" in w for w in body["meta"]["warnings"])


def test_ac2_after_init(init_root: Path) -> None:
    body = _get(init_root)
    assert _states(body) == ["done"] + ["waiting"] * 6
    user = _gate(body, "user")
    assert user["result"] == "FAIL"
    direct = subprocess.run(
        [sys.executable, str(init_root / "aidlc/scripts/aidlc.py"), "check", "user"],
        capture_output=True,
        text=True,
        cwd=init_root,
        check=False,
    )
    n = int(re.search(r"미작성 (\d+)개", direct.stdout).group(1))
    assert user["unwritten"] == n > 0
    assert body["data"]["current_stage"] == 1
    assert body["data"]["next_command"] == "/aidlc-interpret"


def test_ac3_partial_init(engine_workspace) -> None:
    info = engine_workspace("partial")  # short-term.md + tasks.md 만, user 없음
    assert _states(_get(info.root))[0] == "in_progress"


@pytest.mark.parametrize(
    "decision", ["**HOLD** — 보류", "{{GO / HOLD — 이유}}", "GOING", ""]
)
def test_ac4_interpret_not_go_in_progress(init_root: Path, decision: str) -> None:
    _fill_user(init_root)
    _write_00(init_root, decision)
    assert _states(_get(init_root))[1] == "in_progress"


def test_ac5_go_but_user_gate_fail(init_root: Path) -> None:
    _write_00(init_root, "**GO** — 이유")
    body = _get(init_root)
    assert _gate(body, "user")["result"] == "FAIL"
    assert _states(body)[1] == "in_progress"


def test_ac6_interpret_done(init_root: Path) -> None:
    _fill_user(init_root)
    _write_00(init_root, "**GO** — 이유")
    body = _get(init_root)
    assert _gate(body, "user")["result"] == "PASS"
    assert _states(body)[1] == "done"


def test_ac6_placeholder_in_00_blocks_done(init_root: Path) -> None:
    _fill_user(init_root)
    _write_00(init_root, "**GO** — {{이유}}")
    assert _states(_get(init_root))[1] == "in_progress"


def test_ac7_analysis(init_root: Path) -> None:
    proj = init_root / "workspace" / "project"
    proj.mkdir(parents=True, exist_ok=True)
    for n in ("10-business-analysis.md", "20-architecture-analysis.md"):
        (proj / n).write_text("# x\n", encoding="utf-8")
    assert _states(_get(init_root))[2] == "in_progress"
    (proj / "30-data-analysis.md").write_text("# x\n", encoding="utf-8")
    assert _states(_get(init_root))[2] == "done"


@pytest.mark.parametrize(
    ("teams", "charters", "expected"),
    [
        ("[product, qa]", ["product"], "in_progress"),
        ("[product, qa]", ["product", "qa"], "done"),
        ("[]", ["product"], "in_progress"),
    ],
)
def test_ac8_teams(
    init_root: Path, teams: str, charters: list[str], expected: str
) -> None:
    write_doc(init_root / "workspace/project/40-team-composition.md", {"teams": teams})
    for t in charters:
        write_doc(init_root / "workspace/teams" / t / "charter.md", {"team": t})
    assert _states(_get(init_root))[3] == expected


def test_ac8_charter_only_is_in_progress(init_root: Path) -> None:
    write_doc(init_root / "workspace/teams/qa/charter.md", {"team": "qa"})
    assert _states(_get(init_root))[3] == "in_progress"


def test_ac9_plan(init_root: Path) -> None:
    _tasks(
        init_root, 1, ["## P1 — x", "- [ ] T-001 [qa] a — FR-001 | deps: - | DoD: x"]
    )
    assert _states(_get(init_root))[4] == "done"
    _tasks(init_root, 1, ["## P1 — x"])
    assert _states(_get(init_root))[4] == "in_progress"


def test_r4_template_tasks_rev0_waiting(init_root: Path) -> None:
    assert _states(_get(init_root))[4] == "waiting"


def test_ac10_run_progress(init_root: Path) -> None:
    _tasks(init_root, 1, ["## P1", "- [x] T-001 [qa] a", "- [ ] T-002 [qa] b"])
    assert _states(_get(init_root))[5] == "in_progress"
    _tasks(init_root, 1, ["## P1", "- [ ] T-001 [qa] a"])
    _stm(init_root, "active")
    assert _states(_get(init_root))[5] == "in_progress"
    _stm(init_root, "idle")
    assert _states(_get(init_root))[5] == "waiting"


def test_ac11_run_done_boundary(init_root: Path) -> None:
    _tasks(init_root, 1, ["## P1", "- [x] T-001 [qa] a"])
    _stm(init_root, "idle")
    _plan(init_root, "[]")
    body = _get(init_root)
    assert _states(body)[5] == "in_progress"  # Memory.pending().level == "plan"
    _plan(init_root, "[P1]")
    body = _get(init_root)
    assert _states(body)[5] == "done"


def test_ac11_active_stm_blocks_run_done(init_root: Path) -> None:
    _tasks(init_root, 1, ["## P1", "- [x] T-001 [qa] a"])
    _plan(init_root, "[P1]")
    _stm(init_root, "active")
    assert _states(_get(init_root))[5] == "in_progress"


def test_ac12_docs(init_root: Path) -> None:
    (init_root / "docs" / "aidlc").mkdir(parents=True)
    (init_root / "docs" / "aidlc" / "README.md").write_text("# fw\n", encoding="utf-8")
    body = _get(init_root)
    docs = _gate(body, "docs")
    assert docs["result"] == "PASS" and docs["no_documents"] is True
    assert _states(body)[6] == "waiting"
    (init_root / "docs" / "README.md").write_text("# docs\n", encoding="utf-8")
    body = _get(init_root)
    assert _states(body)[6] == "done"
    guide = init_root / "docs" / "guide"
    guide.mkdir()
    (guide / "README.md").write_text("# g\n{{미작성}}\n", encoding="utf-8")
    body = _get(init_root)
    assert _gate(body, "docs")["result"] == "FAIL"
    assert _gate(body, "docs")["unwritten"] == 1
    assert _states(body)[6] == "in_progress"


def _complete_all(root: Path) -> None:
    _fill_user(root)
    _write_00(root, "**GO** — ok")
    proj = root / "workspace" / "project"
    for n in (
        "10-business-analysis.md",
        "20-architecture-analysis.md",
        "30-data-analysis.md",
    ):
        (proj / n).write_text("# x\n", encoding="utf-8")
    write_doc(proj / "40-team-composition.md", {"teams": "[qa]"})
    write_doc(root / "workspace/teams/qa/charter.md", {"team": "qa"})
    _tasks(root, 1, ["## P1", "- [x] T-001 [qa] a"])
    _plan(root, "[P1]")
    _stm(root, "idle")
    (root / "docs").mkdir(exist_ok=True)
    (root / "docs" / "README.md").write_text("# docs\n", encoding="utf-8")


def test_ac13_current_stage_and_all_done(init_root: Path) -> None:
    _complete_all(init_root)
    # 루트 템플릿과 같은 이름이 workspace/project 에 모두 있어야 project Gate 가 PASS 이지만,
    # 단계 판정은 project Gate 의 00 파일 수치만 쓴다.
    body = _get(init_root)
    assert _states(body) == ["done"] * 7, body["data"]
    assert body["data"]["all_done"] is True
    assert body["data"]["current_stage"] == 6
    assert body["data"]["next_command"] is None
    _stm(init_root, "active")
    body = _get(init_root)
    assert _states(body)[5] == "in_progress" and _states(body)[6] == "done"
    assert body["data"]["current_stage"] == 5
    assert body["data"]["next_command"] == "/aidlc-run"


@pytest.mark.parametrize("kind", ["full", "partial", "closed_stm", "empty"])
def test_ac14_gate_matches_direct_check(engine_workspace, kind: str) -> None:
    info = engine_workspace(kind)
    body = _get(info.root)
    for layer in ("user", "project", "docs"):
        direct = subprocess.run(
            [sys.executable, str(info.root / "aidlc/scripts/aidlc.py"), "check", layer],
            capture_output=True,
            text=True,
            cwd=info.root,
            check=False,
        )
        gate = _gate(body, layer)
        assert gate["result"] == ("PASS" if direct.returncode == 0 else "FAIL")
        m = re.search(
            r"GATE (PASS|FAIL) — .*미작성 (\d+)개, 누락 문서 (\d+)개", direct.stdout
        )
        if m:
            assert (gate["unwritten"], gate["missing"]) == (
                int(m.group(2)),
                int(m.group(3)),
            )
        else:
            assert gate["target_missing"] is True and gate["unwritten"] is None


def test_ac15_docs_missing_target(init_root: Path) -> None:
    gate = _gate(_get(init_root), "docs")
    assert gate["result"] == "FAIL" and gate["target_missing"] is True
    assert gate["unwritten"] is None and gate["missing"] is None


def test_ac15_gate_timeout_isolated(init_root: Path) -> None:
    def runner(argv, cwd, timeout):
        assert timeout == 10.0
        if argv[-1] == "user":
            raise subprocess.TimeoutExpired(argv, timeout)
        return subprocess_runner(argv, cwd, timeout)

    body = _get(init_root, gate_runner=runner)
    user = _gate(body, "user")
    assert user["result"] == "UNKNOWN" and user["error_code"] == "GATE_TIMEOUT"
    assert _gate(body, "project")["result"] in ("PASS", "FAIL")
    states = _states(body)
    assert states[0] == "done"
    assert body["meta"]["status"] == "partial"


def test_gate_timeout_makes_interpret_unknown(init_root: Path) -> None:
    _fill_user(init_root)
    _write_00(init_root, "**GO** — ok")

    def runner(argv, cwd, timeout):
        if argv[-1] == "user":
            raise subprocess.TimeoutExpired(argv, timeout)
        return subprocess_runner(argv, cwd, timeout)

    assert _states(_get(init_root, gate_runner=runner))[1] == "unknown"


def test_ac16_broken_tasks_only_stages_4_5_unknown(engine_workspace) -> None:
    info = engine_workspace("full")
    tasks = info.memory / "tasks.md"
    tasks.write_bytes(tasks.read_bytes() + b"\n\xff\xfe broken\n")
    body = _get(info.root)
    states = _states(body)
    assert states[4] == "unknown" and states[5] == "unknown"
    assert states[0] != "unknown" and states[2] != "unknown"
    assert body["meta"]["status"] == "partial"
    assert len(body["meta"]["warnings"]) >= 1


def test_broken_workspace_never_500(engine_workspace) -> None:
    info = engine_workspace("broken")
    body = _get(info.root)
    assert body["meta"]["status"] in ("partial", "ok")


def test_engine_missing_stages_4_5_unknown(workspace_factory) -> None:
    info = workspace_factory("full")  # 엔진 복사 안 함
    body = _get(info.root)
    states = _states(body)
    assert states[4] == "unknown" and states[5] == "unknown"
    assert any("엔진" in w for w in body["meta"]["warnings"])
    assert all(g["error_code"] == "SOURCE_MISSING" for g in body["data"]["gates"])


def test_ac17_closed_stm_readonly(engine_workspace) -> None:
    info = engine_workspace("closed_stm")
    before = hash_tree(info.root)
    stm_before = (info.memory / "short-term.md").read_bytes()
    client = client_for(info.root)
    for _ in range(3):
        assert client.get("/api/v1/pipeline").status_code == 200
    assert hash_tree(info.root) == before
    assert (info.memory / "short-term.md").read_bytes() == stm_before


def test_gate_runner_receives_check_only(init_root: Path) -> None:
    calls: list[list[str]] = []

    def runner(argv, cwd, timeout):
        calls.append(list(argv))
        return RunOutput(0, "\nGATE PASS — x layer: 미작성 0개, 누락 문서 0개\n")

    _get(init_root, gate_runner=runner)
    assert len(calls) == 3
    for argv in calls:
        assert argv[0] == sys.executable
        assert argv[2] == "check" and argv[3] in ("user", "project", "docs")
        assert "status" not in argv
