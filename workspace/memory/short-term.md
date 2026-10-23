---
status: active
task: T-003
team: qa
outcome: none
opened_at: 2026-10-23T08:30:00+00:00
---
# Short-term Memory

> **계층 4 (작업 단위).** Task 1개를 수행하는 동안의 작업 메모리. 한 번에 하나만 열린다.
> 수명: `status: active` 로 열고 → 작업 → `outcome` 기록 → `status: closed` 로 닫는다.
> 닫히는 순간 Hook 이 이 파일을 `archive/STM-xxxx_<task>.md` 로 옮기고 Long-term memory 갱신(cascade 1/3)을 요구한다.
> frontmatter 값: status(idle|active|closed) / outcome(done|partial|blocked)

## 1. 목표
- Task: T-003 [qa] test-strategy.md + 공용 fixture(conftest: 빈/일부/전체/깨짐/closed STM workspace, 가짜 JSONL 생성기 — 본문 표식 문자열 포함, 스냅샷 fixture) — NFR-001, NFR-002 | deps: T-001
- 완료 조건(DoD): fixture 를 import 하는 smoke 테스트 통과 + user/02 §10 공통 DoD (ruff 통과, 관련 문서 갱신)

## 2. 로드한 컨텍스트
- 관련: NFR-001(성능, Task 100 + 30일 JSONL), NFR-002(깨진 입력 500 0건), NFR-003(본문 표식 문자열 비노출), CON-03(해시 불변, closed STM fixture 필수), CON-06(실제 `~/.claude` 금지, 경로는 `AIDLC_ROOT`·`CLAUDE_HOME` 환경 변수/설정 주입), QS-01~04·06·07, FR-003(Hook 규칙 대조), FR-005(일시정지/재개 시나리오)
- 팀 charter: workspace/teams/qa/charter.md (소유: `monitor/backend/tests/{conftest.py,fixtures/,scenarios/,perf/}`, `monitor/frontend/tests/`, `workspace/project/qa/`. unit/·api/ 는 backend 소유)
- 보안 입력: workspace/project/security/privacy.md §8~(본문 비노출 테스트 기준 T-xx), threat-model.md — fixture 의 본문 표식 문자열·symlink/경로 이탈 음성 케이스를 만들 때 따른다
- 계약: workspace/project/contracts/ (claude-status / control / loop-status 스키마, README §2·§3 transcript_dir_name 규칙 D-13)
- 가짜 JSONL 생성기 원본: workspace/project/eda/bench_synthetic.py (`fake_line`, `build`) — 이식하되 결정적(seed 고정), 본문은 가짜 + 표식 문자열 포함
- EDA 근거(30): 중복 requestId 57.95%(응답 1개가 최대 7줄), `"usage"` 문자열은 있으나 `message.usage` 없는 줄 11.7%, 서브에이전트 기록은 `<세션>/subagents/agent-*.jsonl`, 한 줄 최대 ~236 KB, timestamp 는 UTC `Z`
- LTM: D-02(허용 필드·requestId 중복 제거), D-07(`status` 서브프로세스 금지 — closed STM fixture 로 해시 불변 검증), D-13, 패턴(`format` 비강제 → 음성 케이스도 스키마로 실행)
- 환경: pytest·fastapi 미설치(Python 3.13). 패키지 전역 설치 금지(02 §11) → `monitor/.venv`(gitignore 됨)에 설치. requirements-dev.txt 는 cicd 소유(T-007) — 필요한 dev 패키지는 STM §5 에 `[cicd]` 후보로 남긴다. monitor/ 디렉터리는 아직 없음.

## 3. 작업 로그
<!-- 시간순으로 짧게. 무엇을 했고 무엇을 봤는지 -->
- 2026-10-23 **세션 일시 중단(사용자 요청, 나중에 재개).** team-qa 작업 도중 오케스트레이터가 중지함. 완료 여부 미검증.
  - 존재: `monitor/backend/tests/conftest.py`, `tests/fixtures/*.py`(workspace, jsonl_gen, claude_home, hashing, markers, contracts, runtime_files, reference_parser), `tests/scenarios/test_fixture_{contract,jsonl,workspace}_smoke.py`. `monitor/.venv`(pytest 9.1.1 등) 생성됨(gitignore).
  - 미작성: `workspace/project/qa/test-strategy.md`. 마지막 파일 수정 도중 중단되어 fixture 일부가 덜 쓰였을 수 있음 → 재개 시 먼저 `monitor/.venv/bin/python -m pytest monitor/backend/tests -q` 와 ruff 로 상태 확인.
  - 재개 방법: STM 을 `status: active` 로 둔 채 `/aidlc-run` → 0단계에서 이 STM 이어받아 3단계(team-qa 작업 모드 재위임). 남은 일: test-strategy.md, smoke 통과·ruff 확인, STM §5 `[cicd]` dev 패키지 후보 기록, §6 검증 결과, outcome 설정 → 리뷰 게이트(security, architecture 등) → 닫기.

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
