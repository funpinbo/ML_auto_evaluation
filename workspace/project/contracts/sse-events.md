---
doc: contract
contract: sse-events
schema_version: 1
owner: architecture
implementer: backend (services/watcher.py, api/events.py)
consumers: frontend (composables/useEventStream.ts)
sources: [20 §5 F2, 20 §4 변경 감지 & SSE 허브, ADR-008, ADR-010, ADR-011, FR-008, QS-02, 00 C1]
---
# SSE 이벤트 계약 (`GET /api/v1/events`)

> 서버 → 브라우저 단방향 알림. **알림만 보내고 데이터는 보내지 않는다** — 프론트는 topic 에 해당하는 REST 엔드포인트를 다시 조회한다(서버 무상태, 03 §3).
> 표준 `text/event-stream` (FastAPI `StreamingResponse`, 추가 의존성 없음 — 원칙 3).

## 1. 연결
- `GET /api/v1/events` — 쿼리·본문 없음. ADR-011 Host 가드 적용(다른 Host → 400 `BAD_HOST`).
- 응답 헤더: `Content-Type: text/event-stream; charset=utf-8`, `Cache-Control: no-cache`, `X-Accel-Buffering: no` + ADR-011 보안 헤더.
- 동시 연결 상한 **8**. 초과 시 스트림을 열지 않고 HTTP **503** `{"error":{"code":"TOO_MANY_STREAMS","message":"..."}}` → 프론트는 5초 폴링 폴백.
- `id:` 필드는 쓰지 않는다(재전송·재생 없음). `Last-Event-ID` 는 무시한다. 재연결 직후 프론트는 모든 패널을 한 번 다시 조회한다.
- 연결 직후 첫 프레임: `retry: 5000` 후 현재 데우기 상태(`warming` 또는 `ready`) 1개.

## 2. 이벤트
| event | data (JSON 한 줄) | 의미 / 프론트 동작 |
|-------|-------------------|-------------------|
| `changed` | `{"topics": ["memory","tasks"], "at": "<RFC3339 UTC>"}` | topic 목록의 패널만 재조회. `topics` 는 중복 없음, 비어 있지 않음, 아래 enum 만, 정렬 무관 |
| `warming` | `{"progress": 0.0~1.0, "at": "<RFC3339 UTC>"}` | 사용량 캐시 데우는 중. 진행률이 바뀔 때 최대 1초 1회 |
| `ready` | `{"at": "<RFC3339 UTC>"}` | 데우기 완료(연결 시 이미 완료면 즉시). 프론트는 `usage` topic 패널 재조회 |
| (주석) | `: keep-alive` | **15초**마다 이벤트가 없을 때 전송. 프론트는 무시. 45초 동안 아무 프레임도 없으면 연결을 끊고 재연결 |

- 프레임 형식: `event: <name>\ndata: <json>\n\n`. `data` 는 항상 한 줄 JSON 객체.
- 한 폴링 tick(1초, ADR-008)에서 감지한 변경은 **`changed` 1개로 합친다**(topic 합집합).
- 페이로드에 파일 경로·파일 내용·ID 를 넣지 않는다(ADR-011 §8).

## 3. Topic 목록과 감시 대상
| topic | 다시 조회할 API | 변경 원천 (stat 감시) | 마일스톤 |
|-------|-----------------|------------------------|----------|
| `memory` | `/api/v1/memory` | `workspace/memory/short-term.md`, `long-term.md`, `archive/` 디렉터리, `.cascade-state.json` | **M1** |
| `tasks` | `/api/v1/tasks` | `workspace/memory/tasks.md` | **M1** |
| `control` | `/api/v1/control` | `workspace/memory/.control.json`, `workspace/memory/.monitor/loop-status.json` (+ paused 상태의 heartbeat 120 s 경계 통과 시 서버가 직접 발행) | **M1** |
| `usage` | `/api/v1/usage/summary`, `/usage/timeseries` | `workspace/memory/.monitor/claude-status.json`, 해석된 `~/.claude/projects/<enc>/**/*.jsonl` (+ `captured_at` 10분 경계 통과 시) | **M1** |
| `plan` | `/api/v1/plan` | `workspace/memory/plan.md`, `tasks.md` | M2 |
| `pipeline` | `/api/v1/pipeline` | `workspace/user/`, `workspace/project/`, `workspace/teams/`, `workspace/memory/plan.md`·`tasks.md` | M2 |
| `teams` | `/api/v1/teams` | `workspace/teams/*/charter.md`, `workspace/project/40-team-composition.md`, `short-term.md`, `archive/` | M2 |
| `timeline` | `/api/v1/timeline` | `short-term.md`, `archive/`, `long-term.md`, `tasks.md`, `plan.md` (ADR-010) | M2 |
| `alerts` | `/api/v1/alerts` | `memory`·`tasks`·`usage` 가 발행될 때 함께 발행(파생) | M2 |

- M1 서버는 M1 topic 4개만 발행해도 계약 위반이 아니다. 프론트는 **모르는 topic 을 무시**해야 한다(topic 추가 = 하위 호환 변경).
- 하나의 파일이 여러 topic 에 걸리면 해당 topic 을 모두 발행한다.
- 시각 경계 이벤트(heartbeat 만료, 스냅샷 오래됨)는 파일이 바뀌지 않아도 화면 판정이 바뀌므로 서버가 `changed` 로 알린다.

## 4. 호환성 규칙
- 하위 호환: 새 topic, 새 event 이름(프론트는 모르는 이벤트 무시), data 에 새 키 추가.
- 깨지는 변경: topic 이름 변경·삭제, 기존 data 키 의미 변경, keep-alive 주기 30초 초과로 늘림 → architecture 리뷰 + 이 문서 `schema_version` 증가.
- OpenAPI(`openapi.json`)에는 `/api/v1/events` 를 `text/event-stream` 응답으로만 기재한다. 이벤트 형식의 기준은 이 문서다.
