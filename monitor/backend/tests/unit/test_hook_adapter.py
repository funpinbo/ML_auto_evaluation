"""Hook 어댑터 (ADR-009 §1·§3): 허용 목록, 로드 실패 처리, 깨진 파일 분류, 바이트코드 미기록."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from backend_support import REPO_ROOT

from app.services.aidlc_reader import (
    ALLOWED_ATTRS,
    EngineUnavailable,
    HookLoader,
    SourceProblem,
)


def _root(tmp_path: Path, source: str | None = None) -> Path:
    hook = tmp_path / "aidlc" / "hooks" / "memory_cascade.py"
    hook.parent.mkdir(parents=True)
    if source is None:
        shutil.copy2(REPO_ROOT / "aidlc" / "hooks" / "memory_cascade.py", hook)
    else:
        hook.write_text(source, encoding="utf-8")
    return tmp_path


def test_loads_real_hook_without_pycache(tmp_path: Path) -> None:
    root = _root(tmp_path)
    loader = HookLoader()
    engine = loader.load(root)
    assert loader.load(root) is engine  # mtime 같으면 캐시
    assert all(hasattr(engine.module, a) for a in ALLOWED_ATTRS)
    assert not (root / "aidlc" / "hooks" / "__pycache__").exists()


@pytest.mark.parametrize(
    "source", [None, "raise RuntimeError('x')\n", "x = 1\n", "def (:\n"]
)
def test_unavailable_engine(tmp_path: Path, source: str | None) -> None:
    if source is None:
        root = tmp_path  # 파일 없음
    else:
        root = _root(tmp_path, source)
    with pytest.raises(EngineUnavailable):
        HookLoader().load(root)


def test_read_doc_classification(tmp_path: Path) -> None:
    engine = HookLoader().load(_root(tmp_path))
    ok = tmp_path / "ok.md"
    ok.write_text("---\nrev: 3\nteams: [a, b]\n---\nbody\n", encoding="utf-8")
    doc = engine.read_doc(ok)
    assert doc.meta == {"rev": 3, "teams": ["a", "b"]} and doc.body == "body\n"
    assert engine.read_doc(tmp_path / "missing.md").meta == {}
    unterminated = tmp_path / "u.md"
    unterminated.write_text("---\nrev: 1\n", encoding="utf-8")
    binary = tmp_path / "b.md"
    binary.write_bytes(b"\xff\xfe\x00")
    for path in (unterminated, binary):
        with pytest.raises(SourceProblem) as caught:
            engine.read_doc(path)
        assert caught.value.code.value == "SOURCE_PARSE_ERROR"
    folder = tmp_path / "dir.md"
    folder.mkdir()
    assert engine.read_doc(folder).meta == {}  # Hook: is_file() 아니면 빈 문서
    assert engine.as_int("abc") == 0 and engine.as_int("7") == 7


def test_memory_view_wraps_decode_errors(tmp_path: Path) -> None:
    root = _root(tmp_path)
    mem = root / "workspace" / "memory"
    mem.mkdir(parents=True)
    (mem / "tasks.md").write_bytes(b"---\nrev: 1\n---\n\xff")
    view = HookLoader().load(root).memory(root)
    with pytest.raises(SourceProblem):
        view.phases()
    with pytest.raises(SourceProblem):
        view.pending_level()
    assert view.archived_count() == 0 and view.latest_seq() == 0
    assert view.load_state() == {}
    assert view.exists() is False
