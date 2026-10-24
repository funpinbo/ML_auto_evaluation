"""GET /api/v1/usage/summary · /api/v1/usage/timeseries 모델 (FR-004, 20 §5).

응답에는 집계 숫자·모델명·시각·상태 코드만 담는다. 경로·`transcript_dir_name`·세션 ID·requestId·본문은
필드 자체가 없다(Pydantic allow-list, privacy.md P-09, D-13).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.models.envelope import SourceErrorCode
from app.models.health import UsageWarming

UsageRange = Literal["5h", "24h", "7d", "30d"]
UsageBucket = Literal["hour", "day"]
UsageGroup = Literal["model", "sidechain", "none"]
SnapshotState = Literal["ok", "missing", "broken", "unreadable"]


class TokenTotals(BaseModel):
    responses: int = Field(description="고유 응답 수 (requestId 중복 제거 후)")
    input_tokens: int
    output_tokens: int
    cache_creation_input_tokens: int
    cache_read_input_tokens: int
    cache_hit_rate: float | None = Field(
        description="cache_read / (input + cache_creation + cache_read), 분모 0 이면 null"
    )


class TokenWindow(BaseModel):
    start: str = Field(description="구간 시작 (RFC 3339)")
    end: str = Field(description="구간 끝 = 현재 (RFC 3339)")
    estimated: bool = Field(
        description="true = 이동 구간 추정(스냅샷 resets_at 없음). 집계는 1시간 버킷 단위"
    )
    totals: TokenTotals


class LimitWindow(BaseModel):
    used_percentage: float | None = Field(description="0~100 (계정 전체 기준)")
    resets_at: int | None = Field(description="초기화 시각, Unix epoch 초")
    resets_at_iso: str | None = Field(description="초기화 시각 (RFC 3339, UTC)")
    reset_passed: bool | None = Field(
        description="초기화 시각이 지났음 — '새 응답 후 갱신' 안내"
    )


class SnapshotInfo(BaseModel):
    state: SnapshotState = Field(description="스냅샷 파일 판독 결과")
    captured_at: str | None
    age_sec: int | None = Field(description="captured_at 경과 초")
    stale: bool = Field(description="600 초 초과 (SNAPSHOT_STALE)")
    code: SourceErrorCode | None = Field(
        description="한도 영역 코드: SOURCE_MISSING / SOURCE_PARSE_ERROR / SOURCE_UNREADABLE / SNAPSHOT_STALE"
    )


class UsageSummaryData(BaseModel):
    scope: Literal["project"] = Field(description="토큰은 이 프로젝트 기준 (A13)")
    limits_available: bool = Field(
        description="스냅샷에 한도 값이 있음. false 면 limits_notice 를 표시"
    )
    limits_notice: str | None
    five_hour: LimitWindow | None
    seven_day: LimitWindow | None
    snapshot: SnapshotInfo
    session_cost_usd: float | None = Field(description="세션 비용(추정), 최근 세션")
    session_duration_ms: int | None
    context_used_percentage: float | None
    model_id: str | None
    project_dir_found: bool
    tokens_code: SourceErrorCode | None = Field(
        description="토큰 영역 코드: PROJECT_DIR_NOT_FOUND"
    )
    today: TokenWindow = Field(description="로컬 오늘(tz_offset_min 기준) 토큰")
    five_hour_tokens: TokenWindow = Field(
        description="현재 5시간 구간 = [resets_at − 5h, now] 또는 이동 5시간(estimated)"
    )
    skipped_lines: int = Field(description="형식 오류로 건너뛴 기록 줄 수")
    warming: UsageWarming


class TokenSeries(BaseModel):
    key: str = Field(
        description="group=model → 모델 id, sidechain → main|subagent, none → all"
    )
    responses: list[int]
    input_tokens: list[int]
    output_tokens: list[int]
    cache_creation_input_tokens: list[int]
    cache_read_input_tokens: list[int]


class UsageTimeseriesData(BaseModel):
    scope: Literal["project"]
    range: UsageRange
    bucket: UsageBucket
    group: UsageGroup
    tz_offset_min: int
    start: str
    end: str
    buckets: list[str] = Field(
        description="버킷 시작 시각 목록 (hour = UTC 정시, day = 로컬 자정, RFC 3339). series 값과 같은 순서"
    )
    series: list[TokenSeries]
    totals: TokenTotals
    project_dir_found: bool
    warming: UsageWarming
