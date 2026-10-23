---
status: active
task: T-003
team: qa
outcome: done
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
- 2026-10-23 **재개(team-qa 작업 모드).** fixture 9개 모듈·conftest·smoke 3파일을 끝까지 읽어 덜 쓰인 부분 점검 → 미완성 코드 없음(모든 함수·dataclass 종결, 커밋 0766beb 와 작업 트리 동일, `git status` 깨끗). 코드 수정 없음.
  - 검증 재실행: pytest 72 passed(루트·`monitor/backend` 양쪽, `--import-mode=importlib` 포함), ruff check / ruff format --check 통과.
  - perf 크기 실측(스크래치패드, 실행 후 삭제): 기본 1.6 MB / `responses_per_day=300, body_pad=3000` 129.4 MB 1.09 s / `300, 8000` 298.9 MB 2.04 s → 329~658 MB 는 pad 9000~18000 추정.
  - `workspace/project/qa/test-strategy.md` 작성(원칙, 피라미드, 소유 경계, 시나리오 S-01~S-13·P-01~P-02, perf 절차 §5, fixture 카탈로그 §6, 실행 §7, 게이트 §8, privacy/contracts 추적 §9, 리스크 §10). 코드 docstring 의 "§5 perf 절차", "§6 사용 규칙" 참조와 절 번호 일치.
  - `aidlc.py check project` GATE PASS.

## 4. 발견 사항 (LTM 후보)
- 결정:
  - qa fixture 는 `HOME`/`USERPROFILE` 을 autouse 로 임시 경로로 바꾸고 `AIDLC_ROOT`/`CLAUDE_HOME` 을 지운다. 앱 경로 주입은 `app_env` 환경 변수뿐 (CON-06)
  - 생성기 기대값(`JsonlManifest.expected_buckets`)을 독립 오라클(`reference_parser.aggregate`)로 교차 검증하고, 앱 수집기는 둘과 비교한다
- 패턴:
  - 본문 표식은 영숫자만 쓴다 — Claude Code 경로 인코딩(`[^A-Za-z0-9] → -`)에서 밑줄 등이 바뀌면 표식이 깨진다
  - `tests/` 에 `__init__.py` 없음, `from fixtures...` import, 테스트 파일 basename 은 디렉터리가 달라도 중복 금지 (`conftest.py` 가 importlib 모드도 보강)
  - `assert_no_markers` 실패 메시지는 표식 종류만 적고 주변 내용은 적지 않는다(테스트 로그 자체가 노출 경로가 되지 않게)
  - 시나리오 ID S-01~S-13, P-01~P-02 는 test-strategy.md §4 에서만 정의, 다른 문서는 참조만
- 이슈/리스크:
  - jsonschema 를 dev 의존성으로 쓰고 있으나 ADR-006 dev 목록(pytest, pytest-cov, httpx, ruff, pip-audit)에 없음
  - pytest-cov·httpx·fastapi 미설치 → 커버리지·API 테스트는 T-005/T-007 이후에만 측정 가능
  - perf 30일 329~658 MB 크기는 선형 추정(pad 9000~18000), T-013 에서 실측 보정 필요
- 교훈:
  - 중단된 세션을 이어받을 때는 테스트 통과만이 아니라 모듈을 끝까지 읽고 `git status`/커밋과 대조해 반쯤 쓴 파일이 없는지 확인한다

## 5. 새로 발견된 Task (Task 후보)
- [cicd] T-007 에서 `monitor/backend/requirements-dev.txt` 에 qa 가 실제로 쓰는 dev 의존성을 `==` 고정: `pytest==9.1.1`, `jsonschema==4.26.0`(전이: `referencing==0.37.0`, `jsonschema-specifications==2025.9.1`, `rpds-py==2026.9.1`, `attrs==26.1.0`), `ruff==0.17.2`, `pytest-cov`(미설치, 고정 버전 결정 필요), `httpx`(TestClient, ADR-006). venv `pip freeze` 로 확정. 근거: test-strategy.md §7·§8
- [architecture] ADR-006 Decision 2 의 dev 의존성 목록에 `jsonschema`(계약 스키마 검증, MIT) 추가 — 이미 qa fixture(`tests/fixtures/contracts.py`)가 사용 중. T-008 DoD 의 "jsonschema 를 dev 의존성으로 쓰면 ADR-006 갱신" 조건이 T-003 에서 먼저 충족됨
- [qa] T-013 에서 pytest marker `perf` 등록(backend 의 pytest 설정 파일 생성 시점에 맞춰)과 30일 329~658 MB 실측 크기 보정

## 6. 결과 & 인수인계
- 산출물(파일/PR):
  - 신규: `workspace/project/qa/test-strategy.md`
  - 기존(커밋 0766beb, 이번 세션 무수정): `monitor/backend/tests/conftest.py`, `tests/fixtures/{__init__,workspace,jsonl_gen,claude_home,markers,hashing,contracts,runtime_files,reference_parser}.py`, `tests/scenarios/test_fixture_{contract,jsonl,workspace}_smoke.py`
- 검증 결과 (2026-10-23, 직접 실행):
  - `monitor/.venv/bin/python -m pytest monitor/backend/tests -q` → `72 passed in 0.46s`
  - `cd monitor/backend && ../.venv/bin/python -m pytest -q` → `72 passed in 0.57s`; `--import-mode=importlib -p no:cacheprovider` → `72 passed in 1.40s`
  - `monitor/.venv/bin/ruff check monitor/backend/tests` → `All checks passed!`
  - `monitor/.venv/bin/ruff format --check monitor/backend/tests` → `13 files already formatted`
  - `python3 aidlc/scripts/aidlc.py check project` → `GATE PASS`
  - 커버리지: 미측정(`app/` 코드 없음, pytest-cov 미설치) — T-003 DoD 대상 아님
- 남은 일: 리뷰 게이트(qa 자체 외 security — 표식/privacy §7 정합, architecture — contracts 사용 정합). §5 후보 3건 반영. FR 별 `test-cases/FR-xxx.md` 는 T-004 스토리 확정 후

## 7. 리뷰 기록 (리뷰 게이트)
<!-- /aidlc-run 이 리뷰 게이트 대상 팀을 리뷰 모드로 호출하면 각 팀이 한 줄씩 추가 -->
| 팀 | 결과 | 근거 | 필요한 조치 |
|----|------|------|-------------|
