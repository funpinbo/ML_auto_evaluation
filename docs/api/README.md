---
doc: api-overview
layer: docs
author: team-product (docs 팀 없음 — /aidlc-docs 오케스트레이터 지시)
spec: workspace/project/contracts/openapi.json
api_version: 0.1.0
---
# AI-DLC Monitor API — API 가이드

> 이 문서는 **사람이 읽는 개요**입니다. 엔드포인트별 상세는 자동 생성되는 [레퍼런스](./reference.md)를 보세요.
> 근거: OpenAPI 명세(`workspace/project/contracts/openapi.json`), user/02 §6 API 규칙, LTM 결정 사항, SSE 계약(`workspace/project/contracts/sse-events.md`), 실서버 호출 확인(2026-10-26).

이 API 는 대시보드 화면이 쓰는 **내 PC 전용** API 입니다. 인증이 없고 `127.0.0.1` 에서만 열립니다. 조회(GET) 8개 + 변경 요청(POST) 2개 + 알림 스트림(SSE) 1개, 총 11개 엔드포인트입니다.

## 1. 시작하기
| 환경 | Base URL |
|------|----------|
| 로컬 (기본 포트) | `http://127.0.0.1:8765` |
| 로컬 (포트 변경 시) | `http://127.0.0.1:<포트>` — `python run.py --port N` 또는 `AIDLC_MONITOR_PORT` |

원격 배포 환경은 없습니다. 서버는 `127.0.0.1` 에만 바인딩되고 바꿀 수 없습니다.

첫 호출까지 3단계:
1. 서버를 켭니다: 저장소 루트에서 `./run.sh --no-browser` (Windows 는 `run.bat --no-browser`). 설치 방법은 [monitor/README.md](../../monitor/README.md).
2. 인증 정보 발급·토큰 설정은 **필요 없습니다**.
3. 헬스 체크:
```bash
curl -s http://127.0.0.1:8765/api/v1/health
```
실제 응답(2026-10-26 Linux 컨테이너, 이 저장소 커밋을 깨끗한 복사본에서 실행) 일부:
```json
{"data":{"status":"ok","app":"aidlc-monitor","version":"0.1.0","sources":{"workspace":"ok","claude_projects":"ok","statusline":"missing","control":"missing"},"dist":"ok","usage_warming":{"state":"done","progress":1.0}},"meta":{"status":"partial","warnings":["status line 스냅샷이 없습니다 (statusLine 미실행 또는 첫 응답 전)."],"error":null,"generated_at":"2026-10-26T00:02:00Z","source_mtime":null}}
```
`data.app` 이 `aidlc-monitor` 이면 이 대시보드입니다(런처가 중복 실행을 판정하는 값). 소스가 없어도 HTTP 200 이고 `meta.status` 가 `partial` 이 됩니다.

## 2. 인증
- 방식: **없음** (user/02 §6 — 127.0.0.1 바인딩으로 대체).
- 인증이 필요 없는 엔드포인트: 전부.
- 대신 두 가지 요청 가드가 있습니다.
  - **Host 가드(모든 요청)**: `Host` 헤더가 `127.0.0.1:<서버 포트>` 또는 `localhost:<서버 포트>` 가 아니면 400 `BAD_HOST`.
  - **쓰기 가드(GET·HEAD·OPTIONS 가 아닌 모든 요청)**: `Content-Type: application/json` 이 아니거나 `Origin` 이 허용 주소와 다르면 403 `FORBIDDEN_ORIGIN`. 즉 `curl` 로 POST 할 때 `-H 'Content-Type: application/json'` 이 필요합니다.
- CORS 는 열려 있지 않습니다. 같은 출처(대시보드 화면)에서만 쓰도록 설계되었습니다.

## 3. 리소스 모델
이 API 는 AI-DLC 저장소의 **파일 상태를 읽어 보여 주는 뷰**입니다. 서버는 상태를 저장하지 않고, 요청마다 파일을 읽어 계산합니다(user/03 §3). 쓰기는 `workspace/memory/.control.json` 하나뿐입니다.

| 리소스 | 경로 | 설명 | 관계 |
|--------|------|------|------|
| pipeline | `/api/v1/pipeline` | 단계 0~6 상태, 현재 단계, 다음 명령, 문서 Gate 3종 (FR-001) | 문서(user/project/teams/plan) 존재·내용에서 판정 |
| plan | `/api/v1/plan` | Phase 별 진행률, 현재·완료 Phase (FR-002) | tasks 와 같은 소스(plan.md, tasks.md) |
| tasks | `/api/v1/tasks` | Task 목록, `team`·`status`·`phase` 필터 (FR-002) | plan 의 Phase 1─N Task |
| memory | `/api/v1/memory` | STM·LTM·Tasks 동기 값, 미처리 cascade (FR-003) | 현재 Task 는 tasks 의 항목 |
| control | `/api/v1/control`, `/api/v1/control/pause`, `/api/v1/control/resume` | 루프 상태와 일시정지/재개 (FR-005) | `.control.json` + `loop-status.json` 조합 |
| usage | `/api/v1/usage/summary`, `/api/v1/usage/timeseries` | 한도(5h/7d)·세션 비용·토큰 집계·시계열 (FR-004) | status line 스냅샷 + Claude 기록(JSONL) |
| events | `/api/v1/events` | 변경 알림 스트림 (SSE, FR-008 P1 최소) | 위 리소스의 변경 알림(topic) |
| health | `/api/v1/health` | 생존·소스 접근 가능 여부·데우기 진행률 | 런처·운영 점검용 |

## 4. 요청 규칙
### 4.1 HTTP 메서드 의미
| 메서드 | 안전(Safe) | 멱등(Idempotent) | 이 API 에서의 사용 |
|--------|-----------|------------------|-------------------|
| GET | ✅ | ✅ | 조회 전부, SSE 스트림 |
| POST | | | `control/pause`, `control/resume` — 파일 쓰기 요청. `resume` 은 루프가 없어도 200(멱등). `pause` 는 쓸 때마다 seq 가 증가하지만 결과 상태는 같음 |
| PUT / PATCH / DELETE | | | 사용하지 않음 (405 `METHOD_NOT_ALLOWED`, 아래 §5 참고) |

### 4.2 공통 규칙
- **경로 네이밍:** `/api/v1/<리소스>` 소문자 단수·복수 혼용(명세 그대로). 경로에 파일 경로를 받지 않습니다(user/02 §8).
- **필드 네이밍:** snake_case.
- **Content-Type:** 응답 `application/json`, 스트림은 `text/event-stream; charset=utf-8`. 요청 본문이 있으면 `application/json`.
- **날짜/시간:** RFC 3339 UTC (`2026-10-26T00:02:00Z`). 로컬 날짜 경계가 필요한 사용량 API 는 `tz_offset_min`(UTC 기준 동쪽 +분, -840~840, 기본 0)을 받습니다.
- **ID 형식:** Task ID 는 `T-014` 형태 문자열, Phase 는 `P1` 형태. 서버가 발급하는 ID 는 없습니다.
- **응답 봉투:** 모든 조회 성공 응답은 `{ "data": ..., "meta": { "status", "warnings", "error", "generated_at", "source_mtime" } }`.
- **`meta.status`:** `ok` / `partial`(일부 생략·경고) / `empty`(데이터 없음, 정상) / `error`(그 패널만 읽기 실패) / `warming`(사용량 캐시 준비 중). **소스 파일 문제는 HTTP 200 + `meta.status`** 로 전달하고, 한 패널의 문제가 다른 패널을 막지 않습니다.
- **응답 보안 헤더:** `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `Content-Security-Policy`.

## 5. 응답 & 상태 코드
| 코드 | 의미 | 이 API 에서 언제 |
|------|------|-----------------|
| 200 OK | 성공 | 모든 조회, `pause`/`resume` 성공. 소스 파일이 없거나 깨져도 200 (`meta.status` 참고) |
| 400 Bad Request | Host 가드 | `BAD_HOST` — 허용되지 않은 `Host` 헤더 |
| 403 Forbidden | 쓰기 가드 | `FORBIDDEN_ORIGIN` — 변경 요청의 Origin 불일치 또는 Content-Type 이 `application/json` 아님. SSE 경로는 `Origin`/`Sec-Fetch-Site` 불일치 |
| 404 Not Found | 없는 경로 | `NOT_FOUND` |
| 405 Method Not Allowed | 허용하지 않는 메서드 | `METHOD_NOT_ALLOWED` — `Allow` 헤더 포함 (OPTIONS·HEAD 포함) |
| 409 Conflict | 상태 충돌 | `NO_ACTIVE_LOOP` — 활성 루프가 없을 때 `pause` |
| 422 Unprocessable Entity | 입력 검증 실패 | `VALIDATION_ERROR` — 쿼리(`status`, `range` 등) 또는 본문(`max_pause_sec` 범위) |
| 500 | 서버 오류 | `CONTROL_WRITE_FAILED`(쓰기 실패), `INTERNAL_ERROR` |
| 503 | 동시 스트림 상한 | `TOO_MANY_STREAMS` — SSE 동시 연결 8개 초과 |

비고(명세와 실동작 차이, 실서버 확인): 변경 메서드(PUT/DELETE 등)를 `Content-Type: application/json` 없이 보내면 쓰기 가드가 먼저 걸려 405 가 아니라 **403 `FORBIDDEN_ORIGIN`** 이 옵니다(`DELETE /api/v1/health` 로 확인). JSON Content-Type 을 붙이면 405 입니다(`PUT`). ADR-011 §5 의 의도된 순서이지만 레퍼런스의 405 설명에는 이 조건이 적혀 있지 않습니다 — 아래 §12 불일치 목록 참고.

## 6. 에러 처리
에러 응답 포맷 (user/02 §6 과 명세 `ErrorResponse` 일치):
```json
{"error": {"code": "NO_ACTIVE_LOOP", "message": "활성 루프가 없습니다."}}
```
에러 코드는 닫힌 집합 9개이며, 아래가 전부입니다(명세 `ErrorCode` enum 과 일치).

| 에러 코드 | HTTP | 의미 | 클라이언트 조치 |
|-----------|------|------|----------------|
| `VALIDATION_ERROR` | 422 | 쿼리 또는 본문 검증 실패 (예: `/tasks?status=foo`, `max_pause_sec` 범위 밖) | 입력을 고쳐 다시 요청 |
| `NOT_FOUND` | 404 | 없는 경로 | 경로 확인 |
| `METHOD_NOT_ALLOWED` | 405 | 허용되지 않는 메서드 | `Allow` 헤더의 메서드 사용 |
| `BAD_HOST` | 400 | `Host` 헤더가 `127.0.0.1:<포트>`/`localhost:<포트>` 가 아님 | 대시보드 주소로 접속 |
| `FORBIDDEN_ORIGIN` | 403 | 변경 요청의 Origin 불일치·Content-Type 이 JSON 아님, 또는 SSE 의 출처 불일치 | 같은 출처에서 `application/json` 으로 요청 |
| `NO_ACTIVE_LOOP` | 409 | 활성 루프(running/paused)가 없을 때 `pause` | `/aidlc-run` 으로 루프를 먼저 시작. 재시도 무의미 |
| `TOO_MANY_STREAMS` | 503 | SSE 동시 연결 8개 초과 | 5초 폴링으로 대체(화면이 자동으로 함), 다른 탭 닫기 |
| `CONTROL_WRITE_FAILED` | 500 | `.control.json` 쓰기 실패·락 대기 2초 초과·seq 상한. 기존 파일은 보존됨 | 잠시 뒤 재시도, 계속되면 파일 권한 확인 ([pause 런북](../../workspace/project/ops/runbooks/pause-not-releasing.md)) |
| `INTERNAL_ERROR` | 500 | 예상 못 한 서버 오류 | 콘솔 로그 확인 ([server 런북](../../workspace/project/ops/runbooks/server-wont-start.md)) |

별개로 패널 응답의 `meta.error.code` 는 **HTTP 에러가 아닌 소스 문제 코드**입니다: `SOURCE_MISSING`, `SOURCE_PARSE_ERROR`, `SOURCE_UNREADABLE`, `GATE_TIMEOUT`, `PROJECT_DIR_NOT_FOUND`, `SNAPSHOT_STALE`. 이 경우 HTTP 는 200 입니다.

## 7. 페이지네이션 · 필터 · 정렬
- 페이지네이션: **없음** (목록은 tasks.md 원문 순서로 전체를 한 번에 돌려줍니다).
- 필터 (`GET /api/v1/tasks`, AND 결합):
  - `team` — 팀 id (예: `qa`), 패턴 `^[a-z][a-z0-9-]{1,30}$`. 없는 팀이면 빈 목록 + 200.
  - `status` — `open` / `done` / `blocked` / `active`. 그 밖 값은 422.
  - `phase` — `P1` 형태, 패턴 `^P\d{1,4}$`.
- 사용량: `GET /api/v1/usage/timeseries` — `range`(`5h`/`24h`/`7d`/`30d`, 기본 `24h`), `bucket`(`hour`/`day`, 생략 시 `30d` 는 `day`, 나머지는 `hour`), `group`(`model`/`sidechain`/`none`, 기본 `model`), `tz_offset_min`. `GET /api/v1/usage/summary` — `tz_offset_min`.
- 정렬 파라미터: 없음.

## 8. 멱등성 & 재시도
- 멱등 키 헤더: 지원하지 않음.
- `POST /control/resume` 은 멱등입니다(루프가 없어도 200). `POST /control/pause` 를 반복하면 200 이고 상태는 같지만 내부 seq 는 매번 증가합니다(계약상 허용).
- 재시도: 4xx 는 재시도하지 않습니다. 500 `CONTROL_WRITE_FAILED` 는 잠시 뒤 재시도해도 됩니다(파일은 원자적 교체라 손상되지 않음). 503 `TOO_MANY_STREAMS` 는 스트림 대신 폴링을 쓰세요.

## 9. 요청 한도 (Rate Limit)
- 없음 (127.0.0.1 단일 사용자). 단, SSE 동시 연결은 8개로 제한됩니다.

## 10. 버저닝 & 폐기(Deprecation) 정책
- 버전 방식: URL 경로 `/api/v1`. 앱·명세 버전은 `0.1.0` (`GET /health` 의 `data.version` 과 명세 `info.version`).
- 하위 호환 변경: 응답에 새 필드 추가, 새 SSE topic·event 추가(클라이언트는 모르는 topic·event 를 무시해야 함). 깨지는 변경(이름 변경·삭제·의미 변경)은 architecture 리뷰와 계약 문서 갱신이 필요합니다.
- 폐기 예정 엔드포인트: 없음 (reference.md 에 deprecated 표시 없음).
- P2 에서 추가 예정이지만 **아직 없는** 경로: `/api/v1/teams`, `/api/v1/timeline`, `/api/v1/alerts`, `/api/v1/usage/cost` — 호출하면 404 `NOT_FOUND`.

## 11. 이벤트 / 스트리밍 (SSE)
`GET /api/v1/events` 는 변경 **알림만** 보냅니다. 데이터는 받은 topic 에 해당하는 REST 엔드포인트를 다시 조회해서 얻습니다.

| event | 의미 |
|-------|------|
| `changed` | `{"topics": [...], "at": "<RFC3339 UTC>"}` — 해당 topic 의 패널만 재조회 |
| `warming` | 사용량 캐시 준비 진행률 `{"progress": 0.0~1.0, "at": ...}` |
| `ready` | 사용량 캐시 준비 완료 `{"at": ...}` |
| (주석) `: keep-alive` | 이벤트가 없으면 15초마다. 45초 동안 프레임이 없으면 재연결 |

- 이 버전(M1)이 발행하는 topic: `memory`, `tasks`, `control`, `usage`. (`plan`, `pipeline` 등은 M2 계약에 있으나 M1 서버는 발행하지 않아도 됩니다. 클라이언트는 모르는 topic 을 무시하세요.)
- 연결 첫 프레임은 `retry: 5000`, 이어서 `warming` 또는 `ready`. `id:` 는 쓰지 않고 `Last-Event-ID` 는 무시합니다(재전송 없음 — 재연결 후 모든 패널을 한 번 다시 조회).
- 동시 연결 상한 8. 초과 시 스트림 대신 503 `TOO_MANY_STREAMS` JSON. 허용 메서드는 GET 하나.
- 페이로드에 파일 경로·파일 내용을 담지 않습니다.
- 실서버 확인: 연결 직후 `retry: 5000` 다음 `event: ready` / `data: {"at":"..."}` 프레임이 왔습니다.
- 이벤트 형식의 기준 문서: `workspace/project/contracts/sse-events.md`.
- 웹훅: 없음.

## 12. 명세·표준 대조 결과
| 항목 | 결과 |
|------|------|
| 엔드포인트 11개·메서드·상태 코드 (명세 ↔ reference.md ↔ 이 문서) | 일치 |
| 에러 코드 9개 (명세 `ErrorCode` ↔ 이 문서 §6) | 일치 |
| 에러 포맷 `{"error":{"code","message"}}` (user/02 §6) | 일치 (실서버에서 422·409·400·403·404·405 확인) |
| 변경 메서드 + 비-JSON Content-Type 의 GET 전용 경로 → 403 (명세는 405 만 기재) | **불일치(경미)** — ADR-011 §5 의도와는 일치, 레퍼런스 설명에 조건 없음. `[architecture]` 확인 후보 |
| 인증 (user/02 §6 "없음") ↔ 명세 `securitySchemes` 없음 | 일치 |

## 13. 변경 이력
| 버전 | 날짜 | 변경 | 호환성 |
|------|------|------|--------|
| 0.1.0 | 2026-10-26 | 최초 문서화 (P1 / M1) | - |
