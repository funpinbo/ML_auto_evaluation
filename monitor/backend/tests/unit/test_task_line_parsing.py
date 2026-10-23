"""Task 줄 파싱·상태 우선순위 (FR-002 §2, ADR-009 §4)."""

from __future__ import annotations

import pytest

from app.models.tasks import TaskStatus
from app.services.tasks import ParsedTask, parse_task_text, task_status


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("T-001 [backend] 제목 — FR-001 | deps: T-000 | DoD: x",
         ("T-001", "backend", "제목", ["FR-001"], ["T-000"], True)),
        ("T-023 [qa] 홈 격리 — 보강: ① — I-09, NFR-003 | deps: T-003, T-004 | DoD: a | b",
         ("T-023", "qa", "홈 격리 — 보강: ①", ["I-09", "NFR-003"], ["T-003", "T-004"], True)),
        ("T-002 [qa] 제목만", ("T-002", "qa", "제목만", [], [], True)),
        ("T-003 [Bad Team] x", ("T-003", None, "[Bad Team] x", [], [], False)),
        ("T-004 태그 없음", ("T-004", None, "태그 없음", [], [], False)),
        ("아무 형식 없는 줄", (None, None, "아무 형식 없는 줄", [], [], False)),
        ("T-005 [ops] x | deps: -", ("T-005", "ops", "x", [], [], True)),
    ],
)  # fmt: skip
def test_parse_task_text(text: str, expected) -> None:
    assert parse_task_text(text) == expected


def _task(checked: bool = False, tid: str | None = "T-001") -> ParsedTask:
    return ParsedTask("P1", checked, "", tid, "qa", "t", [], [], True)


@pytest.mark.parametrize(
    ("task", "blocked", "stm", "expected"),
    [
        (_task(True), {"T-001"}, {"status": "active", "task": "T-001"}, TaskStatus.done),
        (_task(), {"T-001"}, None, TaskStatus.blocked),
        (_task(), set(), {"status": "active", "task": "T-001", "outcome": "blocked"}, TaskStatus.blocked),
        (_task(), set(), {"status": "ACTIVE", "task": "T-001", "outcome": "none"}, TaskStatus.active),
        (_task(), set(), {"status": "closed", "task": "T-001"}, TaskStatus.open),
        (_task(), set(), {"status": "active", "task": "T-002"}, TaskStatus.open),
        (_task(tid=None), set(), {"status": "active", "task": "None"}, TaskStatus.open),
    ],
)  # fmt: skip
def test_task_status_priority(task, blocked, stm, expected) -> None:
    assert task_status(task, blocked, stm) == expected
