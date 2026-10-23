---
status: active
task: T-021
team: architecture
outcome: none
opened_at: 2026-10-23T09:46:49+00:00
---
# Short-term Memory

> **계층 4 (작업 단위).** Task 1개를 수행하는 동안의 작업 메모리. 한 번에 하나만 열린다.
> 수명: `status: active` 로 열고 → 작업 → `outcome` 기록 → `status: closed` 로 닫는다.
> 닫히는 순간 Hook 이 이 파일을 `archive/STM-xxxx_<task>.md` 로 옮기고 Long-term memory 갱신(cascade 1/3)을 요구한다.
> frontmatter 값: status(idle|active|closed) / outcome(done|partial|blocked)

## 1. 목표
- Task: T-021 [architecture] ADR-011 보강: (a) §5 에 "비-JSON Content-Type 변경 요청도 403 `FORBIDDEN_ORIGIN`" 한 줄 명시(D-14), (b) §4 Host 가드가 포트를 검사할지 결정 — 검사하면 구현 방식 명시, 안 하면 privacy.md N-02 포트 케이스를 선택 항목으로 유지 — NFR-003 | deps: T-002
- 완료 조건(DoD): ADR-011 에 두 항목 반영, 20 §8 에러 코드·privacy.md N-02 와 정합, LTM I-04·I-05 해소. (c) ADR-006 Decision 2 dev 의존성 목록에 jsonschema(+전이 4종, MIT) 추가 — I-08 해소 (출처: STM-0003 §5, STM-0004 §5; T-009 도 ADR-011 을 수정하므로 같은 파일 충돌 주의) + user/02 §10 공통 DoD

## 2. 로드한 컨텍스트
- 관련: NFR-003, LTM D-14(비-JSON Content-Type → 403), D-15(Origin 없는 로컬 POST 잔여 위험), I-04(Host 가드 포트 검사 미정), I-05, I-08(ADR-006 jsonschema)
- 근거 문서: workspace/project/adr/ADR-011, ADR-006, workspace/project/security/privacy.md (N-02 포트 케이스), 20 §8 에러 코드
- 주의: T-009 도 ADR-011 을 수정(TOO_MANY_STREAMS, I-02) — 이번에 함께 넣을 수 있으면 넣고 STM §4 에 기록

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
