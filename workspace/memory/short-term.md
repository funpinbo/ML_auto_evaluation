---
status: active
task: T-024
team: security
outcome: none
opened_at: 2026-10-23T13:49:09+00:00
---
# Short-term Memory

> **계층 4 (작업 단위).** Task 1개를 수행하는 동안의 작업 메모리. 한 번에 하나만 열린다.
> 수명: `status: active` 로 열고 → 작업 → `outcome` 기록 → `status: closed` 로 닫는다.
> 닫히는 순간 Hook 이 이 파일을 `archive/STM-xxxx_<task>.md` 로 옮기고 Long-term memory 갱신(cascade 1/3)을 요구한다.
> frontmatter 값: status(idle|active|closed) / outcome(done|partial|blocked)

## 1. 목표
- Task: T-024 [security] privacy.md N-02·N-04 를 ADR-011 §4·§5 에 맞춤: 포트 불일치·포트 생략·`[::1]`·`localhost.`·선행 0(`127.0.0.1:08765`)·userinfo(`user@...`)·`127.0.0.1:<port>:x` 거부를 필수로, 대문자 `LOCALHOST:<port>` 통과, Host 헤더가 정확히 1개가 아니면 400 `BAD_HOST`, Content-Type 접두 함정(`application/jsonx`, `application/json-patch+json`) 거부, TrustedHostMiddleware 문구 삭제, 정적 dist·SSE 포함, §5 참고 문단 "20 §8"→"20 §5" — I-13, NFR-003 | deps: T-021
- 완료 조건(DoD): privacy.md 가 ADR-011 §4·§5 와 모순 없음, 각 케이스가 T-005 테스트로 옮길 수 있는 형태 (출처: STM-0005 §5) + user/02 §10 공통 DoD

## 2. 로드한 컨텍스트
- 관련: LTM I-13(privacy.md N-02·N-04 불일치), D-18(호스트+포트 정확 일치 HostGuard), D-19(settings.port 단일 출처), D-14(비-JSON 403), 패턴 "Host 헤더는 정확히 1개 — 가드에서 판정"
- 근거: workspace/project/adr/ADR-011 §4·§5·§9, workspace/project/security/privacy.md, threat-model.md, STM-0005 §5 의 [security] 후보 2건

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
