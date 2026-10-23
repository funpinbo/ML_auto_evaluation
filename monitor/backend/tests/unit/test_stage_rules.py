"""FR-001 판정 보조 규칙 (3값 논리, R3 GO 판정, 경과 시간)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.services.memory import elapsed_seconds, parse_rfc3339
from app.services.pipeline import all3, any3, decision_of, stage_state


def test_three_valued_logic() -> None:
    assert (
        all3(True, True) is True
        and all3(True, None) is None
        and all3(None, False) is False
    )
    assert (
        any3(False, True) is True and any3(False, None) is None and any3(False) is False
    )


@pytest.mark.parametrize(
    ("done", "started", "state"),
    [(True, None, "done"), (None, True, "unknown"), (False, True, "in_progress"),
     (False, None, "unknown"), (False, False, "waiting")],
)  # fmt: skip
def test_stage_state(done, started, state) -> None:
    assert stage_state(done, started) == state


@pytest.mark.parametrize(
    ("body", "decision"),
    [
        ("## 6. 판단\n- 결정: **GO** — 이유\n", "GO"),
        ("## 6. 판단\n- 결정: HOLD — 이유\n", "HOLD"),
        ("## 6. 판단\n- 결정: {{GO / HOLD — 이유}}\n", None),
        ("## 6. 판단\n- 결정:\n", None),
        ("## 5. x\n- 결정: GO\n## 6. 판단\n- 결정: HOLD\n", "HOLD"),
        ("## 6. 판단\n- 결정: GO\n- 결정: HOLD\n", "GO"),
        ("## 1. x\n- 결정: GO\n", None),
        ("## 60. x\n- 결정: GO\n", None),
    ],
)
def test_decision_of(body: str, decision) -> None:
    assert decision_of(body) == decision


NOW = datetime(2026, 10, 23, 12, 0, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("value", "expected"),
    [("2026-10-23T11:00:00+00:00", 3600), ("2026-10-23T11:00:00Z", 3600),
     ("2026-10-23T20:00:00+09:00", 3600), ("2026-10-23T11:00:00", None),
     ("2026-10-23 11:00", None), ("2026-10-24T00:00:00Z", None), (None, None), (123, None)],
)  # fmt: skip
def test_elapsed(value, expected) -> None:
    assert elapsed_seconds(value, NOW) == expected


def test_parse_rfc3339_requires_tz() -> None:
    assert parse_rfc3339("2026-10-23T11:00:00+00:00") is not None
    assert parse_rfc3339("2026-10-23T11:00:00") is None
