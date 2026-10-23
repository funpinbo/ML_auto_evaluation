"""`GET /api/v1/health` 응답 모델 (CON-05, 20 §5, ops 소유).

응답은 공통 봉투 `{data, meta}` 다(D-08). `data` 에는 상태 코드만 담는다 — 경로·파일 이름·ID·
본문은 넣지 않는다(02 §7, ADR-011 §8). 런처(T-007)는 `data.app == "aidlc-monitor"` 로
이미 떠 있는 자기 서버인지 판정한다(ADR-001 §4). `app` 값은 바꾸지 않는다.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

SourceState = Literal["ok", "missing", "stale", "unreadable"]
"""소스 접근 상태. `stale` 은 statusline 스냅샷만 쓴다(수정 시각이 10분 넘음, ADR-003 §4)."""

WarmingState = Literal["not_started", "warming", "done", "unknown"]


class HealthSources(BaseModel):
    """데이터 소스별 접근 가능 여부. 파일 내용은 읽지 않고 메타데이터(stat)만 본다."""

    workspace: SourceState = Field(
        description="`<AIDLC_ROOT>/workspace/memory` 디렉터리"
    )
    claude_projects: SourceState = Field(
        description="`<CLAUDE_HOME>/projects` 디렉터리 (사용량 기록 위치)"
    )
    statusline: SourceState = Field(
        description="status line 스냅샷 파일. 없음 = statusLine 미실행 또는 첫 응답 전"
    )
    control: SourceState = Field(
        description="`.control.json`. 없음은 정상(첫 일시정지 전)이라 경고를 만들지 않는다"
    )


class UsageWarming(BaseModel):
    """사용량 캐시 데우기 진행률 (ADR-002 §6). 수집기(T-010) 전에는 `not_started`."""

    state: WarmingState
    progress: float | None = Field(
        default=None, ge=0.0, le=1.0, description="0.0~1.0, 모르면 null"
    )


class HealthData(BaseModel):
    status: Literal["ok"] = Field(description="프로세스 생존. 응답이 오면 항상 ok")
    app: Literal["aidlc-monitor"] = Field(
        description="앱 식별자. 런처의 중복 실행 판정용 — 값 고정"
    )
    version: str
    sources: HealthSources
    dist: Literal["ok", "missing"] = Field(
        description="프론트 dist(index.html) 유무 (ADR-005 §3)"
    )
    usage_warming: UsageWarming
