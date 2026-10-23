"""GET /api/v1/control · POST /api/v1/control/{pause,resume} 모델 (FR-005, 20 §5 ControlView)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt

ScreenState = Literal[
    "running", "pause_requested", "paused", "resume_requested", "no_session", "ended"
]
ViewId = Literal["V1", "V2", "V3", "V4", "V5", "V6"]
FileState = Literal["ok", "missing", "broken", "unreadable"]


class PauseRequest(BaseModel):
    """본문 `{}` 또는 `{"max_pause_sec": 600~86400}` (정수 리터럴만 — bool·600.0 은 422)."""

    model_config = ConfigDict(extra="forbid")
    max_pause_sec: StrictInt | None = Field(
        default=None,
        ge=600,
        le=86400,
        description="일시정지 1회 상한(초). 생략 시 7200",
    )


class ResumeRequest(BaseModel):
    """본문 `{}`. 재개는 이전 `max_pause_sec` 를 유지한다."""

    model_config = ConfigDict(extra="forbid")


class ControlData(BaseModel):
    state: ScreenState = Field(
        description="화면 상태 (ADR-004 §4). loop-status 없음·ended = ended"
    )
    view: ViewId = Field(description="stories/FR-005 §2.1 V1~V6")
    label: str = Field(description="화면 라벨 (FR-005 §2.1 정확한 문구)")
    hint: str | None = Field(
        description="V1 남은 반복 / V6 재실행 안내 (FR-005 §2.1 추가 표시)"
    )
    can_pause: bool = Field(description="일시정지 버튼 활성 (FR-005 §2.2)")
    can_resume: bool = Field(description="재개 버튼 활성 (FR-005 §2.2)")
    requested_state: Literal["running", "pause"] | None = Field(
        description="`.control.json` state (정상 파일일 때만)"
    )
    requested_at: str | None
    control_seq: int | None
    baseline_seq: int | None
    control_file: FileState = Field(
        description="`.control.json` 판독 결과 (없음은 정상)"
    )
    loop_file: FileState = Field(description="`loop-status.json` 판독 결과")
    loop_state: Literal["running", "paused", "ended"] | None
    paused_since: str | None
    heartbeat_at: str | None
    heartbeat_age_sec: int | None = Field(
        description="세션 생존 판정은 paused 에서만 (> 120 s = no_session, D-11)"
    )
    iterations_done: int | None
    iterations_total: int | None
    remaining_iterations: int | None
    max_pause_sec: int
    pause_elapsed_sec: int | None
    remaining_pause_sec: int | None = Field(
        description="paused 일 때 max_pause_sec − 경과"
    )
    ended_reason: Literal["done", "blocked", "no_task", "pause_timeout"] | None
    ended_message: str | None = Field(description="V1 종료 사유 문구 (FR-005 §2.3)")
