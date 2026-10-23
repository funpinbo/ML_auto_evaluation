---
status: active
task: T-025
team: architecture
outcome: none
opened_at: 2026-10-23T13:52:10+00:00
---
# Short-term Memory

> **계층 4 (작업 단위).** Task 1개를 수행하는 동안의 작업 메모리. 한 번에 하나만 열린다.
> 수명: `status: active` 로 열고 → 작업 → `outcome` 기록 → `status: closed` 로 닫는다.
> 닫히는 순간 Hook 이 이 파일을 `archive/STM-xxxx_<task>.md` 로 옮기고 Long-term memory 갱신(cascade 1/3)을 요구한다.
> frontmatter 값: status(idle|active|closed) / outcome(done|partial|blocked)

## 1. 목표
- Task: T-025 [architecture] ADR-011 §9 보강: 405(OPTIONS 포함)·Starlette 기본 HTTPException 매핑 규칙(기존 코드로 매핑 또는 `METHOD_NOT_ALLOWED` 추가 결정), 기본 `{"detail":...}` 본문 금지, HostGuard 의 websocket scope 거부·lifespan 통과, SSE GET 에 Origin 검사 적용 여부 결정(교차 출처 EventSource 슬롯 소모 가용성 위험), §4 에 Host 헤더 정확히 1개 규칙·선행 0·userinfo·추가 세그먼트 거부 명시, §5 에 미디어 타입 대소문자 무시 정확 일치·422 보다 먼저 403 명시(D-25, privacy.md §5.1·§5.2 와 정합) — I-14 | deps: T-021
- 완료 조건(DoD): ADR-011·20 §5·sse-events.md 정합, 결정 근거 기록 (출처: STM-0005 §5) + user/02 §10 공통 DoD

## 2. 로드한 컨텍스트
- 관련: LTM I-14(405·HTTPException 매핑, websocket/lifespan scope, SSE Origin), D-18~D-20, D-25(privacy.md §5.1·§5.2 케이스 단일 정의), D-12(SSE 연결 상한 503)
- 근거: workspace/project/adr/ADR-011, 20-architecture-analysis.md §5, contracts/sse-events.md, security/privacy.md §5, STM-0005·STM-0008 §5 의 [architecture] 후보

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
