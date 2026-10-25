"""S-01~S-03 가드레일: 깨진·빈·부재 입력에서 모든 GET 엔드포인트가 HTTP 500 을 내지 않는다 (NFR-002, QS-03·04).

workspace 5종 × 데이터 소스 변형 7종(스냅샷 없음/rate_limits 없음/오래됨/깨짐, 프로젝트 디렉터리 없음,
CLAUDE_HOME 없음)을 전수로 조합한다. 500 이 아니면서 API 응답은 `{data, meta}` 봉투여야 하고,
같은 앱이 다음 요청에도 응답한다(프로세스 생존).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fixtures.endpoints import ALL_GETS, API, SSE_PATH
from guardrail_support import (
    SOURCE_VARIANTS,
    WORKSPACE_KINDS,
    app_client,
    prepare_snapshot,
)


def _claude_home(variant_home: str, workspace, claude_home_factory, tmp_path) -> Path:
    if variant_home == "no_home":
        return tmp_path / "no-such-claude-home"
    home = claude_home_factory(workspace.root, with_jsonl=variant_home == "with_jsonl")
    return home.home


@pytest.mark.parametrize("source", SOURCE_VARIANTS, ids=[v[0] for v in SOURCE_VARIANTS])
@pytest.mark.parametrize("kind", WORKSPACE_KINDS)
def test_all_get_endpoints_never_500(
    kind, source, workspace_factory, claude_home_factory, tmp_path
) -> None:
    _, snapshot_kind, variant_home = source
    workspace = workspace_factory(kind)
    home = _claude_home(variant_home, workspace, claude_home_factory, tmp_path)
    prepare_snapshot(workspace, snapshot_kind, dir_name=None)
    client = app_client(workspace, home)

    for path in ALL_GETS:
        response = client.get(path)
        assert response.status_code < 500, (path, response.status_code)
        if path.startswith(API) and response.status_code == 200:
            body = response.json()
            assert set(body) == {"data", "meta"}, path
            assert body["meta"]["status"] in {
                "ok",
                "empty",
                "partial",
                "warming",
                "error",
            }, path
    assert client.get(f"{API}/health").status_code == 200  # 끝난 뒤에도 살아 있다


def test_empty_workspace_panels_report_empty_not_error(
    empty_workspace, claude_home_factory
) -> None:
    """S-02: 없는 파일은 error 가 아니라 empty (패널 단위 안내)."""
    home = claude_home_factory(empty_workspace.root).home
    client = app_client(empty_workspace, home)
    for panel in ("plan", "tasks", "memory", "control"):
        meta = client.get(f"{API}/{panel}").json()["meta"]
        assert meta["status"] in {"empty", "partial"}, (panel, meta["status"])


def test_broken_snapshot_isolated_to_usage_panel(
    full_workspace, claude_home_factory
) -> None:
    """S-01: 스냅샷이 깨져도 영향은 사용량 패널 안에 머문다. 다른 패널은 정상."""
    home = claude_home_factory(full_workspace.root).home
    prepare_snapshot(full_workspace, "broken", dir_name=None)
    client = app_client(full_workspace, home)

    assert client.get(f"{API}/usage/summary").status_code == 200
    for panel in ("plan", "tasks", "memory"):
        assert client.get(f"{API}/{panel}").json()["meta"]["status"] == "ok", panel


def test_missing_snapshot_still_shows_tokens(
    full_workspace, claude_home_factory
) -> None:
    """S-03: 스냅샷이 없어도 토큰 집계는 나온다 (한도 정보만 없음)."""
    home = claude_home_factory(full_workspace.root).home
    prepare_snapshot(full_workspace, "none", dir_name=None)
    client = app_client(full_workspace, home)
    body = client.get(f"{API}/usage/summary").json()
    assert body["meta"]["status"] != "error"
    assert body["data"] is not None


def test_endpoint_list_covers_app_routes(full_workspace, claude_home_factory) -> None:
    """새 GET 라우트가 생기면 전수 목록(fixtures/endpoints.py)에 추가하도록 강제한다."""
    client = app_client(full_workspace, claude_home_factory(full_workspace.root).home)
    routes = {
        route.path
        for route in client.app.routes
        if "GET" in getattr(route, "methods", ())
    }
    listed = {path.split("?")[0] for path in ALL_GETS} | {SSE_PATH}
    assert routes <= listed, sorted(routes - listed)
