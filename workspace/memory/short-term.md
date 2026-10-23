---
status: active
task: T-006
team: ops
outcome: done
opened_at: 2026-10-23T18:10:57+00:00
---
# Short-term Memory

> **계층 4 (작업 단위).** Task 1개를 수행하는 동안의 작업 메모리. 한 번에 하나만 열린다.
> 수명: `status: active` 로 열고 → 작업 → `outcome` 기록 → `status: closed` 로 닫는다.
> 닫히는 순간 Hook 이 이 파일을 `archive/STM-xxxx_<task>.md` 로 옮기고 Long-term memory 갱신(cascade 1/3)을 요구한다.
> frontmatter 값: status(idle|active|closed) / outcome(done|partial|blocked)

## 1. 목표
- Task: T-006 [ops] logging_config + GET /api/v1/health(소스 접근 가능 여부·데우기 진행률·앱 식별자) + 런북 — NFR-002, CON-05 | deps: T-005
- 완료 조건(DoD): health 테스트 통과, 로그에 본문·경로·ID 없음, T-005 연결 지점 사용(`app/api/health.py` 의 `router` 자동 마운트, `app/logging_config.setup_logging()` 자동 호출, health 는 backend 의 `source_status()`·데우기 진행률 읽기 함수 호출) + user/02 §10 공통 DoD

## 2. 로드한 컨텍스트
- 관련: NFR-002, CON-05, user/02 §7(로깅), 03 §7(관측성), QS-11(heartbeat 만료 표시)
- 소유(40 §1.1): app/logging_config.py, app/api/health.py, app/models/health.py, tests/ops/
- 연결 지점(T-005): `app/api/health.py` 의 `router` 자동 마운트, `app/logging_config.setup_logging()` 자동 호출, backend 읽기 함수 `source_status()`·데우기 진행률 호출
- LTM: D-08(envelope), D-26(에러 코드), D-30(가드 체인), D-32(포트), 패턴(TestClient base_url, 로그에 경로·ID·본문 금지), backend 실행 명령

## 3. 작업 로그
<!-- 시간순으로 짧게. 무엇을 했고 무엇을 봤는지 -->
- T-005 연결 지점 확인: `main.py` 가 `app.api.health.router` 를 `/api/v1` 아래 자동 포함, `app.main.setup_logging()` 이 `app.logging_config.setup_logging()` 에 위임. `__main__` 은 이미 `access_log=False, log_config=None`.
- backend 에 `source_status()`·`warmup.progress()` 읽기 함수가 **없음**(services/ 에 usage·warmup 미구현, contracts/README 에 내부 인터페이스 절 없음). → backend 파일은 고치지 않고 health 안에서 `stat`/`access` 만으로 소스 상태를 판정(파일 열기·나열·쓰기 없음), 데우기는 `app.state.warmup.progress()` 가 있으면 읽고 없으면 `not_started` (§5 [backend] 후보).
- `app/models/health.py`: `HealthData{status:"ok", app:"aidlc-monitor"(Literal), version, sources{workspace, claude_projects, statusline, control}: ok|missing|stale|unreadable, dist: ok|missing, usage_warming{state: not_started|warming|done|unknown, progress 0~1|null}}`, 응답은 `Envelope[HealthData]`(D-08).
- `app/api/health.py`: 경고 문구 고정(경로 없음), 경고 있으면 `meta.status=partial`, 경고 없이 데우는 중이면 `warming`. control 없음은 정상이라 경고 없음. statusline 은 파일 mtime 10분 초과 시 `stale`(내용 미파싱). backend `Panel`(meta 조립)·`Services.clock` 재사용.
- `app/logging_config.py`: stderr 1핸들러(멱등), `SafeFormatter` = 포맷 `%(asctime)s %(levelname)s %(message)s`, 메시지 경로·UUID·req_/msg_/toolu_·sk-·Bearer 가림(2차 방어), 줄바꿈→공백, traceback 대신 `(ExceptionType)`. `uvicorn.access` disabled(결정: 끔), `uvicorn`/`uvicorn.error` 는 root 로, httpx WARNING.
- tests/ops 40건(health 27, logging 13). 첫 실행에서 `%d` 인자 오류 테스트가 pytest caplog 핸들러에서 터짐 → 포매터 단위 테스트로 변경. 앱 로그 테스트가 빈 로그로 통과하던 것 발견 → 패널 예외·데우기 예외를 주입해 ERROR/WARN 줄이 실제로 나오는 것까지 단언.
- OpenAPI export + `docs/api/reference.md` 재생성, `export_openapi.py --check` 최신.
- 실제 서버 스모크: `AIDLC_ROOT=<repo> CLAUDE_HOME=<scratch> python -m app --port 18999` → health 200(partial: statusline·dist missing), Host `evil` → 400, 콘솔에 access log 없음·uvicorn 시작/종료 줄만 포맷대로.
- 문서: `workspace/project/ops/README.md`(로컬 실행 전제·health 필드 표), `logging.md`, `runbooks/` 5종(server-wont-start, port-in-use, statusline-not-running, pause-not-releasing, warmup-slow). charter §2 위치를 따름(지시문의 `workspace/teams/ops/runbook.md` 대신).

## 4. 발견 사항 (LTM 후보)
- 결정: health 는 공통 봉투 `{data, meta}` — 런처(T-007)는 `data.app == "aidlc-monitor"` 로 판정(20 §5 의 `{status, app, ...}` 는 `data` 안). 소스 상태 4종 `ok|missing|stale|unreadable` + `dist` 추가(ADR-005 §3 "health 에 표시"), 소스 문제는 200 + partial.
- 결정: uvicorn access log 는 끈다(`__main__` access_log=False + `setup_logging()` 이 `uvicorn.access` disabled → `uvicorn app.main:app` 경로도 차단). 예외 로그는 traceback 없이 예외 타입만.
- 결정: health 소스 판정은 `stat`/`access` 만(열기·나열·쓰기 없음). statusline stale = 파일 mtime 10분 초과(내용 미파싱).
- 패턴: 로그 비노출 테스트는 "로그가 실제로 나왔다" 를 같이 단언한다 — 아니면 빈 로그로 통과한다(실제로 그랬음).
- 패턴: pytest 의 caplog 핸들러가 root 에 붙어 있어 잘못된 %-인자 로그는 테스트 쪽에서 터진다 → 포매터는 LogRecord 직접 생성으로 테스트.
- 이슈/리스크: backend 는 현재 파일 누락·형식 오류 때 WARN 로그를 남기지 않는다(패널 meta 경고만). NFR-002 "WARN 1줄" 과 20 §6 "시작 시 INFO 로 소스 해석 결과" 가 미구현.
- 교훈: 연결 지점 함수(`source_status()` 등)가 문서에만 있고 코드에 없을 수 있다 — 작업 전 grep 으로 확인.

## 5. 새로 발견된 Task (Task 후보)
- [backend] T-010 에서 데우기 진행률을 `app.state.warmup` (메서드 `progress() -> UsageWarming | {"state","progress"}`) 로 노출 — health 가 이미 읽는다. 다른 시그니처를 택하면 `app/api/health.py::_warming` 조정을 [ops] 후보로.
- [backend] 리더가 파일 누락·형식 오류 시 `log.warning("<파일 종류> 형식 오류 N건")`(경로·내용 없이) 남기기 + 시작 시 INFO 로 소스 해석 결과(찾음/못 찾음) 1줄 (NFR-002, 20 §6). `workspace/project/ops/logging.md` 규칙 따름.
- [backend] (선택) `source_status()` 를 services 에 두려면 health 의 `_state()` 판정을 옮기고 health 는 호출만 — 지금은 health 내부 stat 판정이 단일 출처.
- [architecture] 20 §5 health 행을 실제 계약(봉투 `data` 안 `{status, app, version, sources, dist, usage_warming}`, 상태 값 집합)으로 갱신, ADR-001 §4 런처 판정을 `data.app` 으로 명시, contracts/README 에 backend→ops 내부 인터페이스 절(`app.state.warmup.progress()`) 추가.
- [ops] `workspace/project/ops/slo.md` (NFR-001·002 → SLI, 측정은 qa T-013) — charter §2 산출물, T-006 범위 밖.
- [cicd] T-007 런처: health 판정은 HTTP 200 + `body["data"]["app"] == "aidlc-monitor"`. 400 `BAD_HOST` 는 포트 불일치 신호. 런북 `workspace/project/ops/runbooks/port-in-use.md`·`server-wont-start.md` 와 문구 맞추기.
- [ops] (security 리뷰 T-006, non-blocking) `logging_config.redact` 2차 방어 보강: 인코딩된 transcript 디렉터리명(`-home-<user>-...`, `C--Users-...`), `/` 포함 상대 경로, `file://` URL, 공백 포함 Windows 경로, `~user/` 를 가리고 tests/ops 에 케이스 추가. `127.0.0.1:<port>` URL 은 유지.

## 6. 결과 & 인수인계
- 산출물(파일/PR): `monitor/backend/app/logging_config.py`, `app/api/health.py`, `app/models/health.py`, `tests/ops/{conftest.py,test_health_endpoint.py,test_logging_config.py}`, `workspace/project/ops/{README.md,logging.md,runbooks/*.md(5)}`, 재생성 `workspace/project/contracts/openapi.json`, `docs/api/reference.md`. backend 소유 파일 변경 없음.
- 검증 결과: `cd monitor/backend && ../.venv/bin/python -m pytest --cov=app -q -p no:cacheprovider` → 561 passed(기존 521 + ops 40), 커버리지 98%(health 97%, logging_config 100%). `ruff check .`·`ruff format --check .` 통과. `export_openapi.py --check` 최신. `aidlc.py check project` GATE PASS. 실제 서버 스모크(health 200·BAD_HOST 400·access log 없음) 확인. 기존 Host 가드 케이스(H-01~H-22 health 대상)·405 테스트가 대역 대신 실제 라우트로 통과.
- 남은 일: §5 후보(backend WARN/INFO 로그, warmup 노출, architecture 문서 정합, cicd 런처 판정). slo.md(NFR-001·002 → SLI)는 이 Task 범위 밖 — 별도 ops Task 필요. 리뷰 게이트: qa(필수), security(로그·health 비노출), cicd(health 계약), backend/architecture(계약 형태) 권장.

## 7. 리뷰 기록 (리뷰 게이트)
<!-- /aidlc-run 이 리뷰 게이트 대상 팀을 리뷰 모드로 호출하면 각 팀이 한 줄씩 추가 -->
| 팀 | 결과 | 근거 | 필요한 조치 |
|----|------|------|-------------|
| architecture | PASS | 계약: 9978e76 의 openapi.json diff 는 추가만 있음(삭제 줄 0). `/api/v1/health` 를 새로 넣은 것이라 하위 호환이 깨지지 않음. 200 응답 = `Envelope_HealthData_` 로 D-08 봉투를 지키고, 소스 문제는 200 + `meta.warnings` 가 있으면 `partial`(D-33), 경고 없이 데우는 중이면 `warming`(20 §5 meta.status 집합 안). `data.app` 은 Literal `aidlc-monitor`(APP_NAME), ADR-001 §4 의 중복 실행 판정과 맞고, 런처가 `data` 안을 읽는 것은 D-08 을 따른 결과라 ADR 위반이 아님. `dist: ok/missing` 은 ADR-005 §3 "health 에 표시" 를 구현한 것이고 sources 4값은 20 §5 를 구체화한 것. 새 의존성 없음(stdlib logging), 03 §9 ADR 대상 아님. 실행한 검증: `export_openapi.py --check` 결과 최신, `openapi_docs.py render` 결과가 docs/api/reference.md 와 diff 0, `aidlc.py check project` GATE PASS, `pytest tests/api tests/ops` 398 passed. 경계: health 의 stat/access 판정은 읽기 전용(원칙 2, ADR-009)이고 쓰기 대상 파일이 없어 R-10 영향 없음. backend 에 `source_status()` 가 없으므로 ops 안에 단일 출처로 두는 것을 허용함(non-blocking). 로그: access log 를 끈 것은 20 §6 결정과 같고 03 §7 필수 신호(콘솔 로그·health)는 충족. | non-blocking: §5 의 [architecture] 후보를 그대로 쓴다(20 §5 health 행을 봉투 `data` 기준 + dist·상태 값 집합으로 갱신, ADR-001 §4 에 `data.app` 명시, contracts/README 에 내부 인터페이스 절 `app.state.warmup.progress() -> {state, progress}` 추가. T-010 전에 하는 것을 권장). `source_status()` 를 backend 로 옮길지는 T-010 때 판단. |
| security | PASS | 실행: `pytest -q` 561 passed. 실서버 2경로(`python -m app`, `uvicorn app.main:app`, 가짜 CLAUDE_HOME) 기동 후 health·Host evil/포트 불일치 400·POST 교차 Origin 403·UUID/경로/`sk-` 를 넣은 404 URL·쿼리·잘못된 HTTP 요청·OPTIONS 프리플라이트(405, ACAO 없음) 를 보내고 SIGINT 로 종료(잔여 프로세스 0). stderr 는 uvicorn 시작/종료와 `Invalid HTTP request received.` 뿐이고 요청 줄·경로·ID·Host 값 0건 → access log 차단이 두 경로 모두 유효(`uvicorn app.main:app` 은 `__getattr__` 가 앱 로드 시 `setup_logging()` 으로 `uvicorn.access` disabled). health 본문은 상태 enum·고정 `app`·version·고정 경고 문구뿐이고 경로·사용자명·ID 없음. `_state()` 는 `os.stat`/`os.access` 만(open·listdir·쓰기 없음), `~/.claude` 는 `projects` 디렉터리 stat 1회, settings.json·인증 파일 미접근, `transcript_dir_name` 미사용(D-13 준수). health 도 Host 가드 뒤. 앱 내 모든 log 호출이 `type(exc).__name__` 만 사용, SafeFormatter 가 exc_info/exc_text/stack_info 제거·줄바꿈 평탄화(로그 위조 방지). redact 직접 시험: POSIX 2단 이상·Windows 드라이브·UNC·`~/`·UUID·req_/msg_/toolu_·sk-·Bearer 가림 확인. 미실행: pip-audit(venv 에 없음)·npm audit — 이 커밋에 의존성 변경 없음. | non-blocking(2차 방어 보강, §5 [ops]): redact 가 가리지 못함 — 인코딩된 디렉터리명(`-home-user-chatbot`, `C--Users-bob-proj`), 상대 경로(`projects/-home-user-x/a.jsonl`), `file:///home/...`, 공백 포함 Windows 경로(`C:\Users\John Doe\..` 뒤쪽 잔존), `~bob/x`. 현재 1차 방어(호출부 type-only)로 실제 노출은 0건. |
| qa | PASS | 실행: `pytest --cov=app -q -p no:cacheprovider` 561 passed, 커버리지 98%(≥70%), `ruff check`·`ruff format --check` 통과, `export_openapi.py --check` 최신, `openapi_docs.py render` 결과 = docs/api/reference.md(diff 0), mypy(ops 3파일) 오류 0(기존 backend 2건 별개). 소유권: `git show 9978e76 --stat` = logging_config·api/health·models/health·tests/ops·workspace/project/ops·openapi.json·reference.md·STM 뿐, backend/qa 소유 파일 변경 없음. 변이 검사(스크래치 사본, tests/ops): POSIX 경로 redact 제거→실패, `uvicorn.access` 재활성(disabled/propagate)→실패, traceback 출력→실패, health 가 파일 open/`read_bytes`→실패(open spy), missing 시 예외(500)→실패, stale 임계 무력화→실패, 데우기 예외 전파→실패, 경고에 경로 삽입→실패, 종류/권한 검사 제거→2건 실패. 11/11 변이 검출. 엣지: 빈 workspace·CLAUDE_HOME/dist 없음→200 partial·경고 4건·경로 0건, broken workspace 200, 디렉터리/파일 종류 뒤바뀜·stat 오류→unreadable, statusline 10분 초과→stale, 조회 전후 해시 불변. 실제 홈: CLAUDE_HOME 은 항상 tmp(`make_settings` 기본값도 root 아래), autouse `_home_guard_check` 켜짐(가드는 os.stat 미감시이나 stat 대상이 전부 tmp 라 문제 없음). DoD 갭: T-005 에 `source_status()`·warmup.progress() 가 없어 "backend 읽기 함수 호출" 문자 그대로는 미충족. health 안의 stat/access 판정이 단일 출처이고 읽기 전용이며 `app.state.warmup.progress()` 연결 지점이 테스트됨 → P1 에서는 허용(§5 [backend] 후보로 추적). user/02 §10 "run.sh 로 화면 확인"은 런처가 T-007 이라 해당 없음, 대신 `python -m app` 스모크(ops·security 실행). | non-blocking: §5 [backend] warmup 노출·WARN/INFO 로그 후보 유지. T-010 에서 `app.state.warmup` 시그니처가 달라지면 tests/ops warmup 케이스로 회귀 확인. home_guard 가 `os.stat` 을 감시하지 않는다는 한계는 qa 쪽에서 기록만(현재 위반 없음). |
