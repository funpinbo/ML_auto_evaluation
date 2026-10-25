"""조회(GET) 엔드포인트 목록 (qa, T-013). 가드레일 시나리오가 전수 호출에 쓴다.

SSE(`/api/v1/events`)는 끝나지 않는 응답이라 여기 넣지 않는다 — 실서버 시나리오가 따로 읽는다.
새 GET 라우트가 생기면 `test_endpoint_list_covers_app_routes` 가 이 목록 갱신을 요구한다.
"""

from __future__ import annotations

API = "/api/v1"
SSE_PATH = f"{API}/events"

# 첫 화면에 필요한 Must 패널 (NFR-001). 이 순서로 호출한다.
MUST_PANELS = (
    f"{API}/health",
    f"{API}/pipeline",
    f"{API}/plan",
    f"{API}/tasks",
    f"{API}/memory",
    f"{API}/control",
    f"{API}/usage/summary",
    f"{API}/usage/timeseries?range=24h",
)
EXTRA_GETS = (
    f"{API}/tasks?status=open&team=qa&phase=P1",
    f"{API}/usage/timeseries?range=30d&group=sidechain",
    f"{API}/usage/summary?tz_offset_min=540",
    "/",  # 정적 dist (없을 때도 500 이 아니어야 한다)
    f"{API}/no-such-route",
)
ALL_GETS = (*MUST_PANELS, *EXTRA_GETS)
