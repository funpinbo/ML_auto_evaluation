"""backend API 테스트 fixture (backend 소유). qa 의 workspace fixture 위에 엔진·dist·클라이언트를 얹는다."""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

import pytest

_UNIT = Path(__file__).resolve().parents[1] / "unit"
if str(_UNIT) not in sys.path:
    sys.path.insert(0, str(_UNIT))

from backend_support import build_dist, install_engine
from fixtures.workspace import WorkspaceInfo


@pytest.fixture
def engine_workspace(workspace_factory) -> Callable[..., WorkspaceInfo]:
    """`engine_workspace("full")` → 엔진을 복사해 넣은 qa workspace."""

    def make(kind: str = "full", **kwargs: object) -> WorkspaceInfo:
        info = workspace_factory(kind, **kwargs)
        install_engine(info.root)
        return info

    return make


@pytest.fixture
def dist_dir(tmp_path: Path) -> Path:
    return build_dist(tmp_path / "frontend")
