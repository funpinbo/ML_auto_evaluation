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

## 6. 결과 & 인수인계
- 산출물(파일/PR): `monitor/backend/app/logging_config.py`, `app/api/health.py`, `app/models/health.py`, `tests/ops/{conftest.py,test_health_endpoint.py,test_logging_config.py}`, `workspace/project/ops/{README.md,logging.md,runbooks/*.md(5)}`, 재생성 `workspace/project/contracts/openapi.json`, `docs/api/reference.md`. backend 소유 파일 변경 없음.
- 검증 결과: `cd monitor/backend && ../.venv/bin/python -m pytest --cov=app -q -p no:cacheprovider` → 561 passed(기존 521 + ops 40), 커버리지 98%(health 97%, logging_config 100%). `ruff check .`·`ruff format --check .` 통과. `export_openapi.py --check` 최신. `aidlc.py check project` GATE PASS. 실제 서버 스모크(health 200·BAD_HOST 400·access log 없음) 확인. 기존 Host 가드 케이스(H-01~H-22 health 대상)·405 테스트가 대역 대신 실제 라우트로 통과.
- 남은 일: §5 후보(backend WARN/INFO 로그, warmup 노출, architecture 문서 정합, cicd 런처 판정). slo.md(NFR-001·002 → SLI)는 이 Task 범위 밖 — 별도 ops Task 필요. 리뷰 게이트: qa(필수), security(로그·health 비노출), cicd(health 계약), backend/architecture(계약 형태) 권장.

## 7. 리뷰 기록 (리뷰 게이트)
<!-- /aidlc-run 이 리뷰 게이트 대상 팀을 리뷰 모드로 호출하면 각 팀이 한 줄씩 추가 -->
| 팀 | 결과 | 근거 | 필요한 조치 |
|----|------|------|-------------|
