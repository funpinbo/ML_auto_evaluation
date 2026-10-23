"""가짜 JSONL 생성기·CLAUDE_HOME 구성 smoke (T-003).

생성기 기대값을 독립 구현(reference_parser)으로 교차 검증하고, 결정성과 표식 문자열 존재,
경계 입력 포함 여부, 실제 홈 비참조를 확인한다.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from fixtures import markers
from fixtures.claude_home import build_claude_home, encode_project_path
from fixtures.contracts import is_valid
from fixtures.hashing import hash_tree
from fixtures.jsonl_gen import GIANT_LINE_BYTES, TOKEN_KEYS, write_project_jsonl
from fixtures.reference_parser import aggregate

SMALL = {"days": 6, "responses_per_day": 5, "subagent_every": 2}


def test_generation_is_deterministic(tmp_path):
    a = write_project_jsonl(tmp_path / "a", **SMALL)
    b = write_project_jsonl(tmp_path / "b", **SMALL)
    assert [p.relative_to(tmp_path / "a") for p in a.files] == [
        p.relative_to(tmp_path / "b") for p in b.files
    ]
    assert hash_tree(tmp_path / "a") == hash_tree(tmp_path / "b")
    assert a.expected_buckets == b.expected_buckets


def test_different_seed_changes_output(tmp_path):
    write_project_jsonl(tmp_path / "a", seed=1, **SMALL)
    write_project_jsonl(tmp_path / "b", seed=2, **SMALL)
    assert hash_tree(tmp_path / "a") != hash_tree(tmp_path / "b")


def test_body_markers_are_present_in_generated_files(tmp_path):
    write_project_jsonl(tmp_path / "p", **SMALL)
    text = "\n".join(
        p.read_text(encoding="utf-8", errors="replace")
        for p in (tmp_path / "p").rglob("*.jsonl")
    )
    missing = [
        m
        for m in (
            markers.BODY,
            markers.TOOL,
            markers.PATH,
            markers.CWD,
            markers.SESSION,
            markers.UUID,
            markers.REQUEST_ID,
            markers.EXTRA,
        )
        if m not in text
    ]
    assert missing == []


def test_edge_case_lines_are_included(tmp_path):
    m = write_project_jsonl(tmp_path / "p", **SMALL)
    for key in (
        "duplicate_lines",
        "no_usage_lines",
        "usage_string_only_lines",
        "invalid_usage_lines",
        "broken_lines",
        "no_request_id_lines",
        "truncated_tail_lines",
    ):
        assert m.counts[key] > 0, key
    assert len(m.truncated_files) == 1 and not m.truncated_files[
        0
    ].read_bytes().endswith(b"\n")
    assert len(m.expired_files) == 1
    assert any("subagents" in p.parts for p in m.files)
    assert (
        max(len(line) for p in m.files for line in p.read_bytes().split(b"\n"))
        >= GIANT_LINE_BYTES
    )


def test_without_edge_cases_only_clean_lines(tmp_path):
    m = write_project_jsonl(tmp_path / "p", edge_cases=False, **SMALL)
    assert m.counts["broken_lines"] == m.counts["invalid_usage_lines"] == 0
    assert not m.truncated_files and not m.expired_files


def test_duplicate_ratio_is_close_to_eda(tmp_path):
    """30 EDA: usage 줄의 약 58% 가 중복 requestId. 기본값이 그 규모에 가까운지 본다."""
    m = write_project_jsonl(
        tmp_path / "p", days=30, responses_per_day=40, edge_cases=False
    )
    share = m.counts["duplicate_lines"] / m.counts["usage_lines"]
    assert 0.40 < share < 0.75


def test_expected_buckets_match_independent_reference(tmp_path):
    m = write_project_jsonl(tmp_path / "p", **SMALL)
    buckets, counts = aggregate(tmp_path / "p")
    assert buckets == m.expected_buckets
    for key in (
        "usage_lines",
        "duplicate_lines",
        "no_usage_lines",
        "usage_string_only_lines",
        "invalid_usage_lines",
        "broken_lines",
        "no_request_id_lines",
        "truncated_tail_lines",
    ):
        assert counts[key] == m.counts[key], key
    assert sum(t.responses for t in buckets.values()) == m.unique_responses


def test_false_positive_and_giant_lines_do_not_leak_into_totals(tmp_path):
    m = write_project_jsonl(tmp_path / "p", **SMALL)
    totals = m.expected_totals
    assert all(
        getattr(totals, k) < markers.FALSE_POSITIVE_TOKENS * 10 for k in TOKEN_KEYS
    )
    buckets, _ = aggregate(tmp_path / "p")
    assert not any(
        t.output_tokens >= markers.FALSE_POSITIVE_TOKENS for t in buckets.values()
    )


def test_sidechain_buckets_come_from_subagent_files(tmp_path):
    m = write_project_jsonl(tmp_path / "p", edge_cases=False, **SMALL)
    assert any(key[2] for key in m.expected_buckets)
    assert any(not key[2] for key in m.expected_buckets)


def test_timestamps_are_utc_and_within_window(tmp_path, fixed_now):
    m = write_project_jsonl(tmp_path / "p", edge_cases=False, **SMALL)
    hours = sorted(k[0] for k in m.expected_buckets)
    assert all(h.endswith("Z") for h in hours)
    assert hours[-1] <= fixed_now.strftime("%Y-%m-%dT%H:00:00Z")


def test_file_mtimes_follow_content(tmp_path, fixed_now):
    m = write_project_jsonl(tmp_path / "p", **SMALL)
    assert all(p.stat().st_mtime <= fixed_now.timestamp() for p in m.files)
    assert m.expired_files[0].stat().st_mtime < fixed_now.timestamp() - 30 * 86400


def test_body_pad_scales_file_size(tmp_path):
    small = write_project_jsonl(tmp_path / "s", edge_cases=False, **SMALL)
    big = write_project_jsonl(tmp_path / "b", edge_cases=False, body_pad=2000, **SMALL)
    assert big.bytes_written > small.bytes_written * 3


def test_claude_home_layout_and_decoys(full_workspace, claude_home):
    assert claude_home.dir_name.startswith(encode_project_path(full_workspace.root))
    assert claude_home.project_dir.parent == claude_home.projects_dir
    assert json.loads(claude_home.settings_file.read_text(encoding="utf-8"))[
        "statusLine"
    ]["command"]
    assert (
        (claude_home.home / ".credentials.json")
        .read_text(encoding="utf-8")
        .count(markers.CREDENTIAL)
    )
    assert claude_home.manifest is not None and claude_home.manifest.files


def test_claude_home_without_project_dir(full_workspace, claude_home_factory):
    home = claude_home_factory(full_workspace.root, with_jsonl=False)
    assert home.projects_dir.is_dir() and not home.project_dir.exists()
    assert home.manifest is None


def test_snapshot_transcript_dir_name_matches_schema(app_env):
    doc = json.loads(app_env.workspace.claude_status_file.read_text(encoding="utf-8"))
    assert doc["transcript_dir_name"] == app_env.claude_home.dir_name
    assert is_valid(doc, "claude-status")


def test_forbidden_strings_cover_markers_and_paths(claude_home):
    forbidden = claude_home.forbidden_strings()
    assert markers.BODY in forbidden and claude_home.dir_name in forbidden
    assert str(claude_home.home) in forbidden


def test_symlink_escape_cases(claude_home, symlink_escape):
    root = claude_home.project_dir.resolve()
    assert symlink_escape.file_link.is_symlink()
    assert not symlink_escape.file_link.resolve().is_relative_to(root)
    assert (
        symlink_escape.dir_link.resolve().parent != claude_home.projects_dir.resolve()
    )
    assert not symlink_escape.subdir_link.resolve().is_relative_to(root)
    # 상대 링크로 CLAUDE_HOME 안의 decoy 자격 증명을 가리킨다: 홈 안이지만 프로젝트 밖
    creds = symlink_escape.credentials_link
    assert creds.is_symlink() and not Path(os.readlink(creds)).is_absolute()
    assert creds.resolve() == (claude_home.home / ".credentials.json").resolve()
    assert creds.resolve().is_relative_to(claude_home.home.resolve())
    assert not creds.resolve().is_relative_to(root)
    assert markers.CREDENTIAL in creds.read_text(encoding="utf-8")
    # 오라클은 이탈 파일을 건너뛰어, 기대값이 symlink 추가 전과 같아야 한다
    buckets, _ = aggregate(claude_home.project_dir)
    assert buckets == claude_home.manifest.expected_buckets
    assert markers.ESCAPE in symlink_escape.outside_file.read_text(encoding="utf-8")


def test_no_real_home_is_used(_isolate_home, monkeypatch):
    assert Path.home() == _isolate_home
    assert "pytest" in str(_isolate_home) or "fake_home" in str(_isolate_home)
    assert not (_isolate_home / ".claude").exists()
    assert "CLAUDE_CONFIG_DIR" not in os.environ


def test_app_env_injects_paths(app_env):
    import os

    assert Path(os.environ["AIDLC_ROOT"]) == app_env.workspace.root
    assert Path(os.environ["CLAUDE_HOME"]) == app_env.claude_home.home
    assert Path(os.environ["CLAUDE_HOME"]).parent.parent.name != ".claude"


def test_without_app_env_variables_are_cleared():
    import os

    assert "AIDLC_ROOT" not in os.environ and "CLAUDE_HOME" not in os.environ


def test_marker_helpers():
    assert markers.find_markers("clean", b"clean") == []
    assert markers.find_markers(f"x {markers.BODY} y") == [markers.BODY]
    with pytest.raises(AssertionError) as info:
        markers.assert_no_markers(f"leak {markers.PATH}", where="resp")
    message = str(info.value)
    assert "PATH" in message and markers.PATH not in message and "leak" not in message


def test_assert_no_markers_reports_only_labels_and_indices(claude_home):
    forbidden = claude_home.forbidden_strings()
    leaked = f"{claude_home.dir_name} {claude_home.project_dir} {markers.BODY}"
    with pytest.raises(AssertionError) as info:
        markers.assert_no_markers(leaked, extra=forbidden, where="resp")
    message = str(info.value)
    assert "BODY" in message and "DIR_NAME" in message
    assert "extra[" in message  # dir_name·경로는 인덱스로만
    for value in forbidden:
        assert value not in message
    assert str(claude_home.home) not in message


def test_marker_labels_cover_all_markers():
    assert set(markers.MARKER_LABELS) == set(markers.ALL_MARKERS)
    assert len(set(markers.MARKER_LABELS.values())) == len(markers.ALL_MARKERS)


def test_build_claude_home_rejects_nothing_outside_tmp(tmp_path, full_workspace):
    home = build_claude_home(
        tmp_path / "x", full_workspace.root, days=2, responses_per_day=2
    )
    assert tmp_path in home.home.parents
