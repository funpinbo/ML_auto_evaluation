---
rev: 0
synced_ltm_rev: 0
---
# Tasks

> **계층 2.** Plan 의 Phase 를 실행 가능한 Task 로 분해한다.
> 갱신 시점: (1) `/aidlc-plan` 최초 생성 (2) Hook cascade 2/3 — LTM rev 가 증가했을 때.
> **규칙:** 이 파일은 cascade 2/3 단계(또는 /aidlc-plan)에서만 수정한다. 작업 중 결과는 STM 에 기록한다.
>
> 형식: `- [ ] T-001 [team] 제목 — FR-001 | deps: T-000 | DoD: 완료 조건`
> Phase 섹션 제목은 반드시 `## P<숫자> ...` 로 시작해야 Hook 이 완료 여부를 판정한다.

## P1 — (Phase 이름)
- [ ] T-001 [backend] 예시 Task — FR-001 | deps: - | DoD: 단위 테스트 통과

## Backlog (Phase 미배정)
- (새로 발견했지만 아직 Phase 에 넣지 않은 Task)

## Blocked
- (T-ID — blocker 설명 — 해소 조건)
