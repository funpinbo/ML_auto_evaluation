"""패널 단위 예외 격리 (NFR-002, ADR-011 §1): 한 패널의 예상 못 한 예외가 HTTP 500 이나 다른 패널로 번지지 않는다."""

from __future__ import annotations

import logging

import pytest
from backend_support import client_for

PANELS = {
    "/api/v1/pipeline": "pipeline",
    "/api/v1/plan": "tasks",
    "/api/v1/memory": "memory",
}


@pytest.mark.parametrize("path", sorted(PANELS))
def test_unexpected_exception_isolated(engine_workspace, path: str, caplog) -> None:
    info = engine_workspace("full")
    client = client_for(info.root)
    svc = client.app.state.services
    target = getattr(svc, PANELS[path])

    def boom(*args, **kwargs):
        raise KeyError("SECRETMARKER")

    method = "read" if path != "/api/v1/plan" else "plan"
    setattr(target, method, boom)
    with caplog.at_level(logging.ERROR):
        resp = client.get(path)
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"] is None
    assert body["meta"]["status"] == "error"
    assert body["meta"]["error"]["code"] == "SOURCE_UNREADABLE"
    assert "SECRETMARKER" not in resp.text and "SECRETMARKER" not in caplog.text
    assert "KeyError" in caplog.text
    others = [
        p for p in ("/api/v1/tasks", "/api/v1/memory", "/api/v1/pipeline") if p != path
    ]
    for other in others:
        assert client.get(other).json()["meta"]["status"] != "error"
