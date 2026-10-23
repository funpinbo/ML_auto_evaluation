"""GET /api/v1/memory — FR-003 AC-1~AC-14 (Hook `Memory.pending().level` 일치, ADR-009)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from backend_support import client_for, write_doc
from fixtures.hashing import hash_tree

NOW = datetime(2026, 10, 23, 11, 15, 33, tzinfo=UTC)


def _client(root: Path, now: datetime = NOW):
    return client_for(root, clock=lambda: now)


def _get(root: Path, now: datetime = NOW) -> dict:
    resp = _client(root, now).get("/api/v1/memory")
    assert resp.status_code == 200
    return resp.json()


def _mem(root: Path) -> Path:
    return root / "workspace" / "memory"


def _stm(root: Path, **meta: object) -> None:
    write_doc(_mem(root) / "short-term.md", meta)


def _hook_level(client, root: Path) -> str:
    app = client.app
    view = app.state.services.memory.loader.load(root).memory(root)
    return view.pending_level() or "none"


@pytest.fixture
def root(engine_workspace) -> Path:
    return engine_workspace("full").root


def test_ac1_active_stm(root: Path) -> None:
    _stm(root, status="active", task="T-004", team="product", outcome="none",
         opened_at="2026-10-23T09:52:33+00:00")  # fmt: skip
    stm = _get(root)["data"]["stm"]
    assert (stm["status"], stm["task"], stm["team"]) == ("active", "T-004", "product")
    assert stm["opened_at"] == "2026-10-23T09:52:33+00:00"
    assert stm["elapsed_sec"] == 83 * 60  # 1시간 23분


@pytest.mark.parametrize("seconds", [59, 60, 3600])
def test_ac2_elapsed_boundaries(root: Path, seconds: int) -> None:
    opened = datetime.fromtimestamp(NOW.timestamp() - seconds, UTC).isoformat()
    _stm(root, status="active", task="T-1", team="qa", opened_at=opened)
    assert _get(root)["data"]["stm"]["elapsed_sec"] == seconds


def test_ac3_idle(root: Path) -> None:
    _stm(root, status="idle", task="none", team="none")
    stm = _get(root)["data"]["stm"]
    assert stm["status"] == "idle" and stm["elapsed_sec"] is None


def test_ac4_closed_not_archived_readonly(engine_workspace) -> None:
    info = engine_workspace("closed_stm")
    before = hash_tree(info.root)
    archive_before = sorted(p.name for p in (info.memory / "archive").iterdir())
    body = _get(info.root)
    assert body["data"]["stm"]["status"] == "closed"
    assert body["data"]["stm"]["outcome"] == "done"
    assert hash_tree(info.root) == before
    assert sorted(p.name for p in (info.memory / "archive").iterdir()) == archive_before


def _sync(root: Path, *, ltm_rev: int, merged: int, synced: int, archives: int) -> None:
    mem = _mem(root)
    write_doc(mem / "long-term.md", {"rev": ltm_rev, "last_merged_stm": merged})
    tasks = (mem / "tasks.md").read_text(encoding="utf-8").split("---\n", 2)[2]
    write_doc(mem / "tasks.md", {"rev": 4, "synced_ltm_rev": synced}, tasks)
    for p in (mem / "archive").glob("STM-*.md"):
        p.unlink()
    for seq in range(1, archives + 1):
        write_doc(
            mem / "archive" / f"STM-{seq:04d}_T-{seq:03d}.md", {"status": "closed"}
        )


def test_ac5_synced_no_cascade(root: Path) -> None:
    _sync(root, ltm_rev=5, merged=5, synced=5, archives=5)
    data = _get(root)["data"]
    assert (data["ltm_rev"], data["last_merged_stm"], data["synced_ltm_rev"]) == (
        5,
        5,
        5,
    )
    assert data["pending_cascade"] == "none"
    assert data["archive_count"] == 5 and data["latest_archive_seq"] == 5


@pytest.mark.parametrize(
    ("ltm_rev", "merged", "synced", "archives", "plan_done", "expected"),
    [
        (5, 5, 5, 5, "[]", "none"),  # P1 미완료 Task 있음 → 3/3 없음
        (5, 4, 5, 5, "[]", "ltm"),  # AC-6
        (6, 5, 5, 5, "[]", "tasks"),  # AC-7
        (6, 4, 5, 5, "[]", "ltm"),  # AC-9 가장 아래 하나
    ],
)
def test_ac6_ac7_ac9_ac10_cascade_levels(
    root: Path, ltm_rev, merged, synced, archives, plan_done, expected
) -> None:
    _sync(root, ltm_rev=ltm_rev, merged=merged, synced=synced, archives=archives)
    write_doc(
        _mem(root) / "plan.md", {"current_phase": "P1", "completed_phases": plan_done}
    )
    client = _client(root)
    data = client.get("/api/v1/memory").json()["data"]
    assert data["pending_cascade"] == expected == _hook_level(client, root)


def test_ac8_cascade_plan(root: Path) -> None:
    _sync(root, ltm_rev=5, merged=5, synced=5, archives=5)
    write_doc(
        _mem(root) / "tasks.md",
        {"rev": 4, "synced_ltm_rev": 5},
        "## P1\n- [x] T-001 [qa] a\n",
    )
    write_doc(_mem(root) / "plan.md", {"current_phase": "P1", "completed_phases": "[]"})
    client = _client(root)
    assert client.get("/api/v1/memory").json()["data"]["pending_cascade"] == "plan"
    assert _hook_level(client, root) == "plan"


@pytest.mark.parametrize("kind", ["full", "partial", "closed_stm", "broken"])
def test_ac10_hook_equality_on_fixtures(engine_workspace, kind: str) -> None:
    info = engine_workspace(kind)
    client = _client(info.root)
    data = client.get("/api/v1/memory").json()["data"]
    try:
        expected = _hook_level(client, info.root)
    except Exception:  # noqa: BLE001 — Hook 도 못 읽는 경우
        expected = "unknown"
    assert data["pending_cascade"] == expected


@pytest.mark.parametrize(
    "opened",
    [
        None,
        "yesterday",
        "2026-10-23 09:00",
        "2026-10-23T09:00:00",
        "2027-01-01T00:00:00+00:00",
    ],
)
def test_ac12_bad_opened_at(root: Path, opened) -> None:
    meta = {"status": "active", "task": "T-004", "team": "qa"}
    if opened is not None:
        meta["opened_at"] = opened
    _stm(root, **meta)
    body = _get(root)
    assert body["data"]["stm"]["elapsed_sec"] is None
    assert body["data"]["stm"]["task"] == "T-004"
    assert body["meta"]["status"] == "partial" and len(body["meta"]["warnings"]) == 1


@pytest.mark.parametrize(
    "content", [b"---\nstatus: active\ntask: T-003\n", b"\xff\xfe\x00"]
)
def test_ac13_broken_stm_isolated(root: Path, content: bytes) -> None:
    (_mem(root) / "short-term.md").write_bytes(content)
    body = _get(root)
    assert body["meta"]["status"] == "partial"
    assert body["data"]["stm"]["status"] is None
    assert body["data"]["stm"]["error_code"] == "SOURCE_PARSE_ERROR"
    assert body["data"]["ltm_rev"] == 3


def test_ac14_ltm_rev_not_number(root: Path) -> None:
    write_doc(_mem(root) / "long-term.md", {"rev": "abc", "last_merged_stm": 2})
    body = _get(root)
    assert body["data"]["ltm_rev"] == 0
    assert body["meta"]["status"] == "partial"
    assert len(body["meta"]["warnings"]) == 1


def test_broken_workspace_all_values_isolated(engine_workspace) -> None:
    body = _get(engine_workspace("broken").root)
    assert body["meta"]["status"] == "partial"
    assert body["data"]["ltm_rev"] == 0  # "abc" → as_int 0


def test_empty_workspace_memory_dir_missing(engine_workspace) -> None:
    body = _get(engine_workspace("empty").root)
    assert body["meta"]["status"] == "empty" and body["data"] is None


def test_partial_workspace_missing_files_shown_as_null(engine_workspace) -> None:
    body = _get(engine_workspace("partial").root)
    data = body["data"]
    assert data["ltm_rev"] is None and data["current_phase"] is None
    assert data["stm"]["status"] == "idle"
    assert body["meta"]["status"] == "partial"


def test_stop_blocks_from_state_file(root: Path) -> None:
    (_mem(root) / ".cascade-state.json").write_text(
        '{"stop_blocks": 2}', encoding="utf-8"
    )
    assert _get(root)["data"]["stop_blocks"] == 2


def test_engine_missing_panel_error(workspace_factory) -> None:
    body = _get(workspace_factory("full").root)
    assert (
        body["meta"]["status"] == "error"
        and body["meta"]["error"]["code"] == "SOURCE_MISSING"
    )
