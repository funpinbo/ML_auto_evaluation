"""상태 스냅샷 리더 (ADR-003 §4, contracts/README §3, FR-004 AC-3~AC-8)."""

from __future__ import annotations

import json
import os
from datetime import timedelta

import pytest
from fixtures.contracts import is_valid
from fixtures.jsonl_gen import FIXED_NOW
from fixtures.runtime_files import (
    INVALID_DIR_NAMES,
    SNAPSHOT_KINDS,
    claude_status_doc,
    write_claude_status,
    write_json,
)

from app.services.statusline_reader import (
    MAX_SNAPSHOT_BYTES,
    StatuslineReader,
    parse_snapshot,
)


@pytest.fixture
def reader(tmp_path):
    (tmp_path / "workspace" / "memory").mkdir(parents=True)
    return StatuslineReader(tmp_path)


@pytest.mark.parametrize("kind", SNAPSHOT_KINDS)
def test_fixture_kinds(reader, kind: str) -> None:
    write_claude_status(reader.path, kind, transcript_dir_name="-home-fake-project")
    snap = reader.read()
    expected = {"none": "missing", "broken": "broken"}.get(kind, "ok")
    assert snap.state == expected
    if kind == "normal":
        assert snap.five_hour is not None and snap.five_hour.used_percentage == 23.5
        assert snap.seven_day is not None and snap.seven_day.used_percentage == 41
        assert (
            snap.total_cost_usd == 0.12
            and snap.transcript_dir_name == "-home-fake-project"
        )
        assert not snap.stale(FIXED_NOW)
    if kind == "no_rate_limits":
        assert not snap.rate_limits_present and snap.five_hour is None
    if kind == "stale":
        assert snap.stale(FIXED_NOW)


def test_stale_boundary_600_vs_601() -> None:
    for age, stale in ((600, False), (601, True)):
        doc = claude_status_doc("normal", now=FIXED_NOW)
        doc["captured_at"] = (FIXED_NOW - timedelta(seconds=age)).isoformat()
        assert is_valid(doc, "claude-status")
        assert parse_snapshot(doc).stale(FIXED_NOW) is stale


@pytest.mark.parametrize("name", INVALID_DIR_NAMES)
def test_invalid_hint_is_dropped_even_if_rest_is_fine(reader, name: str) -> None:
    doc = claude_status_doc("normal", transcript_dir_name=name)
    write_json(reader.path, doc)
    snap = reader.read()
    assert snap.state == "ok" and snap.transcript_dir_name is None
    assert reader.hint() is None


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.update(schema=2),
        lambda d: d.update(schema=True),
        lambda d: d.update(captured_at="yesterday"),
        lambda d: d.pop("captured_at"),
    ],
)
def test_schema_mismatch_is_broken(reader, mutate) -> None:
    doc = claude_status_doc("normal")
    mutate(doc)
    write_json(reader.path, doc)
    assert reader.read().state == "broken"


def test_not_an_object_and_oversize(reader) -> None:
    reader.path.parent.mkdir(parents=True, exist_ok=True)
    reader.path.write_text("[1, 2]", encoding="utf-8")
    assert reader.read().state == "broken"
    reader.path.write_bytes(b" " * (MAX_SNAPSHOT_BYTES + 1))
    assert reader.read().state == "broken"


def test_directory_in_place_is_unreadable(reader) -> None:
    reader.path.mkdir(parents=True)
    assert reader.read().state == "unreadable"


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="FIFO 없음")
def test_fifo_does_not_block(reader) -> None:
    reader.path.parent.mkdir(parents=True, exist_ok=True)
    os.mkfifo(reader.path)
    assert reader.read().state == "unreadable"


def test_tolerant_field_values() -> None:
    doc = claude_status_doc("normal")
    doc["rate_limits"]["five_hour"] = {"used_percentage": 150, "resets_at": -5}
    doc["rate_limits"]["seven_day"] = None
    doc["cost"] = "x"
    doc["context_window"] = {
        "used_percentage": float("nan"),
        "context_window_size": True,
    }
    snap = parse_snapshot(json.loads(json.dumps(doc, allow_nan=True)))
    assert snap.state == "ok"
    assert snap.five_hour is not None and snap.five_hour.used_percentage is None
    assert snap.five_hour.resets_at is None and snap.seven_day is None
    assert snap.total_cost_usd is None and snap.context_used_percentage is None
    assert snap.context_window_size is None


def test_symlink_and_hardlink_snapshot_are_unreadable(reader, tmp_path) -> None:
    src = tmp_path / "elsewhere.json"
    write_json(src, claude_status_doc("normal"))
    reader.path.parent.mkdir(parents=True, exist_ok=True)
    os.symlink(src, reader.path)
    assert reader.read().state == "unreadable"
    reader.path.unlink()
    os.link(src, reader.path)
    assert reader.read().state == "unreadable"
