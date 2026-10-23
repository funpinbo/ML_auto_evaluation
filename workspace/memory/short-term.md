---
status: active
task: T-023
team: qa
outcome: none
opened_at: 2026-10-23T10:48:11+00:00
---
# Short-term Memory

> **계층 4 (작업 단위).** Task 1개를 수행하는 동안의 작업 메모리. 한 번에 하나만 열린다.
> 수명: `status: active` 로 열고 → 작업 → `outcome` 기록 → `status: closed` 로 닫는다.
> 닫히는 순간 Hook 이 이 파일을 `archive/STM-xxxx_<task>.md` 로 옮기고 Long-term memory 갱신(cascade 1/3)을 요구한다.
> frontmatter 값: status(idle|active|closed) / outcome(done|partial|blocked)

## 1. 목표
- Task: T-023 [qa] 홈 격리 강화 + test-strategy 보강: ① `pytest_configure`(또는 session autouse)에서도 HOME/USERPROFILE 치환·`AIDLC_ROOT`/`CLAUDE_HOME` 제거 ② `CLAUDE_CONFIG_DIR` 제거 또는 미설정 단언 ③ conftest `sys.addaudithook` 가드(실제 홈 아래 open/listdir/scandir 시 실패) ④ `assert_no_markers(extra=...)` 실패 메시지는 라벨/인덱스만 ⑤ decoy 인증 파일을 가리키는 symlink 음성 케이스 ⑥ `VALID_DIR_NAMES` 의 실제 경로 인코딩을 합성 이름으로 교체 ⑦ test-strategy S-10/S-11 에 ADR-009 Decision 2(쓰기 함수 가짜 예외) 검증, S-12 에 exit 64/1·NO_LOOP 는 T-008 범위 명시, sources 에 ADR-004·ADR-011 — I-09, NFR-003 | deps: T-003
- 완료 조건(DoD): 기존 72건 + 새 가드 테스트 통과, 가드가 실제 홈 접근을 잡는 음성 테스트 포함 (출처: STM-0004 §5, security·architecture 리뷰 비차단 후속; 앱 코드 시작 전이라 T-005 앞) + user/02 §10 공통 DoD

## 2. 로드한 컨텍스트
- 관련: LTM I-09(홈 격리 범위), D-16(테스트는 실제 ~/.claude 금지), security 팀 지식(audit-hook 가드 승격), STM-0004 §5 후속 ①~⑦
- 근거: workspace/project/qa/test-strategy.md, workspace/project/security/privacy.md §7, monitor/backend/tests/{conftest.py,fixtures/}
- 실행: `monitor/.venv/bin/python -m pytest monitor/backend/tests -q` (현재 72 passed)

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
