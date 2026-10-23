"""읽기 전용 보장 (CON-03, QS-07, ADR-009 Decision 2·5, D-07, W-01·W-03).

- 모든 조회 API 를 모든 qa workspace 종류(closed_stm 포함)에서 반복 호출해도 workspace 해시 불변.
- Hook 쓰기 함수(write_doc, reset_stm, archive_stm_if_closed, snapshot_stm, save_state, handle, main)를
  예외를 던지는 가짜로 바꾼 상태에서 모든 조회 API 가 정상 응답.
- 앱이 띄우는 서브프로세스는 `aidlc.py check <layer>` 뿐이고 `status` 는 0회.
- 엔진 로드가 `__pycache__` 를 만들지 않는다.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest
from backend_support import BACKEND_DIR, client_for
from fixtures.hashing import diff_manifests, hash_tree, tree_manifest

READ_APIS = (
    "/api/v1/pipeline",
    "/api/v1/plan",
    "/api/v1/tasks",
    "/api/v1/memory",
    "/api/v1/control",
)
WRITE_FUNCS = ("write_doc", "main", "handle")
WRITE_METHODS = ("reset_stm", "archive_stm_if_closed", "snapshot_stm", "save_state")


class HookWriteCalled(AssertionError):
    pass


def _raiser(name: str, calls: list[str] | None = None):
    def fake(*args, **kwargs):
        if calls is not None:
            calls.append(name)
        raise HookWriteCalled(name)

    return fake


@pytest.mark.parametrize("kind", ["empty", "partial", "full", "broken", "closed_stm"])
def test_workspace_hash_unchanged_for_all_read_apis(
    engine_workspace, kind: str
) -> None:
    info = engine_workspace(kind)
    before = tree_manifest(info.root)
    client = client_for(info.root)
    for _ in range(2):
        for path in READ_APIS:
            assert client.get(path).status_code == 200
        assert (
            client.get("/api/v1/tasks?status=open&team=qa&phase=P1").status_code == 200
        )
    after = tree_manifest(info.root)
    assert not diff_manifests(before, after), diff_manifests(before, after)
    assert not list(info.root.rglob("__pycache__"))


def test_closed_stm_not_archived_by_any_api(engine_workspace) -> None:
    info = engine_workspace("closed_stm")
    stm = (info.memory / "short-term.md").read_bytes()
    before = hash_tree(info.root)
    client = client_for(info.root)
    for path in READ_APIS:
        client.get(path)
    assert (info.memory / "short-term.md").read_bytes() == stm
    assert b"status: closed" in stm
    assert hash_tree(info.root) == before


@pytest.mark.parametrize("kind", ["empty", "partial", "full", "broken", "closed_stm"])
def test_hook_write_functions_replaced_by_raising_fakes(
    engine_workspace, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    """I-24: 패널 상태가 아니라 호출 기록으로 판정한다 — 어떤 workspace 종류에서도 0회."""
    info = engine_workspace(kind)
    client = client_for(info.root)
    module = client.app.state.services.memory.loader.load(info.root).module
    calls: list[str] = []
    for name in WRITE_FUNCS:
        monkeypatch.setattr(module, name, _raiser(name, calls))
    for name in WRITE_METHODS:
        monkeypatch.setattr(module.Memory, name, _raiser(name, calls))
    before = hash_tree(info.root)
    for _ in range(2):
        for path in READ_APIS:
            resp = client.get(path)
            assert resp.status_code == 200
    assert calls == []
    assert hash_tree(info.root) == before


def test_no_status_subprocess(
    engine_workspace, monkeypatch: pytest.MonkeyPatch
) -> None:
    info = engine_workspace("closed_stm")
    calls: list[list[str]] = []
    real_run = subprocess.run

    def spy_run(argv, *args, **kwargs):
        calls.append([str(a) for a in argv])
        return real_run(argv, *args, **kwargs)

    def no_popen(*args, **kwargs):  # run 외 경로로 서브프로세스를 띄우면 실패
        raise AssertionError("unexpected Popen")

    monkeypatch.setattr(subprocess, "run", spy_run)
    client = client_for(info.root)
    for path in READ_APIS:
        assert client.get(path).status_code == 200
    monkeypatch.setattr(subprocess, "Popen", no_popen)
    assert calls, "Gate 서브프로세스가 실행되어야 한다"
    for argv in calls:
        assert Path(argv[1]).name == "aidlc.py"
        assert argv[2] == "check" and argv[3] in ("user", "project", "docs")
        assert "status" not in argv


def test_app_source_never_references_hook_writes_or_status() -> None:
    """ADR-009 §2 코드 점검: 어댑터·서비스가 Hook 쓰기 함수 이름과 status 서브커맨드를 쓰지 않는다."""
    banned = re.compile(
        r"\b(write_doc|reset_stm|archive_stm_if_closed|snapshot_stm|save_state)\b"
        r"|\.handle\(|\.main\(|[\"']status[\"']\s*\]"
    )
    hits = []
    for path in sorted((BACKEND_DIR / "app").rglob("*.py")):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            code = line.split("#", 1)[0]
            if banned.search(code) and not code.strip().startswith(('"', "'")):
                hits.append(f"{path.name}:{lineno}")
    assert hits == []


def test_no_trusted_host_middleware_or_415() -> None:
    """privacy.md N-02·N-04 코드 점검."""
    text = "\n".join(
        p.read_text(encoding="utf-8") for p in (BACKEND_DIR / "app").rglob("*.py")
    )
    assert "TrustedHostMiddleware" not in text
    assert not re.search(r"\b415\b|HTTP_415|UNSUPPORTED_MEDIA_TYPE", text)
    assert "0.0.0.0" not in text
