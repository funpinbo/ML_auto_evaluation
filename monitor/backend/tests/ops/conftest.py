"""ops 테스트 fixture (ops 소유, T-006). backend 도우미(`tests/unit/backend_support.py`)를 읽기만 한다."""

from __future__ import annotations

import logging
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

_UNIT = Path(__file__).resolve().parents[1] / "unit"
if str(_UNIT) not in sys.path:
    sys.path.insert(0, str(_UNIT))


@pytest.fixture
def restore_logging() -> Iterator[None]:
    """setup_logging() 이 바꾼 root·uvicorn 로거 상태를 테스트 뒤에 되돌린다."""
    root = logging.getLogger()
    saved_root = (list(root.handlers), root.level)
    names = ("uvicorn", "uvicorn.error", "uvicorn.access", "httpx")
    saved = {
        n: (
            list(logging.getLogger(n).handlers),
            logging.getLogger(n).propagate,
            logging.getLogger(n).disabled,
            logging.getLogger(n).level,
        )
        for n in names
    }
    yield
    root.handlers[:] = saved_root[0]
    root.setLevel(saved_root[1])
    for n, (handlers, propagate, disabled, level) in saved.items():
        logger = logging.getLogger(n)
        logger.handlers[:] = handlers
        logger.propagate = propagate
        logger.disabled = disabled
        logger.setLevel(level)
