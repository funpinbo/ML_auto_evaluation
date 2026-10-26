"""S-10 읽기 전용 (CON-03, QS-07, ADR-009 Decision 2): 조회·SSE 전후 workspace 해시가 같다.

- 실서버: closed STM 포함 workspace 를 실제 서버로 전수 조회하고 SSE 를 연결해도 파일이 바뀌지 않는다.
- 인프로세스: Hook 의 쓰기 함수 7종을 호출 즉시 예외를 던지는 가짜로 바꾼 채 모든 조회·이벤트 허브 tick 이 성공한다.
  (기록으로 판정한다: 삼켜진 예외도 `calls` 에 남는다.)
"""

from __future__ import annotations

import asyncio

import pytest
from fixtures.endpoints import ALL_GETS
from fixtures.engine import install_engine
from fixtures.hashing import diff_manifests, hash_tree, tree_manifest
from fixtures.live_server import live_server
from guardrail_support import WORKSPACE_KINDS, app_client

MODULE_FUNCTIONS = ("write_doc", "main", "handle")
MEMORY_METHODS = ("reset_stm", "archive_stm_if_closed", "snapshot_stm", "save_state")


@pytest.mark.parametrize("kind", ["closed_stm", "full", "broken"])
def test_live_server_leaves_workspace_untouched(
    kind, workspace_factory, claude_home_factory, tmp_path
) -> None:
    workspace = workspace_factory(kind)
    install_engine(workspace.root)
    home = claude_home_factory(workspace.root).home
    before = tree_manifest(workspace.root)
    stm_before = (workspace.memory / "short-term.md").read_bytes()

    with live_server(workspace.root, home, tmp_path) as server:
        for _ in range(2):
            for path in ALL_GETS:
                assert server.client.get(path).status_code < 500, path
        for frame in server.sse_frames():  # 연결만 하고 첫 프레임을 받은 뒤 닫는다
            if frame.startswith(("event: ready", "event: warming")):
                break

    assert not diff_manifests(before, tree_manifest(workspace.root))
    assert (workspace.memory / "short-term.md").read_bytes() == stm_before
    assert not list(workspace.root.rglob("__pycache__"))


@pytest.mark.parametrize("kind", WORKSPACE_KINDS)
def test_hook_write_functions_never_called_by_queries(
    kind, workspace_factory, claude_home_factory, monkeypatch
) -> None:
    workspace = workspace_factory(kind)
    client = app_client(workspace, claude_home_factory(workspace.root).home)
    module = client.app.state.services.memory.loader.load(workspace.root).module
    calls: list[str] = []

    def exploding(name: str):
        def fake(*args, **kwargs):
            calls.append(name)
            raise AssertionError(f"Hook 쓰기 함수 호출: {name}")

        return fake

    for name in MODULE_FUNCTIONS:
        monkeypatch.setattr(module, name, exploding(name))
    for name in MEMORY_METHODS:
        monkeypatch.setattr(module.Memory, name, exploding(name))

    before = hash_tree(workspace.root)
    hub = client.app.state.events
    for _ in range(2):
        for path in ALL_GETS:
            assert client.get(path).status_code < 500, path
        asyncio.run(hub.step((None, None)))  # SSE 허브의 tick (watcher.poll + refresh)
    assert calls == []
    assert hash_tree(workspace.root) == before
