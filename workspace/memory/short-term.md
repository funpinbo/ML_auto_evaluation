---
status: active
task: T-020
team: cicd
outcome: none
opened_at: 2026-10-23T07:45:49+00:00
---
# Short-term Memory

> **계층 4 (작업 단위).** Task 1개를 수행하는 동안의 작업 메모리. 한 번에 하나만 열린다.
> 수명: `status: active` 로 열고 → 작업 → `outcome` 기록 → `status: closed` 로 닫는다.
> 닫히는 순간 Hook 이 이 파일을 `archive/STM-xxxx_<task>.md` 로 옮기고 Long-term memory 갱신(cascade 1/3)을 요구한다.
> frontmatter 값: status(idle|active|closed) / outcome(done|partial|blocked)

## 1. 목표
- Task: T-020 [cicd] `.gitignore` 에 런타임 파일 등록(`workspace/memory/.control.json`, `workspace/memory/.monitor/`) — I-01 | deps: T-001
- 완료 조건(DoD): `git check-ignore` 로 두 경로 무시 확인 (출처: STM-0001 §5) + user/02 §10 공통 DoD

## 2. 로드한 컨텍스트
- 관련: I-01 (LTM §3), contracts/README §2 (런타임 파일 위치·쓰기 주체)
- 팀 charter: workspace/teams/cicd/charter.md (.gitignore 소유 — 기존 프레임워크 줄은 지우지 않고 Monitor 항목만 추가)
- LTM: 파일당 쓰기 주체 1개 패턴, D-03 스냅샷 경로

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
