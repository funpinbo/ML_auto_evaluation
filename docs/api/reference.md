# AI-DLC Monitor API — REST API 레퍼런스

> `workspace/project/contracts/openapi.json` 에서 자동 생성됨 (`python3 aidlc/scripts/openapi_docs.py render`). 직접 수정하지 말고 명세를 고친 뒤 다시 생성하세요.

| 항목 | 값 |
|---|---|
| 버전 | `0.1.0` |
| OpenAPI | `3.1.0` |
| 서버 | `http://127.0.0.1:8765` 로컬 기본 포트 |

로컬 전용(127.0.0.1) AI-DLC 대시보드 API. 조회 응답은 `{data, meta}` 봉투, 요청 오류는 `{"error":{code,message}}` (닫힌 코드 9개). 소스 문제는 HTTP 200 + `meta.status`.

## 엔드포인트 목록

| 그룹 | 메서드 | 경로 | 설명 |
|---|---|---|---|
| pipeline | `GET` | [`/api/v1/pipeline`](#get-apiv1pipeline) | AI-DLC 단계 0~6 상태와 Gate 3종 |
| plan | `GET` | [`/api/v1/plan`](#get-apiv1plan) | Phase 별 진행률과 현재·완료 Phase |
| plan | `GET` | [`/api/v1/tasks`](#get-apiv1tasks) | Task 목록 (팀·상태·Phase 필터, AND) |
| memory | `GET` | [`/api/v1/memory`](#get-apiv1memory) | STM·LTM·Task 동기 값과 미처리 cascade |
| control | `GET` | [`/api/v1/control`](#get-apiv1control) | 루프 제어 화면 상태 (.control.json + loop-status.json 조합) |
| control | `POST` | [`/api/v1/control/pause`](#post-apiv1controlpause) | 일시정지 요청 (.control.json state=pause, seq = max(prev, baseline)+1) |
| control | `POST` | [`/api/v1/control/resume`](#post-apiv1controlresume) | 재개 요청 (멱등, 루프가 없어도 200) |
| usage | `GET` | [`/api/v1/usage/summary`](#get-apiv1usagesummary) | 한도(5h/7d)·세션 비용·오늘/현재 5시간 토큰·캐시 적중률 |
| usage | `GET` | [`/api/v1/usage/timeseries`](#get-apiv1usagetimeseries) | 토큰 시계열 (기간·버킷·그룹) |
| events | `GET` | [`/api/v1/events`](#get-apiv1events) | 변경 알림 스트림 (text/event-stream) |
| health | `GET` | [`/api/v1/health`](#get-apiv1health) | 생존·소스 접근 가능 여부·데우기 진행률·앱 식별자 |

## pipeline

### GET /api/v1/pipeline

**AI-DLC 단계 0~6 상태와 Gate 3종**

단계 판정은 FR-001 §2(D-21). Gate 는 `aidlc.py check` 서브프로세스(TTL 5 s).

- **인증:** 불필요
- **operationId:** `get_pipeline`

#### 응답

| 상태 코드 | 설명 | 본문 |
|---|---|---|
| `200` | Successful Response | Envelope_PipelineData_ |
| `400` | BAD_HOST — Host 가드 | ErrorResponse |
| `405` | METHOD_NOT_ALLOWED — `Allow` 헤더 포함 (OPTIONS·HEAD 포함) | ErrorResponse |
| `500` | INTERNAL_ERROR | ErrorResponse |

`200` 응답 필드

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `data` | PipelineData \| null | ✅ |  |
| `meta` | Meta | ✅ |  |
| `meta.status` | string enum: `ok`, `partial`, `empty`, `error`, `warming` | ✅ |  |
| `meta.warnings` | array<string> |  |  |
| `meta.error` | SourceError \| null |  |  |
| `meta.generated_at` | string | ✅ | 응답 생성 시각 (RFC 3339, UTC) |
| `meta.source_mtime` | string \| null |  | 읽은 소스 파일 중 가장 최근 수정 시각 (RFC 3339, UTC) |

```json
{
  "data": {
    "current_stage": 0,
    "current_stage_name": "string",
    "next_command": "string",
    "all_done": true,
    "stages": [
      {
        "index": 0,
        "name": "string",
        "command": "string",
        "state": "done"
      }
    ],
    "gates": [
      {
        "layer": "user",
        "result": "PASS",
        "unwritten": 0,
        "missing": 0,
        "target_missing": true,
        "no_documents": true,
        "error_code": "SOURCE_MISSING",
        "checked_at": "string"
      }
    ]
  },
  "meta": {
    "status": "ok",
    "warnings": [
      "string"
    ],
    "error": {
      "code": "SOURCE_MISSING",
      "message": "string"
    },
    "generated_at": "string",
    "source_mtime": "string"
  }
}
```

#### 예시

```bash
curl -X GET 'http://127.0.0.1:8765/api/v1/pipeline'
```

## plan

### GET /api/v1/plan

**Phase 별 진행률과 현재·완료 Phase**

- **인증:** 불필요
- **operationId:** `get_plan`

#### 응답

| 상태 코드 | 설명 | 본문 |
|---|---|---|
| `200` | Successful Response | Envelope_PlanData_ |
| `400` | BAD_HOST — Host 가드 | ErrorResponse |
| `405` | METHOD_NOT_ALLOWED — `Allow` 헤더 포함 (OPTIONS·HEAD 포함) | ErrorResponse |
| `500` | INTERNAL_ERROR | ErrorResponse |

`200` 응답 필드

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `data` | PlanData \| null | ✅ |  |
| `meta` | Meta | ✅ |  |
| `meta.status` | string enum: `ok`, `partial`, `empty`, `error`, `warming` | ✅ |  |
| `meta.warnings` | array<string> |  |  |
| `meta.error` | SourceError \| null |  |  |
| `meta.generated_at` | string | ✅ | 응답 생성 시각 (RFC 3339, UTC) |
| `meta.source_mtime` | string \| null |  | 읽은 소스 파일 중 가장 최근 수정 시각 (RFC 3339, UTC) |

```json
{
  "data": {
    "current_phase": "string",
    "completed_phases": [
      "string"
    ],
    "phases": [
      {
        "phase": "string",
        "title": "string",
        "total": 0,
        "checked": 0,
        "percent": 0,
        "completed": true,
        "current": true
      }
    ]
  },
  "meta": {
    "status": "ok",
    "warnings": [
      "string"
    ],
    "error": {
      "code": "SOURCE_MISSING",
      "message": "string"
    },
    "generated_at": "string",
    "source_mtime": "string"
  }
}
```

#### 예시

```bash
curl -X GET 'http://127.0.0.1:8765/api/v1/plan'
```

### GET /api/v1/tasks

**Task 목록 (팀·상태·Phase 필터, AND)**

- **인증:** 불필요
- **operationId:** `get_tasks`

#### 파라미터

| 이름 | 위치 | 타입 | 필수 | 설명 |
|---|---|---|---|---|
| `team` | query | string \| null |  | 팀 id |
| `status` | query | TaskStatus enum: `open`, `done`, `blocked`, `active` \| null |  | open \| done \| blocked \| active |
| `phase` | query | string \| null |  | Phase (예: P1) |

#### 응답

| 상태 코드 | 설명 | 본문 |
|---|---|---|
| `200` | Successful Response | Envelope_TasksData_ |
| `400` | BAD_HOST — Host 가드 | ErrorResponse |
| `405` | METHOD_NOT_ALLOWED — `Allow` 헤더 포함 (OPTIONS·HEAD 포함) | ErrorResponse |
| `500` | INTERNAL_ERROR | ErrorResponse |
| `422` | VALIDATION_ERROR — 쿼리 검증 | ErrorResponse |

`200` 응답 필드

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `data` | TasksData \| null | ✅ |  |
| `meta` | Meta | ✅ |  |
| `meta.status` | string enum: `ok`, `partial`, `empty`, `error`, `warming` | ✅ |  |
| `meta.warnings` | array<string> |  |  |
| `meta.error` | SourceError \| null |  |  |
| `meta.generated_at` | string | ✅ | 응답 생성 시각 (RFC 3339, UTC) |
| `meta.source_mtime` | string \| null |  | 읽은 소스 파일 중 가장 최근 수정 시각 (RFC 3339, UTC) |

```json
{
  "data": {
    "total": 0,
    "items": [
      {
        "id": "string",
        "team": "string",
        "title": "string",
        "refs": [
          null
        ],
        "deps": [
          null
        ],
        "phase": "string",
        "checked": true,
        "status": "open",
        "well_formed": true
      }
    ]
  },
  "meta": {
    "status": "ok",
    "warnings": [
      "string"
    ],
    "error": {
      "code": "SOURCE_MISSING",
      "message": "string"
    },
    "generated_at": "string",
    "source_mtime": "string"
  }
}
```

#### 예시

```bash
curl -X GET 'http://127.0.0.1:8765/api/v1/tasks'
```

## memory

### GET /api/v1/memory

**STM·LTM·Task 동기 값과 미처리 cascade**

cascade 판정은 Hook `Memory.pending().level` (ADR-009). `aidlc.py status` 는 실행하지 않는다.

- **인증:** 불필요
- **operationId:** `get_memory`

#### 응답

| 상태 코드 | 설명 | 본문 |
|---|---|---|
| `200` | Successful Response | Envelope_MemoryData_ |
| `400` | BAD_HOST — Host 가드 | ErrorResponse |
| `405` | METHOD_NOT_ALLOWED — `Allow` 헤더 포함 (OPTIONS·HEAD 포함) | ErrorResponse |
| `500` | INTERNAL_ERROR | ErrorResponse |

`200` 응답 필드

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `data` | MemoryData \| null | ✅ |  |
| `meta` | Meta | ✅ |  |
| `meta.status` | string enum: `ok`, `partial`, `empty`, `error`, `warming` | ✅ |  |
| `meta.warnings` | array<string> |  |  |
| `meta.error` | SourceError \| null |  |  |
| `meta.generated_at` | string | ✅ | 응답 생성 시각 (RFC 3339, UTC) |
| `meta.source_mtime` | string \| null |  | 읽은 소스 파일 중 가장 최근 수정 시각 (RFC 3339, UTC) |

```json
{
  "data": {
    "stm": {
      "status": "idle",
      "task": "string",
      "team": "string",
      "outcome": "string",
      "opened_at": "string",
      "elapsed_sec": 0,
      "error_code": "SOURCE_MISSING"
    },
    "ltm_rev": 0,
    "last_merged_stm": 0,
    "tasks_rev": 0,
    "synced_ltm_rev": 0,
    "current_phase": "string",
    "completed_phases": [
      "string"
    ],
    "archive_count": 0,
    "latest_archive_seq": 0,
    "pending_cascade": "none",
    "stop_blocks": 0
  },
  "meta": {
    "status": "ok",
    "warnings": [
      "string"
    ],
    "error": {
      "code": "SOURCE_MISSING",
      "message": "string"
    },
    "generated_at": "string",
    "source_mtime": "string"
  }
}
```

#### 예시

```bash
curl -X GET 'http://127.0.0.1:8765/api/v1/memory'
```

## control

### GET /api/v1/control

**루프 제어 화면 상태 (.control.json + loop-status.json 조합)**

loop-status 없음 = `meta.status=empty`, 깨짐 = `error`, 제어 파일 깨짐 = `partial`.

- **인증:** 불필요
- **operationId:** `get_control`

#### 응답

| 상태 코드 | 설명 | 본문 |
|---|---|---|
| `200` | Successful Response | Envelope_ControlData_ |
| `400` | BAD_HOST — Host 가드 | ErrorResponse |
| `405` | METHOD_NOT_ALLOWED — `Allow` 헤더 포함 (OPTIONS·HEAD 포함) | ErrorResponse |
| `500` | INTERNAL_ERROR | ErrorResponse |

`200` 응답 필드

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `data` | ControlData \| null | ✅ |  |
| `meta` | Meta | ✅ |  |
| `meta.status` | string enum: `ok`, `partial`, `empty`, `error`, `warming` | ✅ |  |
| `meta.warnings` | array<string> |  |  |
| `meta.error` | SourceError \| null |  |  |
| `meta.generated_at` | string | ✅ | 응답 생성 시각 (RFC 3339, UTC) |
| `meta.source_mtime` | string \| null |  | 읽은 소스 파일 중 가장 최근 수정 시각 (RFC 3339, UTC) |

```json
{
  "data": {
    "state": "running",
    "view": "V1",
    "label": "string",
    "hint": "string",
    "can_pause": true,
    "can_resume": true,
    "requested_state": "running",
    "requested_at": "string",
    "control_seq": 0,
    "baseline_seq": 0,
    "control_file": "ok",
    "loop_file": "ok",
    "loop_state": "running",
    "paused_since": "string",
    "heartbeat_at": "string",
    "heartbeat_age_sec": 0,
    "iterations_done": 0,
    "iterations_total": 0,
    "remaining_iterations": 0,
    "max_pause_sec": 0,
    "pause_elapsed_sec": 0,
    "remaining_pause_sec": 0,
    "session_activity_at": "string",
    "session_activity_age_sec": 0,
    "ended_reason": "done",
    "ended_message": "string"
  },
  "meta": {
    "status": "ok",
    "warnings": [
      "string"
    ],
    "error": {
      "code": "SOURCE_MISSING",
      "message": "string"
    },
    "generated_at": "string",
    "source_mtime": "string"
  }
}
```

#### 예시

```bash
curl -X GET 'http://127.0.0.1:8765/api/v1/control'
```

### POST /api/v1/control/pause

**일시정지 요청 (.control.json state=pause, seq = max(prev, baseline)+1)**

- **인증:** 불필요
- **operationId:** `post_pause`

#### 요청 본문

`application/json`

```json
{
  "max_pause_sec": 0
}
```

#### 응답

| 상태 코드 | 설명 | 본문 |
|---|---|---|
| `200` | Successful Response | Envelope_ControlData_ |
| `400` | BAD_HOST — Host 가드 | ErrorResponse |
| `405` | METHOD_NOT_ALLOWED — `Allow` 헤더 포함 (OPTIONS·HEAD 포함) | ErrorResponse |
| `500` | CONTROL_WRITE_FAILED — 쓰기 실패·락 타임아웃(2 s)·seq 상한, 기존 파일 보존 / INTERNAL_ERROR | ErrorResponse |
| `403` | FORBIDDEN_ORIGIN — Origin 불일치 또는 Content-Type 이 application/json 아님 | ErrorResponse |
| `422` | VALIDATION_ERROR — 본문 검증 (max_pause_sec 600~86400) | ErrorResponse |
| `409` | NO_ACTIVE_LOOP — loop-status 가 running/paused 가 아님 | ErrorResponse |

`200` 응답 필드

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `data` | ControlData \| null | ✅ |  |
| `meta` | Meta | ✅ |  |
| `meta.status` | string enum: `ok`, `partial`, `empty`, `error`, `warming` | ✅ |  |
| `meta.warnings` | array<string> |  |  |
| `meta.error` | SourceError \| null |  |  |
| `meta.generated_at` | string | ✅ | 응답 생성 시각 (RFC 3339, UTC) |
| `meta.source_mtime` | string \| null |  | 읽은 소스 파일 중 가장 최근 수정 시각 (RFC 3339, UTC) |

```json
{
  "data": {
    "state": "running",
    "view": "V1",
    "label": "string",
    "hint": "string",
    "can_pause": true,
    "can_resume": true,
    "requested_state": "running",
    "requested_at": "string",
    "control_seq": 0,
    "baseline_seq": 0,
    "control_file": "ok",
    "loop_file": "ok",
    "loop_state": "running",
    "paused_since": "string",
    "heartbeat_at": "string",
    "heartbeat_age_sec": 0,
    "iterations_done": 0,
    "iterations_total": 0,
    "remaining_iterations": 0,
    "max_pause_sec": 0,
    "pause_elapsed_sec": 0,
    "remaining_pause_sec": 0,
    "session_activity_at": "string",
    "session_activity_age_sec": 0,
    "ended_reason": "done",
    "ended_message": "string"
  },
  "meta": {
    "status": "ok",
    "warnings": [
      "string"
    ],
    "error": {
      "code": "SOURCE_MISSING",
      "message": "string"
    },
    "generated_at": "string",
    "source_mtime": "string"
  }
}
```

#### 예시

```bash
curl -X POST 'http://127.0.0.1:8765/api/v1/control/pause' \
  -H 'Content-Type: application/json' \
  -d '{"max_pause_sec": 0}'
```

### POST /api/v1/control/resume

**재개 요청 (멱등, 루프가 없어도 200)**

- **인증:** 불필요
- **operationId:** `post_resume`

#### 요청 본문

`application/json`

```json
{}
```

#### 응답

| 상태 코드 | 설명 | 본문 |
|---|---|---|
| `200` | Successful Response | Envelope_ControlData_ |
| `400` | BAD_HOST — Host 가드 | ErrorResponse |
| `405` | METHOD_NOT_ALLOWED — `Allow` 헤더 포함 (OPTIONS·HEAD 포함) | ErrorResponse |
| `500` | CONTROL_WRITE_FAILED — 쓰기 실패·락 타임아웃(2 s)·seq 상한, 기존 파일 보존 / INTERNAL_ERROR | ErrorResponse |
| `403` | FORBIDDEN_ORIGIN — Origin 불일치 또는 Content-Type 이 application/json 아님 | ErrorResponse |
| `422` | VALIDATION_ERROR — 본문 검증 (max_pause_sec 600~86400) | ErrorResponse |

`200` 응답 필드

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `data` | ControlData \| null | ✅ |  |
| `meta` | Meta | ✅ |  |
| `meta.status` | string enum: `ok`, `partial`, `empty`, `error`, `warming` | ✅ |  |
| `meta.warnings` | array<string> |  |  |
| `meta.error` | SourceError \| null |  |  |
| `meta.generated_at` | string | ✅ | 응답 생성 시각 (RFC 3339, UTC) |
| `meta.source_mtime` | string \| null |  | 읽은 소스 파일 중 가장 최근 수정 시각 (RFC 3339, UTC) |

```json
{
  "data": {
    "state": "running",
    "view": "V1",
    "label": "string",
    "hint": "string",
    "can_pause": true,
    "can_resume": true,
    "requested_state": "running",
    "requested_at": "string",
    "control_seq": 0,
    "baseline_seq": 0,
    "control_file": "ok",
    "loop_file": "ok",
    "loop_state": "running",
    "paused_since": "string",
    "heartbeat_at": "string",
    "heartbeat_age_sec": 0,
    "iterations_done": 0,
    "iterations_total": 0,
    "remaining_iterations": 0,
    "max_pause_sec": 0,
    "pause_elapsed_sec": 0,
    "remaining_pause_sec": 0,
    "session_activity_at": "string",
    "session_activity_age_sec": 0,
    "ended_reason": "done",
    "ended_message": "string"
  },
  "meta": {
    "status": "ok",
    "warnings": [
      "string"
    ],
    "error": {
      "code": "SOURCE_MISSING",
      "message": "string"
    },
    "generated_at": "string",
    "source_mtime": "string"
  }
}
```

#### 예시

```bash
curl -X POST 'http://127.0.0.1:8765/api/v1/control/resume' \
  -H 'Content-Type: application/json' \
  -d '{}'
```

## usage

### GET /api/v1/usage/summary

**한도(5h/7d)·세션 비용·오늘/현재 5시간 토큰·캐시 적중률**

한도는 status line 스냅샷, 토큰은 이 프로젝트 JSONL. 스냅샷 없음·rate_limits 없음은 토큰만 + 안내.

- **인증:** 불필요
- **operationId:** `get_usage_summary`

#### 파라미터

| 이름 | 위치 | 타입 | 필수 | 설명 |
|---|---|---|---|---|
| `tz_offset_min` | query | integer |  | PC 로컬 시간대 오프셋(분, UTC 기준 동쪽 +). 로컬 날짜 경계에 쓴다 |

#### 응답

| 상태 코드 | 설명 | 본문 |
|---|---|---|
| `200` | Successful Response | Envelope_UsageSummaryData_ |
| `400` | BAD_HOST — Host 가드 | ErrorResponse |
| `405` | METHOD_NOT_ALLOWED — `Allow` 헤더 포함 (OPTIONS·HEAD 포함) | ErrorResponse |
| `500` | INTERNAL_ERROR | ErrorResponse |
| `422` | VALIDATION_ERROR — 쿼리 검증 | ErrorResponse |

`200` 응답 필드

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `data` | UsageSummaryData \| null | ✅ |  |
| `meta` | Meta | ✅ |  |
| `meta.status` | string enum: `ok`, `partial`, `empty`, `error`, `warming` | ✅ |  |
| `meta.warnings` | array<string> |  |  |
| `meta.error` | SourceError \| null |  |  |
| `meta.generated_at` | string | ✅ | 응답 생성 시각 (RFC 3339, UTC) |
| `meta.source_mtime` | string \| null |  | 읽은 소스 파일 중 가장 최근 수정 시각 (RFC 3339, UTC) |

```json
{
  "data": {
    "scope": "string",
    "limits_available": true,
    "limits_notice": "string",
    "five_hour": {
      "used_percentage": 0.0,
      "resets_at": 0,
      "resets_at_iso": "string",
      "reset_passed": true
    },
    "seven_day": {
      "used_percentage": 0.0,
      "resets_at": 0,
      "resets_at_iso": "string",
      "reset_passed": true
    },
    "snapshot": {
      "state": "ok",
      "captured_at": "string",
      "age_sec": 0,
      "stale": true,
      "code": "SOURCE_MISSING"
    },
    "session_cost_usd": 0.0,
    "session_duration_ms": 0,
    "context_used_percentage": 0.0,
    "model_id": "string",
    "project_dir_found": true,
    "tokens_code": "SOURCE_MISSING",
    "today": {
      "start": "string",
      "end": "string",
      "estimated": true,
      "totals": {
        "responses": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
        "cache_hit_rate": 0.0
      }
    },
    "five_hour_tokens": {
      "start": "string",
      "end": "string",
      "estimated": true,
      "totals": {
        "responses": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
        "cache_hit_rate": 0.0
      }
    },
    "skipped_lines": 0,
    "warming": {
      "state": "not_started",
      "progress": 0.0
    }
  },
  "meta": {
    "status": "ok",
    "warnings": [
      "string"
    ],
    "error": {
      "code": "SOURCE_MISSING",
      "message": "string"
    },
    "generated_at": "string",
    "source_mtime": "string"
  }
}
```

#### 예시

```bash
curl -X GET 'http://127.0.0.1:8765/api/v1/usage/summary'
```

### GET /api/v1/usage/timeseries

**토큰 시계열 (기간·버킷·그룹)**

- **인증:** 불필요
- **operationId:** `get_usage_timeseries`

#### 파라미터

| 이름 | 위치 | 타입 | 필수 | 설명 |
|---|---|---|---|---|
| `range` | query | string enum: `5h`, `24h`, `7d`, `30d` |  | 5h \| 24h \| 7d \| 30d |
| `bucket` | query | string enum: `hour`, `day` \| null |  | hour \| day (생략 시 30d 는 day, 나머지는 hour) |
| `group` | query | string enum: `model`, `sidechain`, `none` |  | model \| sidechain \| none |
| `tz_offset_min` | query | integer |  | PC 로컬 시간대 오프셋(분, UTC 기준 동쪽 +). 로컬 날짜 경계에 쓴다 |

#### 응답

| 상태 코드 | 설명 | 본문 |
|---|---|---|
| `200` | Successful Response | Envelope_UsageTimeseriesData_ |
| `400` | BAD_HOST — Host 가드 | ErrorResponse |
| `405` | METHOD_NOT_ALLOWED — `Allow` 헤더 포함 (OPTIONS·HEAD 포함) | ErrorResponse |
| `500` | INTERNAL_ERROR | ErrorResponse |
| `422` | VALIDATION_ERROR — 쿼리 검증 | ErrorResponse |

`200` 응답 필드

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `data` | UsageTimeseriesData \| null | ✅ |  |
| `meta` | Meta | ✅ |  |
| `meta.status` | string enum: `ok`, `partial`, `empty`, `error`, `warming` | ✅ |  |
| `meta.warnings` | array<string> |  |  |
| `meta.error` | SourceError \| null |  |  |
| `meta.generated_at` | string | ✅ | 응답 생성 시각 (RFC 3339, UTC) |
| `meta.source_mtime` | string \| null |  | 읽은 소스 파일 중 가장 최근 수정 시각 (RFC 3339, UTC) |

```json
{
  "data": {
    "scope": "string",
    "range": "5h",
    "bucket": "hour",
    "group": "model",
    "tz_offset_min": 0,
    "start": "string",
    "end": "string",
    "buckets": [
      "string"
    ],
    "series": [
      {
        "key": "string",
        "responses": [
          null
        ],
        "input_tokens": [
          null
        ],
        "output_tokens": [
          null
        ],
        "cache_creation_input_tokens": [
          null
        ],
        "cache_read_input_tokens": [
          null
        ]
      }
    ],
    "totals": {
      "responses": 0,
      "input_tokens": 0,
      "output_tokens": 0,
      "cache_creation_input_tokens": 0,
      "cache_read_input_tokens": 0,
      "cache_hit_rate": 0.0
    },
    "project_dir_found": true,
    "warming": {
      "state": "not_started",
      "progress": 0.0
    }
  },
  "meta": {
    "status": "ok",
    "warnings": [
      "string"
    ],
    "error": {
      "code": "SOURCE_MISSING",
      "message": "string"
    },
    "generated_at": "string",
    "source_mtime": "string"
  }
}
```

#### 예시

```bash
curl -X GET 'http://127.0.0.1:8765/api/v1/usage/timeseries'
```

## events

### GET /api/v1/events

**변경 알림 스트림 (text/event-stream)**

`changed{topics}`·`warming`·`ready` 이벤트와 15초 keep-alive. 형식 기준은 contracts/sse-events.md.

- **인증:** 불필요
- **operationId:** `get_events`

#### 응답

| 상태 코드 | 설명 | 본문 |
|---|---|---|
| `200` | Successful Response | - |
| `400` | BAD_HOST — Host 가드 | ErrorResponse |
| `405` | METHOD_NOT_ALLOWED — `Allow` 헤더 포함 (OPTIONS·HEAD 포함) | ErrorResponse |
| `500` | INTERNAL_ERROR | ErrorResponse |
| `503` | TOO_MANY_STREAMS — 동시 연결 상한 8 | - |

#### 예시

```bash
curl -X GET 'http://127.0.0.1:8765/api/v1/events'
```

## health

### GET /api/v1/health

**생존·소스 접근 가능 여부·데우기 진행률·앱 식별자**

소스 문제는 HTTP 200 + `meta.status=partial`. 런처는 `data.app == "aidlc-monitor"` 로 판정한다.

- **인증:** 불필요
- **operationId:** `get_health`

#### 응답

| 상태 코드 | 설명 | 본문 |
|---|---|---|
| `200` | Successful Response | Envelope_HealthData_ |
| `400` | BAD_HOST — Host 가드 | ErrorResponse |
| `405` | METHOD_NOT_ALLOWED — `Allow` 헤더 포함 (OPTIONS·HEAD 포함) | ErrorResponse |
| `500` | INTERNAL_ERROR | ErrorResponse |

`200` 응답 필드

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `data` | HealthData \| null | ✅ |  |
| `meta` | Meta | ✅ |  |
| `meta.status` | string enum: `ok`, `partial`, `empty`, `error`, `warming` | ✅ |  |
| `meta.warnings` | array<string> |  |  |
| `meta.error` | SourceError \| null |  |  |
| `meta.generated_at` | string | ✅ | 응답 생성 시각 (RFC 3339, UTC) |
| `meta.source_mtime` | string \| null |  | 읽은 소스 파일 중 가장 최근 수정 시각 (RFC 3339, UTC) |

```json
{
  "data": {
    "status": "string",
    "app": "string",
    "version": "string",
    "sources": {
      "workspace": "ok",
      "claude_projects": "ok",
      "statusline": "ok",
      "control": "ok"
    },
    "dist": "ok",
    "usage_warming": {
      "state": "not_started",
      "progress": 0.0
    }
  },
  "meta": {
    "status": "ok",
    "warnings": [
      "string"
    ],
    "error": {
      "code": "SOURCE_MISSING",
      "message": "string"
    },
    "generated_at": "string",
    "source_mtime": "string"
  }
}
```

#### 예시

```bash
curl -X GET 'http://127.0.0.1:8765/api/v1/health'
```

## 스키마

### ControlData

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `state` | string enum: `running`, `pause_requested`, `paused`, `resume_requested`, `no_session`, `ended` | ✅ | 화면 상태 (ADR-004 §4). loop-status 없음·ended = ended |
| `view` | string enum: `V1`, `V2`, `V3`, `V4`, `V5`, `V6` | ✅ | stories/FR-005 §2.1 V1~V6 |
| `label` | string | ✅ | 화면 라벨 (FR-005 §2.1 정확한 문구) |
| `hint` | string \| null | ✅ | V1 남은 반복 / V6 재실행 안내 (FR-005 §2.1 추가 표시) |
| `can_pause` | boolean | ✅ | 일시정지 버튼 활성 (FR-005 §2.2) |
| `can_resume` | boolean | ✅ | 재개 버튼 활성 (FR-005 §2.2) |
| `requested_state` | string enum: `running`, `pause` \| null | ✅ | `.control.json` state (정상 파일일 때만) |
| `requested_at` | string \| null | ✅ |  |
| `control_seq` | integer \| null | ✅ |  |
| `baseline_seq` | integer \| null | ✅ |  |
| `control_file` | string enum: `ok`, `missing`, `broken`, `unreadable` | ✅ | `.control.json` 판독 결과 (없음은 정상) |
| `loop_file` | string enum: `ok`, `missing`, `broken`, `unreadable` | ✅ | `loop-status.json` 판독 결과 |
| `loop_state` | string enum: `running`, `paused`, `ended` \| null | ✅ |  |
| `paused_since` | string \| null | ✅ |  |
| `heartbeat_at` | string \| null | ✅ |  |
| `heartbeat_age_sec` | integer \| null | ✅ | 세션 생존 판정은 paused 에서만 (> 120 s = no_session, D-11) |
| `iterations_done` | integer \| null | ✅ |  |
| `iterations_total` | integer \| null | ✅ |  |
| `remaining_iterations` | integer \| null | ✅ |  |
| `max_pause_sec` | integer | ✅ |  |
| `pause_elapsed_sec` | integer \| null | ✅ |  |
| `remaining_pause_sec` | integer \| null | ✅ | paused 일 때 max_pause_sec − 경과 |
| `session_activity_at` | string \| null |  | V3 세션 활동 = 이 프로젝트 JSONL 최근 기록 시각 (RFC 3339 UTC). 사용량 데우기 전이면 null |
| `session_activity_age_sec` | integer \| null |  | session_activity_at 경과 초 |
| `ended_reason` | string enum: `done`, `blocked`, `no_task`, `pause_timeout` \| null | ✅ |  |
| `ended_message` | string \| null | ✅ | V1 종료 사유 문구 (FR-005 §2.3) |

### Envelope_ControlData_

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `data` | ControlData \| null | ✅ |  |
| `meta` | Meta | ✅ |  |
| `meta.status` | string enum: `ok`, `partial`, `empty`, `error`, `warming` | ✅ |  |
| `meta.warnings` | array<string> |  |  |
| `meta.error` | SourceError \| null |  |  |
| `meta.generated_at` | string | ✅ | 응답 생성 시각 (RFC 3339, UTC) |
| `meta.source_mtime` | string \| null |  | 읽은 소스 파일 중 가장 최근 수정 시각 (RFC 3339, UTC) |

### Envelope_HealthData_

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `data` | HealthData \| null | ✅ |  |
| `meta` | Meta | ✅ |  |
| `meta.status` | string enum: `ok`, `partial`, `empty`, `error`, `warming` | ✅ |  |
| `meta.warnings` | array<string> |  |  |
| `meta.error` | SourceError \| null |  |  |
| `meta.generated_at` | string | ✅ | 응답 생성 시각 (RFC 3339, UTC) |
| `meta.source_mtime` | string \| null |  | 읽은 소스 파일 중 가장 최근 수정 시각 (RFC 3339, UTC) |

### Envelope_MemoryData_

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `data` | MemoryData \| null | ✅ |  |
| `meta` | Meta | ✅ |  |
| `meta.status` | string enum: `ok`, `partial`, `empty`, `error`, `warming` | ✅ |  |
| `meta.warnings` | array<string> |  |  |
| `meta.error` | SourceError \| null |  |  |
| `meta.generated_at` | string | ✅ | 응답 생성 시각 (RFC 3339, UTC) |
| `meta.source_mtime` | string \| null |  | 읽은 소스 파일 중 가장 최근 수정 시각 (RFC 3339, UTC) |

### Envelope_PipelineData_

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `data` | PipelineData \| null | ✅ |  |
| `meta` | Meta | ✅ |  |
| `meta.status` | string enum: `ok`, `partial`, `empty`, `error`, `warming` | ✅ |  |
| `meta.warnings` | array<string> |  |  |
| `meta.error` | SourceError \| null |  |  |
| `meta.generated_at` | string | ✅ | 응답 생성 시각 (RFC 3339, UTC) |
| `meta.source_mtime` | string \| null |  | 읽은 소스 파일 중 가장 최근 수정 시각 (RFC 3339, UTC) |

### Envelope_PlanData_

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `data` | PlanData \| null | ✅ |  |
| `meta` | Meta | ✅ |  |
| `meta.status` | string enum: `ok`, `partial`, `empty`, `error`, `warming` | ✅ |  |
| `meta.warnings` | array<string> |  |  |
| `meta.error` | SourceError \| null |  |  |
| `meta.generated_at` | string | ✅ | 응답 생성 시각 (RFC 3339, UTC) |
| `meta.source_mtime` | string \| null |  | 읽은 소스 파일 중 가장 최근 수정 시각 (RFC 3339, UTC) |

### Envelope_TasksData_

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `data` | TasksData \| null | ✅ |  |
| `meta` | Meta | ✅ |  |
| `meta.status` | string enum: `ok`, `partial`, `empty`, `error`, `warming` | ✅ |  |
| `meta.warnings` | array<string> |  |  |
| `meta.error` | SourceError \| null |  |  |
| `meta.generated_at` | string | ✅ | 응답 생성 시각 (RFC 3339, UTC) |
| `meta.source_mtime` | string \| null |  | 읽은 소스 파일 중 가장 최근 수정 시각 (RFC 3339, UTC) |

### Envelope_UsageSummaryData_

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `data` | UsageSummaryData \| null | ✅ |  |
| `meta` | Meta | ✅ |  |
| `meta.status` | string enum: `ok`, `partial`, `empty`, `error`, `warming` | ✅ |  |
| `meta.warnings` | array<string> |  |  |
| `meta.error` | SourceError \| null |  |  |
| `meta.generated_at` | string | ✅ | 응답 생성 시각 (RFC 3339, UTC) |
| `meta.source_mtime` | string \| null |  | 읽은 소스 파일 중 가장 최근 수정 시각 (RFC 3339, UTC) |

### Envelope_UsageTimeseriesData_

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `data` | UsageTimeseriesData \| null | ✅ |  |
| `meta` | Meta | ✅ |  |
| `meta.status` | string enum: `ok`, `partial`, `empty`, `error`, `warming` | ✅ |  |
| `meta.warnings` | array<string> |  |  |
| `meta.error` | SourceError \| null |  |  |
| `meta.generated_at` | string | ✅ | 응답 생성 시각 (RFC 3339, UTC) |
| `meta.source_mtime` | string \| null |  | 읽은 소스 파일 중 가장 최근 수정 시각 (RFC 3339, UTC) |

### ErrorCode

타입: string enum: `VALIDATION_ERROR`, `NOT_FOUND`, `METHOD_NOT_ALLOWED`, `BAD_HOST`, `FORBIDDEN_ORIGIN`, `NO_ACTIVE_LOOP`, `TOO_MANY_STREAMS`, `CONTROL_WRITE_FAILED`, `INTERNAL_ERROR`

### ErrorDetail

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `code` | ErrorCode enum: `VALIDATION_ERROR`, `NOT_FOUND`, `METHOD_NOT_ALLOWED`, `BAD_HOST`, `FORBIDDEN_ORIGIN`, `NO_ACTIVE_LOOP`, `TOO_MANY_STREAMS`, `CONTROL_WRITE_FAILED`, `INTERNAL_ERROR` | ✅ |  |
| `message` | string | ✅ |  |

### ErrorResponse

요청 오류 본문 `{"error": {"code", "message"}}` (02 §6). 코드는 닫힌 집합 9개.

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `error` | ErrorDetail | ✅ |  |
| `error.code` | ErrorCode enum: `VALIDATION_ERROR`, `NOT_FOUND`, `METHOD_NOT_ALLOWED`, `BAD_HOST`, `FORBIDDEN_ORIGIN`, `NO_ACTIVE_LOOP`, `TOO_MANY_STREAMS`, `CONTROL_WRITE_FAILED`, `INTERNAL_ERROR` | ✅ |  |
| `error.message` | string | ✅ |  |

### Gate

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `layer` | string enum: `user`, `project`, `docs` | ✅ |  |
| `result` | string enum: `PASS`, `FAIL`, `UNKNOWN` | ✅ |  |
| `unwritten` | integer \| null | ✅ | 미작성 플레이스홀더 수 (대상 없음·확인 불가면 null) |
| `missing` | integer \| null | ✅ | 누락 문서 수 (대상 없음·확인 불가면 null) |
| `target_missing` | boolean | ✅ | 대상 디렉터리 없음 (FAIL + '대상 없음') |
| `no_documents` | boolean | ✅ | 검사 대상 문서 0개로 PASS (R5) |
| `error_code` | SourceErrorCode enum: `SOURCE_MISSING`, `SOURCE_PARSE_ERROR`, `SOURCE_UNREADABLE`, `GATE_TIMEOUT`, `PROJECT_DIR_NOT_FOUND`, `SNAPSHOT_STALE` \| null |  |  |
| `checked_at` | string \| null | ✅ |  |

### HealthData

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `status` | string | ✅ | 프로세스 생존. 응답이 오면 항상 ok |
| `app` | string | ✅ | 앱 식별자. 런처의 중복 실행 판정용 — 값 고정 |
| `version` | string | ✅ |  |
| `sources` | HealthSources | ✅ | 데이터 소스별 접근 가능 여부. 파일 내용은 읽지 않고 메타데이터(stat)만 본다. |
| `sources.workspace` | string enum: `ok`, `missing`, `stale`, `unreadable` | ✅ | `<AIDLC_ROOT>/workspace/memory` 디렉터리 |
| `sources.claude_projects` | string enum: `ok`, `missing`, `stale`, `unreadable` | ✅ | `<CLAUDE_HOME>/projects` 디렉터리 (사용량 기록 위치) |
| `sources.statusline` | string enum: `ok`, `missing`, `stale`, `unreadable` | ✅ | status line 스냅샷 파일. 없음 = statusLine 미실행 또는 첫 응답 전 |
| `sources.control` | string enum: `ok`, `missing`, `stale`, `unreadable` | ✅ | `.control.json`. 없음은 정상(첫 일시정지 전)이라 경고를 만들지 않는다 |
| `dist` | string enum: `ok`, `missing` | ✅ | 프론트 dist(index.html) 유무 (ADR-005 §3) |
| `usage_warming` | UsageWarming | ✅ | 사용량 캐시 데우기 진행률 (ADR-002 §6). 수집기(T-010) 전에는 `not_started`. |
| `usage_warming.state` | string enum: `not_started`, `warming`, `done`, `unknown` | ✅ |  |
| `usage_warming.progress` | number \| null |  | 0.0~1.0, 모르면 null |

### HealthSources

데이터 소스별 접근 가능 여부. 파일 내용은 읽지 않고 메타데이터(stat)만 본다.

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `workspace` | string enum: `ok`, `missing`, `stale`, `unreadable` | ✅ | `<AIDLC_ROOT>/workspace/memory` 디렉터리 |
| `claude_projects` | string enum: `ok`, `missing`, `stale`, `unreadable` | ✅ | `<CLAUDE_HOME>/projects` 디렉터리 (사용량 기록 위치) |
| `statusline` | string enum: `ok`, `missing`, `stale`, `unreadable` | ✅ | status line 스냅샷 파일. 없음 = statusLine 미실행 또는 첫 응답 전 |
| `control` | string enum: `ok`, `missing`, `stale`, `unreadable` | ✅ | `.control.json`. 없음은 정상(첫 일시정지 전)이라 경고를 만들지 않는다 |

### LimitWindow

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `used_percentage` | number \| null | ✅ | 0~100 (계정 전체 기준) |
| `resets_at` | integer \| null | ✅ | 초기화 시각, Unix epoch 초 |
| `resets_at_iso` | string \| null | ✅ | 초기화 시각 (RFC 3339, UTC) |
| `reset_passed` | boolean \| null | ✅ | 초기화 시각이 지났음 — '새 응답 후 갱신' 안내 |

### MemoryData

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `stm` | StmView | ✅ |  |
| `stm.status` | string enum: `idle`, `active`, `closed`, `unknown` \| null | ✅ | STM 을 읽지 못하면 null |
| `stm.task` | string \| null | ✅ |  |
| `stm.team` | string \| null | ✅ |  |
| `stm.outcome` | string \| null | ✅ |  |
| `stm.opened_at` | string \| null | ✅ |  |
| `stm.elapsed_sec` | integer \| null | ✅ | 현재 − opened_at (초). 없음·형식 오류·미래면 null |
| `stm.error_code` | SourceErrorCode enum: `SOURCE_MISSING`, `SOURCE_PARSE_ERROR`, `SOURCE_UNREADABLE`, `GATE_TIMEOUT`, `PROJECT_DIR_NOT_FOUND`, `SNAPSHOT_STALE` \| null |  |  |
| `ltm_rev` | integer \| null | ✅ |  |
| `last_merged_stm` | integer \| null | ✅ |  |
| `tasks_rev` | integer \| null | ✅ |  |
| `synced_ltm_rev` | integer \| null | ✅ |  |
| `current_phase` | string \| null | ✅ |  |
| `completed_phases` | array<string> \| null | ✅ |  |
| `archive_count` | integer \| null | ✅ |  |
| `latest_archive_seq` | integer \| null | ✅ |  |
| `pending_cascade` | string enum: `none`, `ltm`, `tasks`, `plan`, `unknown` | ✅ | Hook Memory.pending().level (없음 = none, 판정 불가 = unknown) |
| `stop_blocks` | integer \| null | ✅ | Stop Hook 연속 차단 횟수 (.cascade-state.json) |

### Meta

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `status` | string enum: `ok`, `partial`, `empty`, `error`, `warming` | ✅ |  |
| `warnings` | array<string> |  |  |
| `error` | SourceError \| null |  |  |
| `generated_at` | string | ✅ | 응답 생성 시각 (RFC 3339, UTC) |
| `source_mtime` | string \| null |  | 읽은 소스 파일 중 가장 최근 수정 시각 (RFC 3339, UTC) |

### PauseRequest

본문 `{}` 또는 `{"max_pause_sec": 600~86400}` (정수 리터럴만 — bool·600.0 은 422).

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `max_pause_sec` | integer \| null |  | 일시정지 1회 상한(초). 생략 시 7200 |

### PhaseProgress

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `phase` | string | ✅ |  |
| `title` | string | ✅ |  |
| `total` | integer | ✅ |  |
| `checked` | integer | ✅ |  |
| `percent` | integer | ✅ | floor(checked / total × 100), total 0 이면 0 |
| `completed` | boolean \| null | ✅ | plan completed_phases 에 있음 (plan 을 못 읽으면 null) |
| `current` | boolean \| null | ✅ | plan current_phase 와 같음 (plan 을 못 읽으면 null) |

### PipelineData

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `current_stage` | integer | ✅ |  |
| `current_stage_name` | string | ✅ |  |
| `next_command` | string \| null | ✅ | 다음에 실행할 명령. 전체 완료면 null |
| `all_done` | boolean | ✅ |  |
| `stages` | array<Stage> | ✅ |  |
| `stages[].index` | integer | ✅ |  |
| `stages[].name` | string | ✅ |  |
| `stages[].command` | string | ✅ |  |
| `stages[].state` | string enum: `done`, `in_progress`, `waiting`, `unknown` | ✅ |  |
| `gates` | array<Gate> | ✅ |  |
| `gates[].layer` | string enum: `user`, `project`, `docs` | ✅ |  |
| `gates[].result` | string enum: `PASS`, `FAIL`, `UNKNOWN` | ✅ |  |
| `gates[].unwritten` | integer \| null | ✅ | 미작성 플레이스홀더 수 (대상 없음·확인 불가면 null) |
| `gates[].missing` | integer \| null | ✅ | 누락 문서 수 (대상 없음·확인 불가면 null) |
| `gates[].target_missing` | boolean | ✅ | 대상 디렉터리 없음 (FAIL + '대상 없음') |
| `gates[].no_documents` | boolean | ✅ | 검사 대상 문서 0개로 PASS (R5) |
| `gates[].error_code` | SourceErrorCode enum: `SOURCE_MISSING`, `SOURCE_PARSE_ERROR`, `SOURCE_UNREADABLE`, `GATE_TIMEOUT`, `PROJECT_DIR_NOT_FOUND`, `SNAPSHOT_STALE` \| null |  |  |
| `gates[].checked_at` | string \| null | ✅ |  |

### PlanData

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `current_phase` | string \| null | ✅ |  |
| `completed_phases` | array<string> \| null | ✅ |  |
| `phases` | array<PhaseProgress> | ✅ |  |
| `phases[].phase` | string | ✅ |  |
| `phases[].title` | string | ✅ |  |
| `phases[].total` | integer | ✅ |  |
| `phases[].checked` | integer | ✅ |  |
| `phases[].percent` | integer | ✅ | floor(checked / total × 100), total 0 이면 0 |
| `phases[].completed` | boolean \| null | ✅ | plan completed_phases 에 있음 (plan 을 못 읽으면 null) |
| `phases[].current` | boolean \| null | ✅ | plan current_phase 와 같음 (plan 을 못 읽으면 null) |

### ResumeRequest

본문 `{}`. 재개는 이전 `max_pause_sec` 를 유지한다.

타입: object

### SnapshotInfo

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `state` | string enum: `ok`, `missing`, `broken`, `unreadable` | ✅ | 스냅샷 파일 판독 결과 |
| `captured_at` | string \| null | ✅ |  |
| `age_sec` | integer \| null | ✅ | captured_at 경과 초 |
| `stale` | boolean | ✅ | 600 초 초과 (SNAPSHOT_STALE) |
| `code` | SourceErrorCode enum: `SOURCE_MISSING`, `SOURCE_PARSE_ERROR`, `SOURCE_UNREADABLE`, `GATE_TIMEOUT`, `PROJECT_DIR_NOT_FOUND`, `SNAPSHOT_STALE` \| null | ✅ | 한도 영역 코드: SOURCE_MISSING / SOURCE_PARSE_ERROR / SOURCE_UNREADABLE / SNAPSHOT_STALE |

### SourceError

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `code` | SourceErrorCode enum: `SOURCE_MISSING`, `SOURCE_PARSE_ERROR`, `SOURCE_UNREADABLE`, `GATE_TIMEOUT`, `PROJECT_DIR_NOT_FOUND`, `SNAPSHOT_STALE` | ✅ | 패널 `meta.error.code` (20 §5). HTTP 에러 코드 집합과 별개다. |
| `message` | string | ✅ |  |

### SourceErrorCode

패널 `meta.error.code` (20 §5). HTTP 에러 코드 집합과 별개다.

타입: string enum: `SOURCE_MISSING`, `SOURCE_PARSE_ERROR`, `SOURCE_UNREADABLE`, `GATE_TIMEOUT`, `PROJECT_DIR_NOT_FOUND`, `SNAPSHOT_STALE`

### Stage

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `index` | integer | ✅ |  |
| `name` | string | ✅ |  |
| `command` | string | ✅ |  |
| `state` | string enum: `done`, `in_progress`, `waiting`, `unknown` | ✅ |  |

### StmView

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `status` | string enum: `idle`, `active`, `closed`, `unknown` \| null | ✅ | STM 을 읽지 못하면 null |
| `task` | string \| null | ✅ |  |
| `team` | string \| null | ✅ |  |
| `outcome` | string \| null | ✅ |  |
| `opened_at` | string \| null | ✅ |  |
| `elapsed_sec` | integer \| null | ✅ | 현재 − opened_at (초). 없음·형식 오류·미래면 null |
| `error_code` | SourceErrorCode enum: `SOURCE_MISSING`, `SOURCE_PARSE_ERROR`, `SOURCE_UNREADABLE`, `GATE_TIMEOUT`, `PROJECT_DIR_NOT_FOUND`, `SNAPSHOT_STALE` \| null |  |  |

### TaskItem

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `id` | string \| null | ✅ | T-ID. 형식 불일치 줄이면 null |
| `team` | string \| null | ✅ |  |
| `title` | string | ✅ |  |
| `refs` | array<string> | ✅ | 제목 뒤 `—` 다음의 요구사항·이슈 ID (FR-001 등) |
| `deps` | array<string> | ✅ |  |
| `phase` | string | ✅ |  |
| `checked` | boolean | ✅ |  |
| `status` | TaskStatus enum: `open`, `done`, `blocked`, `active` | ✅ |  |
| `well_formed` | boolean | ✅ |  |

### TaskStatus

타입: string enum: `open`, `done`, `blocked`, `active`

### TasksData

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `total` | integer | ✅ | 필터 전 Phase 섹션의 Task 수 |
| `items` | array<TaskItem> | ✅ |  |
| `items[].id` | string \| null | ✅ | T-ID. 형식 불일치 줄이면 null |
| `items[].team` | string \| null | ✅ |  |
| `items[].title` | string | ✅ |  |
| `items[].refs` | array<string> | ✅ | 제목 뒤 `—` 다음의 요구사항·이슈 ID (FR-001 등) |
| `items[].deps` | array<string> | ✅ |  |
| `items[].phase` | string | ✅ |  |
| `items[].checked` | boolean | ✅ |  |
| `items[].status` | TaskStatus enum: `open`, `done`, `blocked`, `active` | ✅ |  |
| `items[].well_formed` | boolean | ✅ |  |

### TokenSeries

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `key` | string | ✅ | group=model → 모델 id, sidechain → main\|subagent, none → all |
| `responses` | array<integer> | ✅ |  |
| `input_tokens` | array<integer> | ✅ |  |
| `output_tokens` | array<integer> | ✅ |  |
| `cache_creation_input_tokens` | array<integer> | ✅ |  |
| `cache_read_input_tokens` | array<integer> | ✅ |  |

### TokenTotals

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `responses` | integer | ✅ | 고유 응답 수 (requestId 중복 제거 후) |
| `input_tokens` | integer | ✅ |  |
| `output_tokens` | integer | ✅ |  |
| `cache_creation_input_tokens` | integer | ✅ |  |
| `cache_read_input_tokens` | integer | ✅ |  |
| `cache_hit_rate` | number \| null | ✅ | cache_read / (input + cache_creation + cache_read), 분모 0 이면 null |

### TokenWindow

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `start` | string | ✅ | 구간 시작 (RFC 3339) |
| `end` | string | ✅ | 구간 끝 = 현재 (RFC 3339) |
| `estimated` | boolean | ✅ | true = 이동 구간 추정(스냅샷 resets_at 없음). 집계는 1시간 버킷 단위 |
| `totals` | TokenTotals | ✅ |  |
| `totals.responses` | integer | ✅ | 고유 응답 수 (requestId 중복 제거 후) |
| `totals.input_tokens` | integer | ✅ |  |
| `totals.output_tokens` | integer | ✅ |  |
| `totals.cache_creation_input_tokens` | integer | ✅ |  |
| `totals.cache_read_input_tokens` | integer | ✅ |  |
| `totals.cache_hit_rate` | number \| null | ✅ | cache_read / (input + cache_creation + cache_read), 분모 0 이면 null |

### UsageSummaryData

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `scope` | string | ✅ | 토큰은 이 프로젝트 기준 (A13) |
| `limits_available` | boolean | ✅ | 스냅샷에 한도 값이 있음. false 면 limits_notice 를 표시 |
| `limits_notice` | string \| null | ✅ |  |
| `five_hour` | LimitWindow \| null | ✅ |  |
| `seven_day` | LimitWindow \| null | ✅ |  |
| `snapshot` | SnapshotInfo | ✅ |  |
| `snapshot.state` | string enum: `ok`, `missing`, `broken`, `unreadable` | ✅ | 스냅샷 파일 판독 결과 |
| `snapshot.captured_at` | string \| null | ✅ |  |
| `snapshot.age_sec` | integer \| null | ✅ | captured_at 경과 초 |
| `snapshot.stale` | boolean | ✅ | 600 초 초과 (SNAPSHOT_STALE) |
| `snapshot.code` | SourceErrorCode enum: `SOURCE_MISSING`, `SOURCE_PARSE_ERROR`, `SOURCE_UNREADABLE`, `GATE_TIMEOUT`, `PROJECT_DIR_NOT_FOUND`, `SNAPSHOT_STALE` \| null | ✅ | 한도 영역 코드: SOURCE_MISSING / SOURCE_PARSE_ERROR / SOURCE_UNREADABLE / SNAPSHOT_STALE |
| `session_cost_usd` | number \| null | ✅ | 세션 비용(추정), 최근 세션 |
| `session_duration_ms` | integer \| null | ✅ |  |
| `context_used_percentage` | number \| null | ✅ |  |
| `model_id` | string \| null | ✅ |  |
| `project_dir_found` | boolean | ✅ |  |
| `tokens_code` | SourceErrorCode enum: `SOURCE_MISSING`, `SOURCE_PARSE_ERROR`, `SOURCE_UNREADABLE`, `GATE_TIMEOUT`, `PROJECT_DIR_NOT_FOUND`, `SNAPSHOT_STALE` \| null | ✅ | 토큰 영역 코드: PROJECT_DIR_NOT_FOUND |
| `today` | TokenWindow | ✅ |  |
| `today.start` | string | ✅ | 구간 시작 (RFC 3339) |
| `today.end` | string | ✅ | 구간 끝 = 현재 (RFC 3339) |
| `today.estimated` | boolean | ✅ | true = 이동 구간 추정(스냅샷 resets_at 없음). 집계는 1시간 버킷 단위 |
| `today.totals` | TokenTotals | ✅ |  |
| `today.totals.responses` | integer | ✅ | 고유 응답 수 (requestId 중복 제거 후) |
| `today.totals.input_tokens` | integer | ✅ |  |
| `today.totals.output_tokens` | integer | ✅ |  |
| `today.totals.cache_creation_input_tokens` | integer | ✅ |  |
| `today.totals.cache_read_input_tokens` | integer | ✅ |  |
| `today.totals.cache_hit_rate` | number \| null | ✅ | cache_read / (input + cache_creation + cache_read), 분모 0 이면 null |
| `five_hour_tokens` | TokenWindow | ✅ |  |
| `five_hour_tokens.start` | string | ✅ | 구간 시작 (RFC 3339) |
| `five_hour_tokens.end` | string | ✅ | 구간 끝 = 현재 (RFC 3339) |
| `five_hour_tokens.estimated` | boolean | ✅ | true = 이동 구간 추정(스냅샷 resets_at 없음). 집계는 1시간 버킷 단위 |
| `five_hour_tokens.totals` | TokenTotals | ✅ |  |
| `five_hour_tokens.totals.responses` | integer | ✅ | 고유 응답 수 (requestId 중복 제거 후) |
| `five_hour_tokens.totals.input_tokens` | integer | ✅ |  |
| `five_hour_tokens.totals.output_tokens` | integer | ✅ |  |
| `five_hour_tokens.totals.cache_creation_input_tokens` | integer | ✅ |  |
| `five_hour_tokens.totals.cache_read_input_tokens` | integer | ✅ |  |
| `five_hour_tokens.totals.cache_hit_rate` | number \| null | ✅ | cache_read / (input + cache_creation + cache_read), 분모 0 이면 null |
| `skipped_lines` | integer | ✅ | 형식 오류로 건너뛴 기록 줄 수 |
| `warming` | UsageWarming | ✅ | 사용량 캐시 데우기 진행률 (ADR-002 §6). 수집기(T-010) 전에는 `not_started`. |
| `warming.state` | string enum: `not_started`, `warming`, `done`, `unknown` | ✅ |  |
| `warming.progress` | number \| null |  | 0.0~1.0, 모르면 null |

### UsageTimeseriesData

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `scope` | string | ✅ |  |
| `range` | string enum: `5h`, `24h`, `7d`, `30d` | ✅ |  |
| `bucket` | string enum: `hour`, `day` | ✅ |  |
| `group` | string enum: `model`, `sidechain`, `none` | ✅ |  |
| `tz_offset_min` | integer | ✅ |  |
| `start` | string | ✅ |  |
| `end` | string | ✅ |  |
| `buckets` | array<string> | ✅ | 버킷 시작 시각 목록 (hour = UTC 정시, day = 로컬 자정, RFC 3339). series 값과 같은 순서 |
| `series` | array<TokenSeries> | ✅ |  |
| `series[].key` | string | ✅ | group=model → 모델 id, sidechain → main\|subagent, none → all |
| `series[].responses` | array<integer> | ✅ |  |
| `series[].input_tokens` | array<integer> | ✅ |  |
| `series[].output_tokens` | array<integer> | ✅ |  |
| `series[].cache_creation_input_tokens` | array<integer> | ✅ |  |
| `series[].cache_read_input_tokens` | array<integer> | ✅ |  |
| `totals` | TokenTotals | ✅ |  |
| `totals.responses` | integer | ✅ | 고유 응답 수 (requestId 중복 제거 후) |
| `totals.input_tokens` | integer | ✅ |  |
| `totals.output_tokens` | integer | ✅ |  |
| `totals.cache_creation_input_tokens` | integer | ✅ |  |
| `totals.cache_read_input_tokens` | integer | ✅ |  |
| `totals.cache_hit_rate` | number \| null | ✅ | cache_read / (input + cache_creation + cache_read), 분모 0 이면 null |
| `project_dir_found` | boolean | ✅ |  |
| `warming` | UsageWarming | ✅ | 사용량 캐시 데우기 진행률 (ADR-002 §6). 수집기(T-010) 전에는 `not_started`. |
| `warming.state` | string enum: `not_started`, `warming`, `done`, `unknown` | ✅ |  |
| `warming.progress` | number \| null |  | 0.0~1.0, 모르면 null |

### UsageWarming

사용량 캐시 데우기 진행률 (ADR-002 §6). 수집기(T-010) 전에는 `not_started`.

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `state` | string enum: `not_started`, `warming`, `done`, `unknown` | ✅ |  |
| `progress` | number \| null |  | 0.0~1.0, 모르면 null |
