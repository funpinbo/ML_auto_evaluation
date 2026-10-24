"""GET /api/v1/usage/summary, /api/v1/usage/timeseries (FR-004, 20 §5)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from app.api.deps import QUERY_ERROR_RESPONSES, Services, run_panel, services
from app.models.envelope import Envelope
from app.models.usage import (
    UsageBucket,
    UsageGroup,
    UsageRange,
    UsageSummaryData,
    UsageTimeseriesData,
)

router = APIRouter(tags=["usage"])

TzOffset = Annotated[
    int,
    Query(
        ge=-840,
        le=840,
        description="PC 로컬 시간대 오프셋(분, UTC 기준 동쪽 +). 로컬 날짜 경계에 쓴다",
    ),
]


@router.get(
    "/usage/summary",
    response_model=Envelope[UsageSummaryData],
    responses=QUERY_ERROR_RESPONSES,
    summary="한도(5h/7d)·세션 비용·오늘/현재 5시간 토큰·캐시 적중률",
)
def get_usage_summary(
    svc: Annotated[Services, Depends(services)], tz_offset_min: TzOffset = 0
) -> Any:
    """한도는 status line 스냅샷, 토큰은 이 프로젝트 JSONL. 스냅샷 없음·rate_limits 없음은 토큰만 + 안내."""
    return run_panel(svc, lambda: svc.usage.summary(tz_offset_min), "usage")


@router.get(
    "/usage/timeseries",
    response_model=Envelope[UsageTimeseriesData],
    responses=QUERY_ERROR_RESPONSES,
    summary="토큰 시계열 (기간·버킷·그룹)",
)
def get_usage_timeseries(
    svc: Annotated[Services, Depends(services)],
    range_: Annotated[
        UsageRange, Query(alias="range", description="5h | 24h | 7d | 30d")
    ] = "24h",
    bucket: Annotated[
        UsageBucket | None,
        Query(description="hour | day (생략 시 30d 는 day, 나머지는 hour)"),
    ] = None,
    group: Annotated[
        UsageGroup, Query(description="model | sidechain | none")
    ] = "model",
    tz_offset_min: TzOffset = 0,
) -> Any:
    return run_panel(
        svc,
        lambda: svc.usage.timeseries(range_, bucket, group, tz_offset_min),
        "usage",
    )
