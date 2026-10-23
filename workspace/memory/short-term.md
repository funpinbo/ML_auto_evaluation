---
status: active
task: T-001
team: architecture
outcome: none
opened_at: 2026-10-23T07:36:23+00:00
---
# Short-term Memory

> **계층 4 (작업 단위).** Task 1개를 수행하는 동안의 작업 메모리. 한 번에 하나만 열린다.
> 수명: `status: active` 로 열고 → 작업 → `outcome` 기록 → `status: closed` 로 닫는다.
> 닫히는 순간 Hook 이 이 파일을 `archive/STM-xxxx_<task>.md` 로 옮기고 Long-term memory 갱신(cascade 1/3)을 요구한다.
> frontmatter 값: status(idle|active|closed) / outcome(done|partial|blocked)

## 1. 목표
- Task: T-001 [architecture] 파일 계약 3종(.control.json, loop-status.json, claude-status.json JSON Schema) + loop-cli.md(서브커맨드·exit code) + sse-events.md + contracts/README — FR-004, FR-005, FR-008 | deps: -
- 완료 조건(DoD): workspace/project/contracts/ 에 스키마·문서 존재, ADR-003·004·011 과 일치 + user/02 §10 공통 DoD

## 2. 로드한 컨텍스트
- 관련 FR: FR-004(사용량·스냅샷), FR-005(루프 제어), FR-008(SSE) — 00-interpretation.md §2
- 근거 문서: workspace/project/20-architecture-analysis.md §5, adr/ADR-003·004·010·011
- 팀 charter: workspace/teams/architecture/charter.md (contracts/ 소유, openapi.json 은 backend 가 export)
- LTM: D-03(스냅샷 경로), D-04(파일당 쓰기 주체 1개, exit 0/10/20/2), D-08(envelope·에러 포맷)

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
