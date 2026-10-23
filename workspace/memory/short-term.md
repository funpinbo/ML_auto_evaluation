---
status: active
task: T-023
team: qa
outcome: done
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
- 2026-10-23 10:50 UTC — **세션 중단(사용자 요청 "Stop").** team-qa 작업 도중 중지. **미완료 변경이 커밋 df9508e 에 포함됨**: conftest.py, fixtures/{claude_home,markers,runtime_files}.py, scenarios/test_fixture_jsonl_smoke.py 수정 + fixtures/home_guard.py 신규. 중단 시점 pytest: `2 failed, 72 passed in 1.64s`. 미작성: test-strategy.md ⑦ 보강 등. 재개: STM `status: active` 유지 상태로 `/aidlc-run` → team-qa 작업 모드 재위임, 먼저 위 파일들을 끝까지 읽어 ①~⑦ 중 어디까지 됐는지 확인.

- 2026-10-23 UTC — team-qa 재개. df9508e 변경 확인: ①②(pytest_configure 세션 홈 치환, AIDLC_ROOT/CLAUDE_HOME/CLAUDE_CONFIG_DIR/XDG_CONFIG_HOME 제거), ③ 가드 본체(fixtures/home_guard.py + conftest 설치·_home_guard_check), ④(markers 라벨/인덱스), ⑤(creds-link 상대 symlink), ⑥(-home-fake-project) 는 작성돼 있었음. 2 failed 원인은 test_fixture_jsonl_smoke.py 의 `import os` 누락(NameError) 하나 → 추가. 미작성: ③ 음성 테스트, ⑦.
- scenarios/test_home_guard.py 신규(21건): session 범위 환경 단언, pwd 홈 기록, 실제 홈 open/read_text/listdir/scandir/iterdir/~/.claude 차단(RealHomeAccessError = 시스템 호출 전 차단, FileNotFoundError 아님), tmp→실제 홈 symlink 차단, 삼킨 예외도 기록, 메시지에 전체 경로 없음, 허용 목록(홈·조상·민감 경로 거부, 홈 아래 venv 허용), enabled/disabled 플래그, 상대 symlink 추적.
- ruff: conftest import 정렬(I001) 수정, home_guard.py format, 새 테스트 SIM115/SIM117 정리.
- test-strategy.md ⑦: sources 에 ADR-004·ADR-011, §1 원칙에 3겹 격리·가드 설명, §6.1 fixture 표(가드 fixture, symlink decoy), assert_no_markers 설명, S-10/S-11 ADR-009 Decision 2(쓰기 함수 7종 예외 가짜), S-12 exit 64/1·NO_LOOP 는 backend T-008 단위 테스트 범위.

## 4. 발견 사항 (LTM 후보)
- 결정: 테스트 홈 격리는 3겹(pytest_configure 세션 치환 + autouse 테스트별 치환 + sys.addaudithook 가드). 가드는 제거 불가라 `enabled` 플래그, 음성 테스트는 `home_guard.expect()` 블록 사용.
- 패턴: 가드 음성 테스트는 실제 홈 아래 **존재하지 않는 이름**만 쓰고, 기대 예외를 `RealHomeAccessError`(PermissionError 하위)로 단언해 "시스템 호출 전 차단"을 증명한다. 허용 목록 로직은 hook 미설치 HomeGuard 인스턴스 + 합성 홈(tmp)으로 단위 검증.
- 이슈/리스크: 가드는 정수 fd·dir_fd 상대 경로·os.stat 등 감사 이벤트 없는 호출은 보지 않는다(home_guard.py 문서화). 앱 코드(T-005~) 가 생기면 subprocess 로 띄우는 서버는 이 가드 밖이므로 env 주입·표식 검사로 보완해야 한다.
- 교훈: 중단 후 커밋된 반쪽 변경은 실패 원인이 사소한 경우(import 누락)가 많다 — 갈아엎기 전에 먼저 실행해 원인 확인.

## 5. 새로 발견된 Task (Task 후보)
- [backend] T-005 이후 앱 어댑터가 `projects/<enc>/` 안 상대 symlink(`creds-link.jsonl -> ../../.credentials.json`)를 프로젝트 디렉터리 기준으로 거부하는지 단위 테스트(`symlink_escape.credentials_link` fixture 사용, P-28·P-30) — 기존 T-005/T-006 DoD 에 포함되지 않았다면 추가.

## 6. 결과 & 인수인계
- 산출물(파일/PR): monitor/backend/tests/conftest.py, fixtures/home_guard.py(format), scenarios/test_fixture_jsonl_smoke.py(import os), scenarios/test_home_guard.py(신규), workspace/project/qa/test-strategy.md. (df9508e 의 claude_home.py·markers.py·runtime_files.py 는 그대로 유지)
- 검증 결과(실제 실행):
  - `monitor/.venv/bin/python -m pytest monitor/backend/tests -q` → `95 passed in 0.91s` (기존 74 + 새 21; 72 + df9508e 추가 2)
  - `cd monitor/backend && ../.venv/bin/ruff check tests` → `All checks passed!`
  - `../.venv/bin/ruff format --check tests` → `15 files already formatted`
  - `python3 aidlc/scripts/aidlc.py check project` → `GATE PASS`
  - `python3 -m unittest discover -s aidlc/tests` → `OK`
- 남은 일: 리뷰 게이트(qa·security·architecture). 커버리지(pytest-cov 미설치)·frontend 테스트는 이 Task 범위 밖.

## 7. 리뷰 기록 (리뷰 게이트)
<!-- /aidlc-run 이 리뷰 게이트 대상 팀을 리뷰 모드로 호출하면 각 팀이 한 줄씩 추가 -->
| 팀 | 결과 | 근거 | 필요한 조치 |
|----|------|------|-------------|
