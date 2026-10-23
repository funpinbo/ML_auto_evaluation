---
status: active
task: T-005
team: backend
outcome: none
opened_at: 2026-10-23T17:38:08+00:00
---
# Short-term Memory

> **계층 4 (작업 단위).** Task 1개를 수행하는 동안의 작업 메모리. 한 번에 하나만 열린다.
> 수명: `status: active` 로 열고 → 작업 → `outcome` 기록 → `status: closed` 로 닫는다.
> 닫히는 순간 Hook 이 이 파일을 `archive/STM-xxxx_<task>.md` 로 옮기고 Long-term memory 갱신(cascade 1/3)을 요구한다.
> frontmatter 값: status(idle|active|closed) / outcome(done|partial|blocked)

## 1. 목표
- Task: T-005 [backend] API 앱 셸(앱 팩토리, 응답 envelope, 에러 포맷, Host/Origin 가드, dist 마운트, 설정 주입) + AI-DLC 상태 리더(읽기 전용) + GET /pipeline /plan /tasks /memory — FR-001, FR-002, FR-003 | deps: T-001, T-003, T-020, T-021, T-023, T-024, T-025
- 완료 조건(DoD): Host 가드는 자체 ASGI `HostGuardMiddleware`(D-18), `settings.port` 단일 출처(D-19), 비-JSON 403, 에러 코드 닫힌 집합(D-20) + privacy.md §5.1 H-01~H-22·§5.2 C-01~C-11 전 케이스 테스트(H-18 은 ASGI scope 직접 구성), ADR-011 §9~§12 테스트(에러 코드 9개 enum, `{"detail"}` 금지, 405+Allow·OPTIONS, `/api` 밖 404, websocket close 1008, 처리 순서 D-29), OpenAPI export(`workspace/project/contracts/openapi.json`) + `docs/api` 재생성, TestClient base_url 지정, 단위·API 테스트 통과, 조회 전후 workspace 해시 불변, `status` 서브프로세스 미사용 + user/02 §10 공통 DoD

## 2. 로드한 컨텍스트
- 관련 FR: FR-001(단계 판정 D-21), FR-002(Plan·Task), FR-003(메모리), 스토리 workspace/project/stories/FR-001~003.md
- ADR: ADR-001(단일 프로세스), ADR-006(의존성 fastapi 0.161.1·uvicorn 0.54.0·pydantic 2.14.1), ADR-009(memory_cascade 읽기 함수만, `status` 서브프로세스 금지), ADR-011 §2·§4·§5·§9~§12
- 보안 케이스: workspace/project/security/privacy.md §5.1 H-01~H-22, §5.2 C-01~C-11
- LTM: D-07, D-08, D-16, D-18, D-19, D-24~D-29, 패턴(TestClient base_url, Host 헤더 1개, Starlette 405 가로채기), I-21
- 테스트: qa fixture(monitor/backend/tests/fixtures/, conftest), 소유 경로 tests/{unit,api}/ (40 §1.1)

## 3. 작업 로그
<!-- 시간순으로 짧게. 무엇을 했고 무엇을 봤는지 -->

## 4. 발견 사항 (LTM 후보)
- 결정:
- 패턴:
- 이슈/리스크:
- 교훈:

## 5. 새로 발견된 Task (Task 후보)
- 

## 6. 결과 & 인수인계
- 산출물(파일/PR):
- 검증 결과:
- 남은 일:

## 7. 리뷰 기록 (리뷰 게이트)
<!-- /aidlc-run 이 리뷰 게이트 대상 팀을 리뷰 모드로 호출하면 각 팀이 한 줄씩 추가 -->
| 팀 | 결과 | 근거 | 필요한 조치 |
|----|------|------|-------------|
