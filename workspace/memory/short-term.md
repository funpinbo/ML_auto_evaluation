---
status: active
task: T-002
team: security
outcome: none
opened_at: 2026-10-23T07:47:02+00:00
---
# Short-term Memory

> **계층 4 (작업 단위).** Task 1개를 수행하는 동안의 작업 메모리. 한 번에 하나만 열린다.
> 수명: `status: active` 로 열고 → 작업 → `outcome` 기록 → `status: closed` 로 닫는다.
> 닫히는 순간 Hook 이 이 파일을 `archive/STM-xxxx_<task>.md` 로 옮기고 Long-term memory 갱신(cascade 1/3)을 요구한다.
> frontmatter 값: status(idle|active|closed) / outcome(done|partial|blocked)

## 1. 목표
- Task: T-002 [security] threat-model.md(STRIDE) + privacy.md(허용 필드 화이트리스트, `~/.claude` 접근 범위, Host/Origin 정책) — NFR-003, Q2 | deps: -
- 완료 조건(DoD): workspace/teams/security/ 에 문서, 이후 리뷰 체크리스트로 사용 가능 + user/02 §10 공통 DoD

## 2. 로드한 컨텍스트
- 관련: NFR-003, 00 Q2(본문 비접근 규칙), C2, ADR-002·003·011, contracts/README §2·§3
- 팀 charter: workspace/teams/security/charter.md
- LTM: D-02(허용 필드), D-08(Host/Origin), D-13(transcript_dir_name 재검증·노출 금지), security 팀 지식(경로 필드 3종 요구, symlink 재확인)

## 3. 작업 로그
<!-- 시간순으로 짧게. 무엇을 했고 무엇을 봤는지 -->
- 2026-10-23 07:50 UTC — **세션 일시 중단(사용자 요청).** team-security 작업 도중 오케스트레이터가 중지함. 산출물 없음(threat-model.md, privacy.md 미작성).
  재개 방법: STM 을 그대로 두고(`status: active` 유지) `/aidlc-run` 실행 → 0단계에서 이 STM 을 이어받아 3단계(team-security 작업 모드 재위임)부터 진행. 요구 산출물은 tasks.md T-002 와 STM §1 참고.

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
