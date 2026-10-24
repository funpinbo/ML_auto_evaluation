---
status: active
task: T-008
team: backend
outcome: done
opened_at: 2026-10-23T18:58:50+00:00
---
# Short-term Memory

> **계층 4 (작업 단위).** Task 1개를 수행하는 동안의 작업 메모리. 한 번에 하나만 열린다.
> 수명: `status: active` 로 열고 → 작업 → `outcome` 기록 → `status: closed` 로 닫는다.
> 닫히는 순간 Hook 이 이 파일을 `archive/STM-xxxx_<task>.md` 로 옮기고 Long-term memory 갱신(cascade 1/3)을 요구한다.
> frontmatter 값: status(idle|active|closed) / outcome(done|partial|blocked)

## 1. 목표
- Task: T-008 [backend] 루프 제어 CLI(aidlc/scripts/loop_control.py + aidlc.py loop-start/loop-check/wait-resume/loop-end) + GET /control, POST /control/pause·resume + R-01 스파이크 — FR-005 | deps: T-001, T-005, T-020, T-026
- 완료 조건(DoD): exit code 계약(D-09: 0/10/20/2/64/1) 테스트·일시정지/재개/episode 상한 초과·NO_LOOP 시나리오 테스트 통과, 쓰기 결과를 contracts 스키마로 검증하는 테스트(jsonschema 를 dev 의존성으로 쓰면 ADR-006 갱신), loop-cli §2.1·§7.1~§7.3 구현(D-39·D-40: seq 발급 max+1, 엄격 정수 술어 CLI·대시보드 공유, 상한·락 타임아웃·임시 파일·고정 메시지) + SQ-1~SQ-21 전 시나리오 테스트, 스파이크 결과 STM 기록, privacy.md C-01~C-03·H-01~H-03 POST 통과 기대값을 실제 control 라우트 기준("400/403/422 아님", 루프 없음 409)으로 조정(I-25), T-005 하드닝(I-24: `server_header=False`, 텔레메트리 명시 비활성 + 테스트, 가짜 Hook 쓰기 함수 호출을 모든 workspace kind 에서 `calls == []` 단언, `asgi_http` receive 짧은 timeout), backend mypy 오류 5건(aidlc_reader.py:173, pipeline.py:294, security.py:203·204, static_files.py:86) 수정·`monitor/tools/check.py` 게이트 전 단계 통과(I-29·I-30) + user/02 §10 공통 DoD

## 2. 로드한 컨텍스트
- 관련 FR: FR-005 (stories/FR-005.md AC-1~23, 화면 라벨 V1~V6), 01 §10 결정(같은 세션 대기 후 자동 재개)
- 계약: contracts/loop-cli.md (§2.1 엄격 정수, §7 seq 발급, SQ-1~SQ-21, exit 0/10/20/2/64/1, stdout 한 줄), control.schema.json, loop-status.schema.json, ADR-004 Decision 1.1
- LTM: D-04, D-09~D-11, D-26, D-39, D-40, I-24(하드닝), I-25(C/H POST 기대값), I-29·I-30(mypy 5건), R-01(Bash 호출 끊김 위험)
- 실행: `cd monitor/backend && ../.venv/bin/python -m pytest --cov=app -q -p no:cacheprovider`, 게이트 `monitor/.venv/bin/python monitor/tools/check.py`

## 3. 작업 로그
<!-- 시간순으로 짧게. 무엇을 했고 무엇을 봤는지 -->
- 시작 시 게이트 FAIL 원인은 mypy 5건뿐. 고침: aidlc_reader `set_data` 의 data 를 `Buffer` 로(3.11 호환을 위해 TYPE_CHECKING 안에서 typing_extensions import), pipeline `stage_state -> StageState`(type: ignore 제거), security `wrap_guards` 중간 변수를 `ASGIApp` 로, static_files `response: Response` (I-30)
- `aidlc/scripts/loop_control.py` 작성(stdlib 단독): 4개 서브커맨드, 직접 만든 인자 파서(usage 오류 64, `--opt v`/`--opt=v`, 반복·모르는 옵션 거부, ASCII 10진수만), §2.1 엄격 판독(parse_int 16자리 상한, parse_constant 거부, UTF-8/BOM/RecursionError/64 KiB 상한 → broken), loop-status 전체 검증(조건부 규칙 + done ≤ total), 원자적 쓰기(mkstemp → fsync → os.replace 5×50 ms 재시도 → finally unlink, 실패는 stderr 경고만), 예외 → exit 1 + 예외 종류만
- `aidlc.py` 에 loop-* 등록 블록(주석으로 구간 표시)만 추가: importlib 로 loop_control 을 불러오고 `sys.dont_write_bytecode=True`(저장소에 .pyc 안 만듦), import 실패도 exit 1 + 예외 종류만
- (API 사용량 한도로 중단 → 코디네이터 WIP 커밋 8855519 → 재개)
- backend: `services/control.py`(술어 사본 + 판정 + 쓰기, 프레임워크 무의존·도메인 예외), `models/control.py`(ControlData, PauseRequest StrictInt 600~86400 extra=forbid, ResumeRequest `{}` 만), `api/control.py`(GET + POST 2개, NoActiveLoop→409, ControlWriteFailed→500), main/deps 연결
- I-24: `uvicorn.run(server_header=False)`, `FastAPI(telemetry={tracing,metrics,logs,operation_spans,auto_configure: False})`, 가짜 Hook 쓰기 함수 테스트를 5개 kind 전부·호출 기록 `calls == []` 단언으로(+GET /control 포함), `asgi_http` 두 번째 receive 0.05 s
- I-25: control 대역 라우트 제거, Host·Content-Type 가드 테스트의 통과 기대값을 "400/403/422 아님" + 활성 루프 없음 pause 409 / resume 200 으로, 활성 루프 있는 C-01~C-03 pause·resume 200 테스트 추가(쓰인 파일 스키마 검증, 그 밖의 트리 해시 불변)
- 테스트 추가: test_loop_cli.py 61건(시계 주입, 실제 서브프로세스 포함), test_loop_strict_parity.py 112건(CLI·대시보드·jsonschema 판정 교차), test_control_api.py 66건(SQ-1~SQ-21, V1~V6, 422/409, AC-1~5 흐름), test_app_factory I-24 3건
- export_openapi → openapi_docs render 로 openapi.json·docs/api/reference.md 재생성
- 검증: `monitor/.venv/bin/python monitor/tools/check.py` 게이트 PASS(ruff·mypy 2종·pytest backend 811 passed 커버리지 98%·launcher 37·OpenAPI diff·레퍼런스 신선도), Hook 테스트 31 OK, `aidlc.py check project` PASS
- R-01 스파이크(이 backend 서브에이전트의 Bash 도구, 실제 저장소 workspace): loop-start 3 → 서비스로 pause(seq 1) → loop-check 1 exit 10 → `wait-resume --max-wait 120` (Bash timeout 600000) 120.13 s 후 exit 10 STILL_PAUSED → `--max-wait 300` 300.24 s 후 exit 10(paused_sec 430, paused_since 누적 확인) → 백그라운드 일회성 스크립트가 15 s 뒤 resume(seq 2) 기록 23:48:14.490, wait-resume 23:48:15.415 exit 0 RESUMED(지연 0.93 s) → 다시 pause(seq 3) → loop-check 2 exit 10 → **기본값 540** 호출 540.37 s 후 exit 10(새 episode, paused_sec 540) → loop-end blocked --done 2 → `.control.json`·`.monitor/` 삭제로 원상 복구, 남은 프로세스 없음

## 4. 발견 사항 (LTM 후보)
- 결정:
  - 엄격 정수 술어는 import 공유 대신 **사본 + 교차 테스트**: CLI 는 stdlib 단독 스크립트이고 대시보드는 다른 `AIDLC_ROOT` 를 볼 수 있어 서로 import 하지 않는다. `test_loop_strict_parity.py` 가 같은 바이트 코퍼스(40종 control, 25종 loop-status)에 대해 CLI 판정 = 대시보드 판정 = (jsonschema 통과 ∧ type(x) is int) 임과 상수·정규식 동일을 단언 (T-008)
  - 판독은 스키마보다 약간 더 엄격(같은 방향, 양쪽 동일): UTF-8 BOM·64 KiB 초과·실재하지 않는 날짜(13월)·끝 개행 시각은 broken. loop-status 는 `iterations_done ≤ iterations_total` 불변식까지 검사 → 위반이면 CLI NO_LOOP = 대시보드 409 로 일치
  - GET /control 화면 상태 6종(running/pause_requested/paused/resume_requested/no_session/ended)에 loop-status **없음도 ended**(V1, `meta.status=empty`, `loop_file=missing`)로 둔다. 깨짐 = `meta.status=error` SOURCE_PARSE_ERROR "루프 상태를 읽을 수 없음", 제어 파일 깨짐 = `partial` + 경고. 응답은 20 §5 ControlView 필드 + `view`(V1~V6)·`label`·`hint`·`can_pause`/`can_resume`·`control_seq`·`baseline_seq`·`control_file`/`loop_file`·`ended_reason`/`ended_message`
  - POST /resume 본문은 `{}` 만(`max_pause_sec` 를 주면 422) — 재개는 이전 값을 유지하므로 받을 이유가 없다. POST /pause 의 `max_pause_sec` 는 StrictInt(`true`·`600.0`·`"600"` → 422). 본문 생략도 허용(기본 7200)
  - 대시보드는 디렉터리를 만들지 않는다: `workspace/memory/` 가 없으면 resume 도 500 CONTROL_WRITE_FAILED(쓰기 경로 `.control.json` 하나 유지)
  - CONTROL_WRITE_FAILED 고정 문구 = errors.py 기존 MESSAGES 값 "제어 파일을 쓰지 못했습니다." (새 코드 없음, D-26)
  - **R-01 통과(이 환경)**: Bash 도구 호출이 120 s·300 s·540 s(기본값) 대기를 끊김 없이 견디고 exit 10 을 돌려줬고, 대기 중 resume 은 0.93 s 안에 exit 0. 01 §10 "같은 세션 대기 후 자동 재개" 설계와 `--max-wait 540` 기본값을 유지할 근거. 후퇴안(ADR-004 Alternative B) 불필요
- 패턴:
  - 대기 루프 테스트는 벽시계·monotonic·sleep 을 하나의 가상 시계(`SimClock`)로 묶고 `sleep` 에 tick 콜백을 달아 "tick n 에서 POST/삭제/손상" 을 결정적으로 주입 — 7200 s 상한·540 s max-wait 도 실제 대기 0 (T-008)
  - CLI 와 API 를 한 workspace 루트에서 in-process 로 번갈아 실행하고, 래퍼에서 매 CLI 호출 전후 `.control.json` 바이트 불변·매 POST 전후 `loop-status.json` 바이트 불변을 단언하면 단일 작성자 규칙(R-10)이 모든 시나리오에 자동 적용된다
  - 동시 POST 의 seq 연속성은 응답 본문(응답 시점 재판독이라 겹칠 수 있음)이 아니라 쓰기 함수 스파이로 발급 seq 를 기록해 확인한다
  - 동적 import 한 모듈에 dataclass 가 있으면 `exec_module` 전에 `sys.modules[name]` 등록 필수(안 하면 AttributeError)
- 이슈/리스크:
  - R-01 은 **backend 서브에이전트의 Bash 도구**에서 측정했다. 사용자가 VS Code 에서 직접 돌리는 `/aidlc-run` 메인 세션의 Bash 도구·다른 OS(Windows)에서 같은 상한인지는 미검증 → T-014 UAT 리허설(R-1~R-3)에서 재확인 필요. 600 s 이상은 측정하지 않음(계약상 max-wait ≤ 580)
  - 화면 V3 의 "세션 활동 = 최근 JSONL 기록 시각" 은 사용량 수집기(T-010) 전이라 ControlView 에 없음
  - `aidlc.py` 상단 docstring(도움말)에 loop-* 가 없다 — 등록 블록 밖이라 손대지 않음
  - pause_timeout 문구의 H 는 `round(max_pause_sec/3600, 2):g` (600 s → "0.17시간") — 정수 시간이 아니면 어색함
- 교훈:
  - 중단 후 재개 때 WIP 파일을 먼저 끝까지 읽고 mypy 를 돌려 반쯤 쓴 타입 오류를 바로 잡았다 — 커밋된 서비스는 완결돼 있었다
  - 테스트 기대값이 틀렸을 때(제어 파일 running 이 남아 있으면 재진입 즉시 재개) 구현을 고치지 말고 계약 문장으로 돌아가 확인한다 — 두 번 모두 구현이 계약대로였다

## 5. 새로 발견된 Task (Task 후보)
- [architecture] (T-009 에 포함 권장) SKILL.md 는 `--max-wait` 기본 540 유지 가능(R-01 서브에이전트 측정 PASS, §4). 20 §5 `/control` 행에 실제 ControlView 필드(view·label·hint·can_pause/can_resume·control_seq·baseline_seq·control_file/loop_file·ended_reason/ended_message)와 "loop-status 없음 = state ended + meta empty", resume 본문 `{}` 전용(max_pause_sec 422) 반영. `aidlc.py` docstring 에 loop-* 사용법 추가 여부 결정(무소유 영역)
- [security] T-008 리뷰: POST /control/* 쓰기 경로(락 2 s·재시도·임시 파일 정리·고정 문구·seq 상한), 술어 사본 교차 테스트, I-24 하드닝(server_header·텔레메트리), I-25 기대값 조정(privacy.md §5.1·§5.2 문구는 이미 "400/403 아님" 이라 문서 수정 불필요로 판단 — 확인 요청)
- [qa] `test-cases/FR-005.md` 를 T-008 테스트(test_loop_cli·test_loop_strict_parity·test_control_api)와 대조, UAT R-1~R-3 에서 메인 세션·Windows Bash 대기 상한 재측정(R-01 잔여)
- [backend] T-011: paused 상태 heartbeat 120 s 경계에서 `control` topic 발행(파일 변경 없음, AC-16). T-010: V3 세션 활동(최근 JSONL 시각)을 ControlView 에 추가

## 6. 결과 & 인수인계
- 산출물(파일/PR):
  - CLI: `aidlc/scripts/loop_control.py`(신규), `aidlc/scripts/aidlc.py`(loop-* 등록 블록만)
  - API: `monitor/backend/app/services/control.py`, `app/models/control.py`, `app/api/control.py`(신규), `app/main.py`(라우터·ControlService·telemetry 끔), `app/api/deps.py`, `app/__main__.py`(server_header=False)
  - mypy 수정: `app/services/aidlc_reader.py`, `app/services/pipeline.py`, `app/security.py`, `app/static_files.py`
  - 테스트: `tests/unit/loop_support.py`, `tests/unit/test_loop_cli.py`, `tests/unit/test_loop_strict_parity.py`, `tests/api/test_control_api.py`(신규), `tests/unit/test_app_factory.py`, `tests/unit/backend_support.py`, `tests/api/test_readonly_guarantees.py`, `tests/api/test_write_guard_cases.py`, `tests/api/test_host_guard_cases.py`
  - 재생성: `workspace/project/contracts/openapi.json`, `docs/api/reference.md`
- 검증 결과:
  - `monitor/.venv/bin/python monitor/tools/check.py` → 게이트 PASS (0 실패; frontend 만 SKIP — T-012 전)
  - backend pytest 811 passed, 커버리지 98% (control.py 96%), launcher 37 passed
  - `python3 -m unittest discover -s aidlc/tests` 31 OK, `aidlc.py check project` GATE PASS
  - DoD 대응: exit 0/10/20/2/64/1·NO_LOOP·episode 상한(작은 max_pause_sec + 가상 시계)·상태 전이 표 전체, SQ-1~SQ-21 전부, 쓰인 두 파일 jsonschema 검증(jsonschema 는 ADR-006 에 이미 dev 의존성으로 기록 — ADR 변경 불필요), 단일 작성자, I-24·I-25·I-30 해소
  - R-01: 120 s·300 s·540 s 대기 생존(exit 10), resume 반영 0.93 s(exit 0) — 이 서브에이전트 Bash 기준
- 남은 일: §5 후보. 리뷰 게이트 대상 — qa(필수), security(POST /control·하드닝), architecture(openapi 변경·aidlc.py 블록·R-01 결과 반영)

## 7. 리뷰 기록 (리뷰 게이트)
<!-- /aidlc-run 이 리뷰 게이트 대상 팀을 리뷰 모드로 호출하면 각 팀이 한 줄씩 추가 -->
| 팀 | 결과 | 근거 | 필요한 조치 |
|----|------|------|-------------|
| architecture | PASS | ADR-009: aidlc.py 변경은 표시된 loop-* 등록 블록 28줄뿐(importlib spec_from_file_location + `sys.dont_write_bytecode=True`, import 실패 exit 1 + 예외 종류만). loop_control.py stdlib 단독(Python 3.11+ = user/02 §1), exit 0/10/20/2/64/1·stdout `AIDLC-LOOP <sub> <RESULT> k=v` 한 줄·HEARTBEAT 30 s·max-wait 1..580 기본 540·SEQ_MAX 2^53−1·술어 `type(x) is int` 확인. ADR-004 1.1: 락 `acquire(timeout=2.0)`, pause 409 NO_ACTIVE_LOOP / resume 언제나 200(46행·SQ-12 일치). ADR-011 §9: 신규 응답 코드 200/400/403/405/409/422/500 만(닫힌 9개 안, 새 코드 없음). R-10: 대시보드 service 는 aidlc 스크립트를 import 안 함, 쓰기는 `.control.json` 하나·mkdir 없음. openapi.json diff 는 추가만(삭제 0줄) → 하위 호환. 실행: `export_openapi.py --check` "최신", openapi_docs render 재생성 = docs/api/reference.md 동일, pytest loop/control 3파일 239 passed, Hook 테스트 OK, `check project` GATE PASS. 설계 판단: 술어 사본+교차 테스트 승인(원칙: CLI stdlib 단독·대시보드와 결합 금지 = ADR-009/원칙 2, 일치는 test_loop_strict_parity 가 강제), loop-status 없음 → ended(V1)+meta empty 승인(SQ-12 "없음=활성 루프 없음"과 일치, 에러 아님), resume `{}` 전용 승인(loop-cli §7 "resume 은 prev 값 유지" — 받을 이유 없음, 더 엄격한 방향), 디렉터리 미생성 → 500 승인(쓰기 경로 하나 유지, 원칙 2). R-01: 서브에이전트 Bash 에서 120/300/540 s 생존·재개 0.93 s → ADR-004 R-01 "완화(mitigated)" 로 표기 가능, 단 메인 세션·Windows 미검증 단서 필수 | (비차단) T-009: ADR-004 R-01 완화 표기+단서, 20 §5 F3 의 resume 본문 문구를 `{}` 전용으로·ControlView 실제 필드·"loop-status 없음 = ended+meta empty" 반영 (§5 기존 [architecture] 후보와 동일) |
| security | PASS | 실행: backend pytest 811 passed, pip-audit(requirements.txt, 의존성 diff 0줄) "No known vulnerabilities found". W-01/W-02: app/ 쓰기 호출은 control.py 의 mkstemp(dir=memory_dir, `.control.json.*.tmp`)→fsync→os.replace(상수 경로, 요청값 미사용)뿐, mkdir 0. scratch 실측(TestClient): seq=2^53−1·baseline=2^53−1 → 500 CONTROL_WRITE_FAILED 고정 문구 + 파일 불변/미생성, 락 점유 시 2.01 s 후 500, replace PermissionError 5회 → 500 + 원본 해시 불변 + tmp 0개, memory 디렉터리 없음 → 500 + 디렉터리 미생성, `.control.json` 이 외부 파일 심볼릭 링크면 링크만 교체(대상 불변), 깨진 제어 파일 내용·루트 경로가 GET 응답에 없음(partial+고정 경고), 로그는 예외 종류만. 실서버(`python -m app`, FASTAPI_OTEL_AUTO_CONFIGURE=true + OTEL_*_EXPORTER=otlp + 로컬 OTLP 수신기): `server:` 헤더 없음, CORS 헤더 없음(교차 출처 OPTIONS 405), OTLP 요청 0건, 정상 기동. 실서버 가드: Host evil 400 BAD_HOST, Origin 불일치·text/plain 403 FORBIDDEN_ORIGIN, pause 의 extra 필드·true·600.0·86401·5000자리 정수 422, resume `{"max_pause_sec":..}`·`[]`·NaN 422, `{}` 200(seq 연속). CLI(scratch 복사본, `python3 -I`): stdlib import 만, 1e0·true·23자리·2^53·NaN·배열 state·잘못된 시각·BOM·비 UTF-8·64 KiB 초과·깊은 중첩·디렉터리 → exit 2 CONTROL_BROKEN, loop-status 의 done>total·run_id 경로문자열·1.0·13월·추가 키 → NO_LOOP, 위조 인자(아라비아 숫자·0x10·모르는 옵션·중복) → 64; stdout/stderr 에 경로·파일 내용 없음, loop-status 심볼릭 링크는 링크 교체(대상 불변), tmp 잔여 0. | (비차단 권고) 요청 본문 크기 상한 없음 — 5 MB 본문이 422 까지 메모리로 읽힘. 루프백+Host/Origin/Content-Type 가드 뒤라 교차 출처로 도달 불가해 계약 위반 아님. resume `null` 본문은 생략과 같게 200 처리(무해). `.control.json` 이 FIFO 면 open 이 블록(동일 사용자만 가능) — 필요 시 향후 O_NONBLOCK/일반 파일 검사 검토 |
