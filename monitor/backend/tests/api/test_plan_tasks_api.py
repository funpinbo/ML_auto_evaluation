"""GET /api/v1/plan, /api/v1/tasks — FR-002 AC-1~AC-16 (Hook `Memory.phases()` 일치, ADR-009 §4)."""

from __future__ import annotations

from pathlib import Path

import pytest
from backend_support import assert_error, client_for, write_doc


def _engine(app_client):
    app = app_client.app
    return app.state.services.tasks.loader.load(app.settings.aidlc_root)


def _tasks(root: Path, lines: list[str], rev: int = 1) -> None:
    write_doc(
        root / "workspace" / "memory" / "tasks.md",
        {"rev": rev, "synced_ltm_rev": 0},
        "# Tasks\n\n" + "\n".join(lines) + "\n",
    )


def _stm(root: Path, status: str, task: str, outcome: str = "none") -> None:
    write_doc(
        root / "workspace" / "memory" / "short-term.md",
        {"status": status, "task": task, "team": "backend", "outcome": outcome},
    )


def _line(i: int, done: bool = False, team: str = "qa") -> str:
    return f"- [{'x' if done else ' '}] T-{i:03d} [{team}] task {i} — FR-00{i % 9 + 1} | deps: T-000 | DoD: x"


@pytest.fixture
def root(engine_workspace) -> Path:
    return engine_workspace("full").root


def test_ac1_phase_counts_match_hook(root: Path) -> None:
    _tasks(
        root,
        ["## P1 — MVP", *[_line(i, i <= 3) for i in range(1, 6)], "## P2 — ops",
         *[_line(i) for i in range(6, 10)]],
    )  # fmt: skip
    client = client_for(root)
    body = client.get("/api/v1/plan").json()
    phases = {p["phase"]: p for p in body["data"]["phases"]}
    assert (
        phases["P1"]["checked"],
        phases["P1"]["total"],
        phases["P1"]["percent"],
    ) == (3, 5, 60)
    assert (
        phases["P2"]["checked"],
        phases["P2"]["total"],
        phases["P2"]["percent"],
    ) == (0, 4, 0)
    assert phases["P1"]["title"] == "MVP"
    hook = _engine(client).memory(root).phases()
    assert {k: (v["total"], v["checked"]) for k, v in phases.items()} == hook


@pytest.mark.parametrize("task_count", [12, 100])
def test_ac2_hook_equality_fixtures(engine_workspace, task_count: int) -> None:
    info = engine_workspace("full", task_count=task_count)
    client = client_for(info.root)
    body = client.get("/api/v1/plan").json()
    got = {p["phase"]: (p["total"], p["checked"]) for p in body["data"]["phases"]}
    assert got == _engine(client).memory(info.root).phases()
    tasks = client.get("/api/v1/tasks").json()["data"]
    assert tasks["total"] == sum(t for t, _ in got.values()) == len(tasks["items"])


def test_ac2_variant_tasks_md(root: Path) -> None:
    _tasks(
        root,
        ["## P1", "* [X] T-001 [qa] star bullet", "  - [x] T-002 [qa] indented", "- [ ]no space",
         "- [ ] T-003 [qa] ok", "## Notes", "- [x] T-004 [qa] outside", "## P2 extra words",
         "- [ ] T-005 [qa] p2", "## P1", "- [x] T-006 [qa] P1 again"],
    )  # fmt: skip
    client = client_for(root)
    got = {
        p["phase"]: (p["total"], p["checked"])
        for p in client.get("/api/v1/plan").json()["data"]["phases"]
    }
    assert got == _engine(client).memory(root).phases()


@pytest.mark.parametrize(
    ("checked", "total", "pct"), [(2, 3, 66), (99, 100, 99), (100, 100, 100)]
)
def test_ac3_floor_percent(root: Path, checked: int, total: int, pct: int) -> None:
    _tasks(root, ["## P1", *[_line(i, i <= checked) for i in range(1, total + 1)]])
    phase = client_for(root).get("/api/v1/plan").json()["data"]["phases"][0]
    assert phase["percent"] == pct


def test_ac4_phase_without_tasks(root: Path) -> None:
    _tasks(root, ["## P1", _line(1), "## P3 — 빈 Phase"])
    resp = client_for(root).get("/api/v1/plan")
    assert resp.status_code == 200
    p3 = next(p for p in resp.json()["data"]["phases"] if p["phase"] == "P3")
    assert (p3["total"], p3["checked"], p3["percent"]) == (0, 0, 0)


def test_ac5_backlog_excluded(root: Path) -> None:
    _tasks(root, ["## P1", _line(1), "## Backlog", _line(2), _line(3)])
    client = client_for(root)
    phases = client.get("/api/v1/plan").json()["data"]["phases"]
    assert [(p["phase"], p["total"]) for p in phases] == [("P1", 1)]
    ids = [t["id"] for t in client.get("/api/v1/tasks").json()["data"]["items"]]
    assert ids == ["T-001"]


def test_ac6_list_matches_source_order(root: Path) -> None:
    lines = [
        "## P1",
        _line(3, True, "backend"),
        _line(1),
        "## P2",
        _line(2, False, "frontend"),
    ]
    _tasks(root, lines)
    items = client_for(root).get("/api/v1/tasks").json()["data"]["items"]
    assert [
        (t["id"], t["team"], t["title"], t["checked"], t["phase"]) for t in items
    ] == [
        ("T-003", "backend", "task 3", True, "P1"),
        ("T-001", "qa", "task 1", False, "P1"),
        ("T-002", "frontend", "task 2", False, "P2"),
    ]
    assert items[0]["refs"] == ["FR-004"] and items[0]["deps"] == ["T-000"]


def test_ac7_active_task(root: Path) -> None:
    _tasks(root, ["## P1", _line(4), _line(5)])
    _stm(root, "active", "T-004")
    items = client_for(root).get("/api/v1/tasks").json()["data"]["items"]
    assert [t["status"] for t in items] == ["active", "open"]


def test_ac8_blocked_section_and_stm_outcome(root: Path) -> None:
    _tasks(
        root,
        [
            "## P1",
            _line(4),
            _line(9),
            "## Blocked",
            "- T-009 — blocker 설명 — 해소 조건",
        ],
    )
    _stm(root, "active", "T-004", "blocked")
    items = client_for(root).get("/api/v1/tasks").json()["data"]["items"]
    assert {t["id"]: t["status"] for t in items} == {
        "T-004": "blocked",
        "T-009": "blocked",
    }


def test_ac9_done_wins_over_blocked(root: Path) -> None:
    _tasks(root, ["## P1", _line(2, True), "## Blocked", "- T-002 — still listed"])
    items = client_for(root).get("/api/v1/tasks").json()["data"]["items"]
    assert items[0]["status"] == "done"


def test_ac10_team_filter(root: Path) -> None:
    _tasks(
        root, ["## P1", _line(1, team="backend"), _line(2), _line(3, team="backend")]
    )
    client = client_for(root)
    items = client.get("/api/v1/tasks?team=backend").json()["data"]["items"]
    assert [t["id"] for t in items] == ["T-001", "T-003"]
    resp = client.get("/api/v1/tasks?team=nosuchteam")
    assert resp.status_code == 200 and resp.json()["data"]["items"] == []


def test_ac11_status_filter_and_enum(root: Path) -> None:
    _tasks(root, ["## P1", _line(1, True), _line(2)])
    client = client_for(root)
    items = client.get("/api/v1/tasks?status=done").json()["data"]["items"]
    assert [t["id"] for t in items] == ["T-001"]
    assert_error(client.get("/api/v1/tasks?status=foo"), 422, "VALIDATION_ERROR")


def test_ac12_combined_filters(root: Path) -> None:
    _tasks(
        root,
        ["## P1", _line(1), _line(2, True), _line(3, team="ops"), "## P2", _line(4)],
    )
    items = (
        client_for(root)
        .get("/api/v1/tasks?team=qa&status=open&phase=P1")
        .json()["data"]["items"]
    )
    assert [t["id"] for t in items] == ["T-001"]


def test_ac13_malformed_line(root: Path) -> None:
    _tasks(
        root, ["## P1", "- [ ] 아무 형식 없는 줄", "- [ ] T-007 팀 태그 없음", _line(1)]
    )
    client = client_for(root)
    assert client.get("/api/v1/plan").json()["data"]["phases"][0]["total"] == 3
    items = client.get("/api/v1/tasks").json()["data"]["items"]
    assert items[0] == {
        "id": None, "team": None, "title": "아무 형식 없는 줄", "refs": [], "deps": [],
        "phase": "P1", "checked": False, "status": "open", "well_formed": False,
    }  # fmt: skip
    assert items[1]["id"] == "T-007" and items[1]["team"] is None
    assert items[1]["well_formed"] is False and items[2]["well_formed"] is True
    assert (
        client.get("/api/v1/tasks?team=qa").json()["data"]["items"][0]["id"] == "T-001"
    )


@pytest.mark.parametrize(
    "content",
    [
        b"---\nrev: 1\n## P1\n- [ ] T-001 [qa] x\n",
        b"---\nrev: 1\n---\n## P1\n" + b"\xff\xfe",
    ],
)
def test_ac14_broken_tasks_md_error(root: Path, content: bytes) -> None:
    (root / "workspace/memory/tasks.md").write_bytes(content)
    client = client_for(root)
    for path in ("/api/v1/plan", "/api/v1/tasks"):
        resp = client.get(path)
        assert resp.status_code == 200
        meta = resp.json()["meta"]
        assert (
            meta["status"] == "error" and meta["error"]["code"] == "SOURCE_PARSE_ERROR"
        )
    assert client.get("/api/v1/memory").status_code == 200


def test_ac15_tasks_missing_empty(root: Path) -> None:
    (root / "workspace/memory/tasks.md").unlink()
    for path in ("/api/v1/plan", "/api/v1/tasks"):
        body = client_for(root).get(path).json()
        assert body["meta"]["status"] == "empty"
        assert any("/aidlc-plan" in w for w in body["meta"]["warnings"])


@pytest.mark.parametrize(
    "plan_bytes", [None, b"", b"---\ncurrent_phase: P1\n", b"\xff\xfe"]
)
def test_ac16_plan_missing_or_broken_partial(
    root: Path, plan_bytes: bytes | None
) -> None:
    plan = root / "workspace/memory/plan.md"
    if plan_bytes is None:
        plan.unlink()
    else:
        plan.write_bytes(plan_bytes)
    body = client_for(root).get("/api/v1/plan").json()
    assert body["meta"]["status"] == "partial" and body["meta"]["warnings"]
    assert (
        body["data"]["current_phase"] is None
        and body["data"]["completed_phases"] is None
    )
    assert body["data"]["phases"]


def test_plan_current_and_completed(root: Path) -> None:
    _tasks(root, ["## P1", _line(1, True), "## P2", _line(2)])
    write_doc(
        root / "workspace/memory/plan.md",
        {"current_phase": "P2", "completed_phases": "[P1]"},
    )
    data = client_for(root).get("/api/v1/plan").json()["data"]
    assert data["current_phase"] == "P2" and data["completed_phases"] == ["P1"]
    assert [(p["completed"], p["current"]) for p in data["phases"]] == [
        (True, False),
        (False, True),
    ]


def test_stm_broken_tasks_partial_without_active(root: Path) -> None:
    _tasks(root, ["## P1", _line(3)])
    (root / "workspace/memory/short-term.md").write_bytes(
        b"---\nstatus: active\ntask: T-003\n"
    )
    body = client_for(root).get("/api/v1/tasks").json()
    assert body["meta"]["status"] == "partial"
    assert body["data"]["items"][0]["status"] == "open"


def test_duplicate_ids_kept_with_warning(root: Path) -> None:
    _tasks(root, ["## P1", _line(1), _line(1)])
    body = client_for(root).get("/api/v1/tasks").json()
    assert len(body["data"]["items"]) == 2 and body["meta"]["warnings"]


def test_empty_and_missing_workspace(engine_workspace, tmp_path: Path) -> None:
    info = engine_workspace("empty")
    assert (
        client_for(info.root).get("/api/v1/tasks").json()["meta"]["status"] == "empty"
    )
    assert (
        client_for(tmp_path / "nothing").get("/api/v1/plan").json()["meta"]["status"]
        == "empty"
    )


def test_engine_missing_is_panel_error(workspace_factory) -> None:
    info = workspace_factory("full")
    body = client_for(info.root).get("/api/v1/tasks").json()
    assert body["meta"]["status"] == "error"
    assert body["meta"]["error"]["code"] == "SOURCE_MISSING"
