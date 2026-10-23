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

### UsageWarming

사용량 캐시 데우기 진행률 (ADR-002 §6). 수집기(T-010) 전에는 `not_started`.

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `state` | string enum: `not_started`, `warming`, `done`, `unknown` | ✅ |  |
| `progress` | number \| null |  | 0.0~1.0, 모르면 null |
