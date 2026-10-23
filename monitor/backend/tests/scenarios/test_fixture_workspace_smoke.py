"""가짜 workspace 빌더가 의도한 상태를 만드는지 확인한다 (T-003 smoke).

Hook 의 읽기 전용 함수(read_doc, Memory.phases/pending)로 "Hook 이 읽는 방식"과 맞는지도 본다.
"""

from __future__ import annotations

import importlib.util
import sys

import pytest
from fixtures import contracts
from fixtures.hashing import diff_manifests, hash_tree, tree_manifest
from fixtures.workspace import KINDS, build_workspace


def _load_hook():
    path = contracts.REPO_ROOT / "aidlc" / "hooks" / "memory_cascade.py"
    spec = importlib.util.spec_from_file_location("memory_cascade_under_test", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def hook():
    return _load_hook()


def test_unknown_kind_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        build_workspace(tmp_path, "nope")


def test_every_kind_builds_in_isolated_dirs(workspace_factory):
    roots = {kind: workspace_factory(kind).root for kind in KINDS}
    assert len(set(roots.values())) == len(KINDS)
    assert all(r.is_dir() for r in roots.values())


def test_empty_has_no_memory(empty_workspace):
    assert (empty_workspace.root / "workspace").is_dir()
    assert not empty_workspace.memory.exists()


def test_partial_has_only_stm_and_tasks(partial_workspace):
    names = sorted(p.name for p in partial_workspace.memory.iterdir())
    assert names == ["short-term.md", "tasks.md"]


def test_full_is_readable_by_hook_and_consistent(full_workspace, hook):
    mem = hook.Memory(full_workspace.root)
    assert mem.exists()
    stm, _ = hook.read_doc(mem.stm)
    assert stm["status"] == "active"
    assert mem.latest_seq() == 2
    assert mem.pending() is None  # LTM·Tasks·Plan 이 서로 맞는 정상 상태
    assert mem.phases() == {"P1": (7, 3), "P2": (5, 0)}  # 12개 중 7/5, P1 앞쪽 3개 완료


def test_task_count_100_variant(workspace_100_tasks, hook):
    phases = hook.Memory(workspace_100_tasks.root).phases()
    assert sum(total for total, _ in phases.values()) == 100


def test_closed_stm_is_closed_and_not_archived(closed_stm_workspace, hook):
    mem = hook.Memory(closed_stm_workspace.root)
    stm, _ = hook.read_doc(mem.stm)
    assert stm["status"] == "closed"
    # 아카이브는 건드리지 않았다. 조회 API 가 이 상태를 "처리"하면 해시가 달라진다 (CON-03)
    assert mem.latest_seq() == 2


def test_broken_has_intentional_breakage(broken_workspace):
    mem = broken_workspace.memory
    with pytest.raises(UnicodeDecodeError):
        (mem / "tasks.md").read_text(encoding="utf-8")
    assert (mem / "plan.md").read_bytes() == b""
    assert "\n---" not in (mem / "short-term.md").read_text(
        encoding="utf-8"
    )  # frontmatter 미종결


def test_hash_is_stable_and_detects_changes(full_workspace):
    root = full_workspace.root
    before = tree_manifest(root)
    before_hash = hash_tree(root)
    assert hash_tree(root) == before_hash  # 읽기만 하면 불변

    (root / "workspace" / "memory" / "plan.md").write_text("changed", encoding="utf-8")
    (root / "workspace" / "memory" / ".control.json").write_text("{}", encoding="utf-8")
    (root / "workspace" / "memory" / "archive" / "STM-0001_T-001.md").unlink()
    diff = diff_manifests(before, tree_manifest(root))
    assert diff.added == ["workspace/memory/.control.json"]
    assert diff.removed == ["workspace/memory/archive/STM-0001_T-001.md"]
    assert diff.changed == ["workspace/memory/plan.md"]
    assert hash_tree(root) != before_hash


def test_hash_exclude_prefix(full_workspace):
    root = full_workspace.root
    base = hash_tree(root, exclude=("workspace/memory/.monitor",))
    (root / "workspace" / "memory" / ".monitor").mkdir()
    (root / "workspace" / "memory" / ".monitor" / "x.json").write_text(
        "{}", encoding="utf-8"
    )
    assert hash_tree(root, exclude=("workspace/memory/.monitor",)) == base
    assert hash_tree(root) != base
