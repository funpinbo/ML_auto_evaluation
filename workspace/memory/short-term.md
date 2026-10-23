---
status: active
task: T-026
team: architecture
outcome: none
opened_at: 2026-10-23T18:49:49+00:00
---
# Short-term Memory

> **계층 4 (작업 단위).** Task 1개를 수행하는 동안의 작업 메모리. 한 번에 하나만 열린다.
> 수명: `status: active` 로 열고 → 작업 → `outcome` 기록 → `status: closed` 로 닫는다.
> 닫히는 순간 Hook 이 이 파일을 `archive/STM-xxxx_<task>.md` 로 옮기고 Long-term memory 갱신(cascade 1/3)을 요구한다.
> frontmatter 값: status(idle|active|closed) / outcome(done|partial|blocked)

## 1. 목표
- Task: T-026 [architecture] loop-cli §7 / control.schema `seq` 보강: 루프 도중 `.control.json` 이 깨지거나 삭제된 경우 대시보드가 다음 seq 를 `max(이전 seq(없으면 0), loop-status.baseline_seq) + 1` 로 쓰는지 결정·명시(또는 FR-005 AC-18 복구 경로로 대체) — I-16, FR-005 | deps: T-004
- 완료 조건(DoD): loop-cli.md·control.schema·ADR-004 정합, FR-005 AC 와 모순 없음 (출처: STM-0006 §5) + user/02 §10 공통 DoD

## 2. 로드한 컨텍스트
- 관련: LTM I-16(루프 도중 .control.json 깨짐/삭제 → seq 1 ≤ baseline_seq → CLI 가 새 pause/resume 무시), D-04(파일당 쓰기 주체 1개), D-09·D-10(exit code, episode 상한), stories/FR-005.md(AC-18 복구 경로)
- 근거: workspace/project/contracts/loop-cli.md §7, control.schema.json `seq`, loop-status.schema.json `baseline_seq`, ADR-004

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
