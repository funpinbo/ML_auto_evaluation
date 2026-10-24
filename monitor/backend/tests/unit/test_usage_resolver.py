"""프로젝트 디렉터리 해석 — 규칙 → 힌트(재검증) → cwd 폴백, 직속 하위 경계 (D-13, privacy P-25~P-28, S-09)."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import pytest
from fixtures import markers
from fixtures.contracts import CONTRACTS_DIR
from fixtures.jsonl_gen import FIXED_NOW
from fixtures.runtime_files import INVALID_DIR_NAMES, VALID_DIR_NAMES
from usage_support import make_collector, usage_line, write_jsonl

from app.services.usage import resolver
from app.services.usage.resolver import (
    DIR_NAME_PATTERN,
    HintProblem,
    ResolveSource,
    encode_project_path,
    resolve_project_dir,
    valid_dir_name,
)

NOW = FIXED_NOW.timestamp()


def _resolve(home: Path, repo: Path, hint: str | None = None, scan: bool = True):
    return resolve_project_dir(home, repo, hint, now=NOW, allow_cwd_scan=scan)


def test_pattern_is_the_contract_pattern() -> None:
    schema = json.loads(
        (CONTRACTS_DIR / "claude-status.schema.json").read_text(encoding="utf-8")
    )
    assert DIR_NAME_PATTERN == schema["properties"]["transcript_dir_name"]["pattern"]


@pytest.mark.parametrize("name", VALID_DIR_NAMES)
def test_valid_names(name: str) -> None:
    assert valid_dir_name(name)


@pytest.mark.parametrize("name", INVALID_DIR_NAMES)
def test_invalid_names(name: str) -> None:
    assert not valid_dir_name(name)


def test_encoded_rule_first(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    home = tmp_path / "home"
    enc = home / "projects" / encode_project_path(repo.resolve())
    enc.mkdir(parents=True)
    (home / "projects" / "other").mkdir()
    res = _resolve(home, repo, hint="other")
    assert res.source is ResolveSource.encoded and res.path == enc.resolve()


def test_encoded_rule_case_insensitive(tmp_path) -> None:
    repo = tmp_path / "Repo"
    repo.mkdir()
    home = tmp_path / "home"
    enc = home / "projects" / encode_project_path(repo.resolve()).lower()
    enc.mkdir(parents=True)
    res = _resolve(home, repo)
    assert res.source is ResolveSource.encoded and res.path == enc.resolve()


def test_hint_used_when_rule_fails(tmp_path) -> None:
    home = tmp_path / "home"
    (home / "projects" / "-home-fake-project").mkdir(parents=True)
    res = _resolve(home, tmp_path, hint="-home-fake-project")
    assert res.source is ResolveSource.hint and res.hint_problem is None


@pytest.mark.parametrize("name", INVALID_DIR_NAMES)
def test_invalid_hints_are_ignored(tmp_path, name: str) -> None:
    home = tmp_path / "home"
    (home / "projects").mkdir(parents=True)
    (home / "projects" / "real").mkdir()
    res = _resolve(home, tmp_path / "nope", hint=name, scan=False)
    assert res.path is None and res.hint_problem is HintProblem.INVALID_NAME


def test_hint_symlink_outside_is_rejected(
    claude_home, full_workspace, symlink_escape
) -> None:
    res = _resolve(
        claude_home.home,
        full_workspace.root,
        hint=symlink_escape.dir_link_name,
        scan=False,
    )
    assert res.path is None and res.hint_problem is HintProblem.OUTSIDE_PROJECTS


def test_hint_symlink_to_sibling_inside_projects_is_allowed(tmp_path) -> None:
    home = tmp_path / "home"
    real = home / "projects" / "real"
    real.mkdir(parents=True)
    os.symlink(real, home / "projects" / "alias", target_is_directory=True)
    res = _resolve(home, tmp_path, hint="alias", scan=False)
    assert res.path == real.resolve()


def test_hint_file_or_missing(tmp_path) -> None:
    home = tmp_path / "home"
    (home / "projects").mkdir(parents=True)
    (home / "projects" / "afile").write_text("x", encoding="utf-8")
    assert (
        _resolve(home, tmp_path, "afile", scan=False).hint_problem
        is HintProblem.OUTSIDE_PROJECTS
    )
    assert (
        _resolve(home, tmp_path, "gone", scan=False).hint_problem
        is HintProblem.NOT_FOUND
    )


def test_no_projects_dir(tmp_path) -> None:
    res = _resolve(tmp_path / "none", tmp_path, hint="x")
    assert res.path is None


def test_cwd_fallback_uses_usage_lines_only(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    home = tmp_path / "home"
    projects = home / "projects"
    # 1) usage 없는 줄의 cwd 는 보지 않는다 (사전 필터 통과분만)
    write_jsonl(projects / "a-dir" / "s.jsonl", [{"type": "user", "cwd": str(repo)}])
    assert _resolve(home, repo).path is None
    # 2) usage 줄의 cwd 가 같으면 그 디렉터리
    write_jsonl(
        projects / "b-dir" / "s.jsonl", [usage_line("r1", cwd=str(repo) + os.sep)]
    )
    res = _resolve(home, repo)
    assert (
        res.source is ResolveSource.cwd and res.path == (projects / "b-dir").resolve()
    )


def test_cwd_fallback_skips_symlinked_and_invalid_dirs(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    home = tmp_path / "home"
    outside = tmp_path / "outside"
    write_jsonl(outside / "s.jsonl", [usage_line("r1", cwd=str(repo))])
    (home / "projects").mkdir(parents=True)
    os.symlink(outside, home / "projects" / "link", target_is_directory=True)
    write_jsonl(
        home / "projects" / "bad name" / "s.jsonl", [usage_line("r1", cwd=str(repo))]
    )
    write_jsonl(
        home / "projects" / "old" / "s.jsonl",
        [usage_line("r1", cwd=str(repo))],
        mtime=FIXED_NOW.replace(month=8),
    )
    assert _resolve(home, repo).path is None


def test_collector_logs_codes_without_values(tmp_path, caplog) -> None:
    home = tmp_path / "home"
    (home / "projects").mkdir(parents=True)
    bad = f"../{markers.DIR_NAME}\n"
    col = make_collector(home, tmp_path / "repo", hint=bad)
    with caplog.at_level(logging.INFO, logger="aidlc_monitor"):
        col.ensure_fresh()
        col.refresh(force=True)
    assert "기록 폴더 힌트를 무시했습니다: HINT_INVALID_NAME" in caplog.text
    assert caplog.text.count("HINT_INVALID_NAME") == 1  # 같은 문제는 한 번만
    assert "기록 폴더를 찾지 못했습니다" in caplog.text
    markers.assert_no_markers(caplog.text, extra=(str(tmp_path), "../"))


def test_collector_found_log_names_source_only(
    claude_home, full_workspace, caplog
) -> None:
    col = make_collector(
        claude_home.home, full_workspace.root, hint=claude_home.dir_name
    )
    with caplog.at_level(logging.INFO, logger="aidlc_monitor"):
        col.ensure_fresh()
    assert "사용량 기록 폴더를 찾았습니다 (hint)" in caplog.text
    markers.assert_no_markers(caplog.text, extra=claude_home.forbidden_strings())


def test_cwd_scan_is_rate_limited(tmp_path, monkeypatch) -> None:
    calls: list[int] = []
    real = resolver._scan_cwd

    def spy(*a, **k):
        calls.append(1)
        return real(*a, **k)

    monkeypatch.setattr(resolver, "_scan_cwd", spy)
    now = [0.0]
    col = make_collector(tmp_path / "home", tmp_path, monotonic=lambda: now[0])
    col.ensure_fresh()
    col.refresh(force=True)
    assert len(calls) == 1
    now[0] += 61
    col.refresh(force=True)
    assert len(calls) == 2


def test_iter_jsonl_never_yields_links(claude_home, symlink_escape) -> None:
    """탐색 단계에서 symlink 파일·디렉터리를 따라가지 않는다 (열기 단계 검사와 별개인 1차 방어)."""
    names = {e.name for e in resolver.iter_jsonl(claude_home.project_dir)}
    assert names, "탐색 결과가 비면 검사가 무의미"
    assert not names & {"linked.jsonl", "creds-link.jsonl", "leak.jsonl"}
    assert any(
        "subagents" in e.path for e in resolver.iter_jsonl(claude_home.project_dir)
    )


# ---------------------------------------------------------------- 안전 열기 (security 리뷰 조치: 폴백도 같은 검사)
def _spy_open(monkeypatch) -> list[str]:
    opened: list[str] = []
    real = os.open

    def spy(path, *a, **k):
        opened.append(os.path.basename(os.fspath(path)))
        return real(path, *a, **k)

    monkeypatch.setattr(os, "open", spy)
    return opened


def test_cwd_fallback_never_opens_hardlinks_or_fifos(tmp_path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    home = tmp_path / "home"
    creds = home / ".credentials.json"
    creds.parent.mkdir(parents=True)
    creds.write_text(json.dumps({"token": markers.CREDENTIAL}), encoding="utf-8")
    other = home / "projects" / "other-proj"
    other.mkdir(parents=True)
    outside = write_jsonl(tmp_path / "outside.jsonl", [usage_line("r1", cwd=str(repo))])
    try:
        os.link(creds, other / "s.jsonl")  # decoy 자격 증명 하드 링크
        os.link(outside, other / "hard.jsonl")  # cwd 가 맞는 밖 파일 하드 링크
    except OSError as exc:
        pytest.skip(f"하드 링크를 만들 수 없음: {type(exc).__name__}")
    if hasattr(os, "mkfifo"):
        os.mkfifo(other / "fifo.jsonl")
    opened = _spy_open(monkeypatch)
    res = _resolve(home, repo)
    assert res.path is None, "하드 링크 파일의 cwd 로 해석하면 안 된다"
    assert res.skipped_files == 2
    assert not {"s.jsonl", "hard.jsonl", "fifo.jsonl", ".credentials.json"} & set(
        opened
    )


def test_collector_logs_fallback_skips_as_count(tmp_path, caplog) -> None:
    home = tmp_path / "home"
    other = home / "projects" / "other"
    other.mkdir(parents=True)
    src = write_jsonl(tmp_path / "x.jsonl", [usage_line("r1", cwd=str(tmp_path))])
    try:
        os.link(src, other / "s.jsonl")
    except OSError as exc:
        pytest.skip(f"하드 링크를 만들 수 없음: {type(exc).__name__}")
    col = make_collector(home, tmp_path / "repo")
    with caplog.at_level(logging.WARNING, logger="aidlc_monitor"):
        col.ensure_fresh()
    assert (
        "하드 링크·일반 파일 아님·경계 밖 기록 파일 1개를 건너뛰었습니다" in caplog.text
    )
    assert str(tmp_path) not in caplog.text


def test_open_regular_rules(tmp_path, monkeypatch) -> None:
    from app.services.usage import safe_open

    ok = tmp_path / "ok.jsonl"
    ok.write_text("x\n", encoding="utf-8")
    opened = safe_open.open_regular(ok)
    assert opened is not None
    os.close(opened[0])
    other = tmp_path / "other.jsonl"
    other.write_text("y\n", encoding="utf-8")
    assert safe_open.open_regular(ok, expect=os.stat(other)) is None  # 다른 파일
    os.symlink(ok, tmp_path / "sym.jsonl")
    assert safe_open.open_regular(tmp_path / "sym.jsonl") is None
    assert safe_open.open_regular(tmp_path) is None
    assert safe_open.open_regular(tmp_path / "missing") is None
    if hasattr(os, "mkfifo"):
        os.mkfifo(tmp_path / "f.jsonl")
        assert safe_open.open_regular(tmp_path / "f.jsonl") is None
    os.link(other, tmp_path / "hl.jsonl")
    assert (
        safe_open.open_regular(other) is None
        and safe_open.open_regular(tmp_path / "hl.jsonl") is None
    )
    # lstat 뒤 열기 전에 symlink 로 바뀜 → O_NOFOLLOW 가 막는다
    swapped = tmp_path / "swap.jsonl"
    swapped.write_text("z\n", encoding="utf-8")
    real_lstat = os.lstat

    def lstat_then_swap(path, *a, **k):
        st = real_lstat(path, *a, **k)
        if os.fspath(path) == str(swapped):
            swapped.unlink()
            os.symlink(ok, swapped)
        return st

    monkeypatch.setattr(safe_open.os, "lstat", lstat_then_swap)
    assert safe_open.open_regular(swapped) is None
    monkeypatch.undo()
    # fstat 결과가 다른 inode 이면 닫고 거부 (fd 누수 없음)
    closed: list[int] = []
    real_close = os.close
    monkeypatch.setattr(safe_open.os, "fstat", lambda fd: real_lstat(other))
    monkeypatch.setattr(
        safe_open.os, "close", lambda fd: (closed.append(fd), real_close(fd))
    )
    assert safe_open.open_regular(ok) is None and len(closed) == 1
