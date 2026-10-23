---
doc: team-charter
layer: team
team: backend
group: engineering
tier: conditional
status: draft
---
# Backend 팀 Charter

> 팀 Agent(`.claude/agents/team-backend.md`)가 작업 전 항상 읽는 문서입니다. `aidlc/teams/catalog.json` 기본값으로 생성되며,
> team-architect 가 프로젝트 분석서 근거로 구체화합니다 ("프로젝트 적용" 칸).
> 상위 문서와 충돌하면 user/02(개발 표준) > user/03(아키텍처 철학) > 이 문서 순으로 따릅니다.

## 1. 미션
도메인 로직과 API 를 개발 표준과 계약에 맞게 구현하고 테스트한다.

- 생성 근거: 서버 측 API 또는 도메인 로직 컴포넌트가 있을 때 (대부분의 프로젝트)
- 프로젝트 적용: 20 §4 컴포넌트 표에서 API 앱 셸·AI-DLC 상태 리더·사용량 수집기·상태 스냅샷 리더·status line 스크립트·변경 감지 & SSE 허브·루프 제어 서비스·API·루프 제어 CLI 의 소유 팀이 backend, 20 §5 엔드포인트 15개 → create_when "서버 측 API" 충족. 40 §2 에서 integration(Claude Code 연동)·data(수집·정제·집계)·dba(메모리 캐시 구조) 책임을 인수 (40 §1)

## 2. 책임 범위
**소유 (Owns)**
- 서버 애플리케이션 코드 (예: src/api, src/domain)
- API 구현 및 단위·통합 테스트
- DB 접근 계층 코드 — 이 프로젝트는 DB 없음(03 §4). 대신 프로세스 메모리 캐시 구조(`services/usage/` 커서·버킷)
- (integration·data 인수) Claude Code JSONL·status line 연동, 사용량 수집·정제·집계
- `aidlc/scripts/loop_control.py`, `aidlc/hooks/statusline.{sh,py}`
- `workspace/project/contracts/openapi.json` 갱신(export 스크립트로만) + `docs/api/` 재생성

**하지 않음 (Not owns)**
- DB 스키마 운영 변경 실행 (dba)
- 인프라 리소스 (infra)
- 계약 정의 자체 (architecture)

- 프로젝트 적용 (실제 디렉토리/컴포넌트):
  - `monitor/backend/app/**` — `main.py`, `config.py`, `api/`(health 제외), `services/`(aidlc_reader, pipeline, tasks, gates, teams, timeline, statusline_reader, control, watcher, usage/), `models/`(health 제외)
  - `monitor/backend/scripts/export_openapi.py`
  - `monitor/backend/tests/unit/`, `monitor/backend/tests/api/`
  - `aidlc/scripts/loop_control.py` + `aidlc/scripts/aidlc.py` 의 `loop-*` 서브커맨드 등록 블록만
  - `aidlc/hooks/statusline.sh`, `aidlc/hooks/statusline.py`, `.claude/settings.json` 의 `statusLine` 키만
  - `workspace/project/contracts/openapi.json`(손편집 금지, export 로만), `docs/api/`(`openapi_docs.py` 재생성으로만)
  - **하지 않음:** `app/logging_config.py`, `app/api/health.py`, `app/models/health.py`(ops), `tests/conftest.py`·`fixtures/`·`scenarios/`·`perf/`(qa), `tests/ops/`(ops), `requirements*.txt`·`pyproject.toml`(cicd), `memory_cascade.py`·그 밖의 `aidlc.py`(무소유, 수정 금지)

## 3. 산출물
- API 구현 + OpenAPI 동기화
- 단위/통합 테스트
- 마이그레이션 스크립트 (실행은 승인 후)

## 4. 입력 문서
- workspace/project/contracts/
- workspace/project/stories/
- workspace/user/02-development-standards.md

## 5. 담당 요구사항
| FR/NFR | 내용 | Phase |
|--------|------|-------|
| FR-001 | `/api/v1/pipeline`: 단계 0~6 + Gate 3종(`aidlc.py check` 서브프로세스, TTL 5 s, timeout 10 s) | P1 |
| FR-002 | `/api/v1/plan`, `/api/v1/tasks`(team/status/phase 필터) | P1 |
| FR-003 | `/api/v1/memory`: Hook 읽기 함수 재사용(ADR-009), `status` 서브프로세스 금지 | P1 |
| FR-004 | 사용량 수집기(증분·허용 필드·requestId 중복 제거·버킷·데우기), 스냅샷 리더, status line 스크립트, `/api/v1/usage/*` | P1 |
| FR-005 | `.control.json` 쓰기 API, `loop-status.json` 조합 상태 판정, 루프 제어 CLI(540 s/호출, 30 s heartbeat, 7200 s 상한) | P1 |
| FR-008 | 1초 stat 폴링 + SSE 허브(M1: memory·control·usage·tasks topic) | P1 / P2(전 topic) |
| CON-01·02·03 | 127.0.0.1, Host/Origin 가드, 읽기 전용(쓰기 1파일) | P1 |
| FR-006 | `/api/v1/timeline`(STM 로그 + 추론 이벤트, ADR-010) | P2 |
| FR-007 | `/api/v1/teams`(팀별 할당/완료, 리뷰 PASS/FAIL) | P2 |
| FR-009 | `/api/v1/usage/cost` (`monitor/pricing.json` 있을 때만) | P2 |
| FR-010 | `/api/v1/alerts` 조건 3종 | P2 |

## 6. 협업 인터페이스
- frontend/mobile: API 계약
- data: 이벤트/로그 스키마
- dba: 쿼리·인덱스 검토
- qa: 테스트 데이터

| 방향 | 상대 팀 | 계약 | 위치 |
|------|---------|------|------|
| 제공 | frontend | REST + 봉투 + 에러 포맷 | `workspace/project/contracts/openapi.json`, `docs/api/reference.md` |
| 제공 | frontend | SSE 이벤트 | `workspace/project/contracts/sse-events.md` |
| 제공 | architecture(SKILL.md) | `aidlc.py loop-*` exit code 0/2/10/20 | `workspace/project/contracts/loop-cli.md` |
| 제공 | ops | `source_status()`, `warmup.progress()` | `workspace/project/contracts/README.md` |
| 사용 | ops | `setup_logging()`, 로그 문구 규칙 | `monitor/backend/app/logging_config.py` |
| 사용 | architecture | 파일 계약 스키마 3종 | `workspace/project/contracts/*.schema.json` |
| 사용 | security | 허용 필드 체크리스트 | `workspace/project/security/privacy.md` |
| 사용 | qa | fixture 생성기 | `monitor/backend/tests/fixtures/` |

## 7. 팀 Definition of Done
- [ ] user/02 §10 공통 DoD
- [ ] 계약(OpenAPI)과 구현 일치
- [ ] user/02 커버리지 기준 충족
- [ ] 에러 응답 포맷 준수
- [ ] 로그에 개인정보 없음

## 8. 품질 지표
- API p95 지연
- 테스트 커버리지
- 5xx 비율

## 9. 리뷰 게이트 (다른 팀 Task 검증)
- 없음 (리뷰 게이트를 운영하지 않는 팀)

## 10. 팀 표준 (user/02 구체화)
- 언어/프레임워크: Python 3.11+, FastAPI 0.161.1, uvicorn 0.54.0(기본, `[standard]` 아님), Pydantic 2.14.1. 그 밖은 표준 라이브러리만(ADR-006). 계층 api → services → models 단방향
- 디렉토리: 위 "프로젝트 적용" 목록
- 테스트 명령: `cd monitor/backend && python -m pytest` (커버리지 `--cov=app`, 라인 ≥ 70%), `ruff format --check . && ruff check .`. API 변경 시 `python monitor/backend/scripts/export_openapi.py` → `python3 aidlc/scripts/openapi_docs.py` 로 `docs/api/` 재생성(같은 Task)
- 규칙: 요청에서 파일 경로를 받지 않는다(02 §8). 소스 문제는 HTTP 200 + `meta.status`(NFR-002). 경로는 `AIDLC_ROOT`·`CLAUDE_HOME` 설정으로 주입
