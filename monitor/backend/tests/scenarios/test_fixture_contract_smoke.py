"""fixture 가 만드는 런타임 파일이 계약 스키마를 통과하는지 확인한다 (T-003 smoke).

스키마 `format` 은 비강제라 `pattern` 만 검증된다. 음성 케이스도 실제로 실행해
스키마가 거부하는지 본다 (LTM 패턴).
"""

from __future__ import annotations

import json
from datetime import datetime

import pytest
from fixtures.contracts import CONTRACTS_DIR, SCHEMA_NAMES, is_valid, schema_errors
from fixtures.runtime_files import (
    INVALID_DIR_NAMES,
    LOOP_SCENARIOS,
    SNAPSHOT_KINDS,
    VALID_DIR_NAMES,
    claude_status_doc,
    control_doc,
    loop_status_doc,
    write_claude_status,
)


@pytest.mark.parametrize("name", SCHEMA_NAMES)
def test_schema_examples_are_valid(name):
    schema = json.loads(
        (CONTRACTS_DIR / f"{name}.schema.json").read_text(encoding="utf-8")
    )
    for example in schema["examples"]:
        assert schema_errors(example, name) == []


@pytest.mark.parametrize("state", ["running", "pause"])
def test_control_doc_is_valid(state):
    assert schema_errors(control_doc(state, seq=3), "control") == []


def test_control_doc_rejects_short_pause_limit():
    assert not is_valid(control_doc(max_pause_sec=599), "control")


@pytest.mark.parametrize("scenario", LOOP_SCENARIOS)
def test_loop_status_scenarios_are_valid(scenario):
    assert schema_errors(loop_status_doc(scenario), "loop-status") == []


def test_loop_status_scenarios_cover_fr005_states():
    states = {s: loop_status_doc(s) for s in LOOP_SCENARIOS}
    assert states["paused"]["state"] == "paused" and states["paused"]["paused_since"]
    assert states["resumed"]["paused_since"] is None
    assert states["pause_timeout"]["ended_reason"] == "pause_timeout"
    assert states["pause_timeout"][
        "paused_since"
    ]  # 2시간 초과 종료는 paused_since 를 유지한다


def test_loop_status_schema_rejects_inconsistent_state():
    bad = loop_status_doc("running") | {"paused_since": "2026-10-23T08:00:00+00:00"}
    assert not is_valid(bad, "loop-status")


@pytest.mark.parametrize(
    "kind", [k for k in SNAPSHOT_KINDS if k not in ("none", "broken")]
)
def test_claude_status_snapshots_are_valid(kind):
    assert (
        schema_errors(
            claude_status_doc(kind, transcript_dir_name="-home-user-x"), "claude-status"
        )
        == []
    )


def test_snapshot_variants_differ_as_documented(fixed_now):
    assert claude_status_doc("normal")["rate_limits"] is not None
    assert claude_status_doc("no_rate_limits")["rate_limits"] is None
    captured = datetime.fromisoformat(claude_status_doc("stale")["captured_at"])
    assert (fixed_now - captured).total_seconds() > 600  # SNAPSHOT_STALE 기준


def test_snapshot_none_and_broken_files(tmp_path):
    missing = write_claude_status(tmp_path / "none.json", "none")
    assert not missing.exists()
    broken = write_claude_status(tmp_path / "broken.json", "broken")
    with pytest.raises(json.JSONDecodeError):
        json.loads(broken.read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", VALID_DIR_NAMES)
def test_transcript_dir_name_accepts_valid(name):
    assert is_valid(
        claude_status_doc("normal", transcript_dir_name=name), "claude-status"
    )


@pytest.mark.parametrize("name", INVALID_DIR_NAMES, ids=lambda n: repr(n)[:30])
def test_transcript_dir_name_rejects_invalid(name):
    assert not is_valid(
        claude_status_doc("normal", transcript_dir_name=name), "claude-status"
    )


def test_snapshot_schema_rejects_forbidden_extra_keys():
    doc = claude_status_doc("normal") | {"transcript_path": "/x", "cwd": "/y"}
    assert not is_valid(doc, "claude-status")
