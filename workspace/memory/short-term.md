---
status: active
task: T-013
team: qa
outcome: none
opened_at: 2026-10-25T00:00:00+00:00
---
# Short-term Memory

> **계층 4 (작업 단위).** Task 1개를 수행하는 동안의 작업 메모리. 한 번에 하나만 열린다.
> 수명: `status: active` 로 열고 → 작업 → `outcome` 기록 → `status: closed` 로 닫는다.
> 닫히는 순간 Hook 이 이 파일을 `archive/STM-xxxx_<task>.md` 로 옮기고 Long-term memory 갱신(cascade 1/3)을 요구한다.
> frontmatter 값: status(idle|active|closed) / outcome(done|partial|blocked)

## 1. 목표
- Task: T-013 [qa] 핵심 통합·성능 테스트(빠른 진행 모드로 축소, D-51): 500 0건, 응답·로그 본문 0건, 일시정지/재개 E2E(실서버), Task 100 + 30일 JSONL 첫 응답 ≤ 2초(`tests/perf`, marker `perf`) — NFR-001~003, FR-005 | deps: T-012
- 완료 조건(DoD): check.py 게이트 PASS, perf 측정값 STM 기록 + user/02 §10 공통 DoD. 원래 DoD 의 나머지(추적표·home_guard 빈틈 I-19·AC-22 시나리오 I-36·I-32 시나리오·test-cases 문서)는 Backlog T-032

## 2. 로드한 컨텍스트
- 관련: NFR-001(첫 응답 ≤ 2초, Task 100 + 30일 JSONL), NFR-002(깨진 입력 500 0건), NFR-003(본문 0건), FR-005(일시정지/재개 E2E), CON-03(해시 불변)
- 계획 문서: workspace/project/qa/test-strategy.md §4 시나리오 S-01~S-13(위치 tests/scenarios·tests/perf), §5 perf 크기(329~658 MB 는 선형 추정 → 실측으로 I-11 보정), pytest marker `perf` 등록
- 빠른 진행 모드(D-51, 사용자 합의 2026-10-24): 다중 리뷰 Agent 대신 로컬 게이트 `monitor/tools/check.py` 전체 PASS + 실서버 E2E 로 대신. 막지 않는 지적은 Backlog
- 환경: `monitor/.venv` 재생성·`npm ci` 완료. 시작 시점 게이트 12개 전부 PASS(pytest backend 75 s)
- 이미 있는 것: tests/{unit,api,ops,scenarios,fixtures}, home_guard, 실제 서버 기동은 run.py/uvicorn 으로 127.0.0.1 임시 포트
- 규칙: 실제 ~/.claude 금지(CLAUDE_HOME 주입), 결함은 고치지 말고 STM §5 [팀] 후보로

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
