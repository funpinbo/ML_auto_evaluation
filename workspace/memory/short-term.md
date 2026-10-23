---
status: active
task: T-005
team: backend
outcome: done
opened_at: 2026-10-23T17:38:08+00:00
---
# Short-term Memory

> **계층 4 (작업 단위).** Task 1개를 수행하는 동안의 작업 메모리. 한 번에 하나만 열린다.
> 수명: `status: active` 로 열고 → 작업 → `outcome` 기록 → `status: closed` 로 닫는다.
> 닫히는 순간 Hook 이 이 파일을 `archive/STM-xxxx_<task>.md` 로 옮기고 Long-term memory 갱신(cascade 1/3)을 요구한다.
> frontmatter 값: status(idle|active|closed) / outcome(done|partial|blocked)

## 1. 목표
- Task: T-005 [backend] API 앱 셸(앱 팩토리, 응답 envelope, 에러 포맷, Host/Origin 가드, dist 마운트, 설정 주입) + AI-DLC 상태 리더(읽기 전용) + GET /pipeline /plan /tasks /memory — FR-001, FR-002, FR-003 | deps: T-001, T-003, T-020, T-021, T-023, T-024, T-025
- 완료 조건(DoD): Host 가드는 자체 ASGI `HostGuardMiddleware`(D-18), `settings.port` 단일 출처(D-19), 비-JSON 403, 에러 코드 닫힌 집합(D-20) + privacy.md §5.1 H-01~H-22·§5.2 C-01~C-11 전 케이스 테스트(H-18 은 ASGI scope 직접 구성), ADR-011 §9~§12 테스트(에러 코드 9개 enum, `{"detail"}` 금지, 405+Allow·OPTIONS, `/api` 밖 404, websocket close 1008, 처리 순서 D-29), OpenAPI export(`workspace/project/contracts/openapi.json`) + `docs/api` 재생성, TestClient base_url 지정, 단위·API 테스트 통과, 조회 전후 workspace 해시 불변, `status` 서브프로세스 미사용 + user/02 §10 공통 DoD

## 2. 로드한 컨텍스트
- 관련 FR: FR-001(단계 판정 D-21), FR-002(Plan·Task), FR-003(메모리), 스토리 workspace/project/stories/FR-001~003.md
- ADR: ADR-001(단일 프로세스), ADR-006(의존성 fastapi 0.161.1·uvicorn 0.54.0·pydantic 2.14.1), ADR-009(memory_cascade 읽기 함수만, `status` 서브프로세스 금지), ADR-011 §2·§4·§5·§9~§12
- 보안 케이스: workspace/project/security/privacy.md §5.1 H-01~H-22, §5.2 C-01~C-11
- LTM: D-07, D-08, D-16, D-18, D-19, D-24~D-29, 패턴(TestClient base_url, Host 헤더 1개, Starlette 405 가로채기), I-21
- 테스트: qa fixture(monitor/backend/tests/fixtures/, conftest), 소유 경로 tests/{unit,api}/ (40 §1.1)

## 3. 작업 로그
<!-- 시간순으로 짧게. 무엇을 했고 무엇을 봤는지 -->
- 기준선: `cd monitor/backend && ../.venv/bin/python -m pytest -q` → 95 passed, ruff clean.
- `monitor/.venv` 에 fastapi==0.161.1, uvicorn==0.54.0, pydantic==2.14.1 + httpx 0.28.1, pytest-cov 7.1.0 설치. 전이 의존성에 starlette 1.9.0 과 **opentelemetry-api 1.45.1, annotated-doc 0.0.5**(fastapi 0.161 신규 요구)가 포함됨.
- Starlette 1.9 / FastAPI 0.161 소스 확인: FastAPI `APIRoute` 는 GET 에 HEAD 를 자동 추가하지 않음(순수 Starlette `Route` 는 추가), FastAPI 라우터도 FULL > PARTIAL 우선, `router.default` 로 미매치 처리 가능, `redirect_slashes` 기본 True(끝 슬래시 307).
- 앱 셸 구현: `MonitorApp.__call__` 이 가드 체인(Host → Origin/미디어 타입 → 보안 헤더 → ErrorShield)을 FastAPI 전체(텔레메트리·ServerErrorMiddleware 포함) 바깥에서 먼저 실행. 정적 dist 는 `router.default`(StaticFallback), `redirect_slashes=False`, docs/redoc/openapi 라우트 비활성.
- Hook 어댑터: `spec_from_file_location` 기본 로더가 `<AIDLC_ROOT>/aidlc/hooks/__pycache__/*.pyc` 를 **쓴다**는 것을 실측(임시 디렉터리) → `set_data` 를 무시하는 `_NoBytecodeLoader` 로 교체, Gate 서브프로세스에 `PYTHONDONTWRITEBYTECODE=1`.
- FR-001 AC-16: tasks.md 가 깨져도 STM active 로 5 를 판정할 수 있었으나 스토리 문구(4·5 = 확인 불가)에 맞춰 tasks 를 못 읽으면 5 도 unknown 으로 둠.
- 테스트 426건 추가(unit 7파일, api 9파일). 실제 서버 `AIDLC_MONITOR_PORT=18799 python -m app` 기동 후 curl: memory 200, Host evil 400 BAD_HOST, text/plain POST 403, localhost:18799/ 200.
- OpenAPI export → `workspace/project/contracts/openapi.json`, `python3 aidlc/scripts/openapi_docs.py render ... -o docs/api` → `docs/api/reference.md` 생성.
- `monitor/backend/requirements.txt` 작성(런타임 14개 `==`), 새 venv 에 설치 후 `pip freeze` 와 정확히 일치 확인.

## 4. 발견 사항 (LTM 후보)
- 결정:
  - 가드는 FastAPI 미들웨어 목록이 아니라 `FastAPI` 서브클래스의 `__call__` 에서 감싼다 — `add_middleware` 는 ServerErrorMiddleware 안쪽이고 FastAPI 0.161 네이티브 텔레메트리도 미들웨어 스택 바깥에서 돌아 "가장 바깥" 이 아니다 (T-005)
  - 정적 dist 는 `app.router.default` 에 둔다: `/api`·`/api/...` 는 메서드 무관 404, 그 밖은 파일 있으면 GET/HEAD 서빙·다른 메서드 405 `Allow: GET, HEAD`, 없으면 404(SPA 폴백 없음), dist 없으면 `/` 만 안내 HTML. `redirect_slashes=False` 로 끝 슬래시는 404 (T-005)
  - 기본 포트 8765, `AIDLC_MONITOR_PORT` 또는 `python -m app --port N`(우선)으로만 변경, 선행 0·0·범위 밖 거부. 호스트 옵션 없음 (ADR-001, D-19)
  - 패널 규칙: `meta.warnings` 가 하나라도 있으면 `partial`. 파일 없음은 값 `null` + 경고, 판정 파일 깨짐은 해당 값만 `null`/`unknown` (T-005)
  - Task 상태의 `## Blocked` 판정은 항목 줄의 **첫 T-ID** 만 본다(`- T-009 — blocker … T-004` 의 T-004 는 막힘 아님) (T-005)
  - FR-001 단계 1 의 "00 미작성 0개" 는 project Gate 출력의 `project/00-interpretation.md (N개 미작성)` 줄을 쓴다(플레이스홀더 규칙을 aidlc.py 와 단일 출처로 유지) (T-005)
- 패턴:
  - Hook 모듈을 importlib 로 읽을 때는 바이트코드를 쓰지 않는 로더를 쓴다 — 기본 `SourceFileLoader` 는 대상 저장소에 `__pycache__` 를 만든다(읽기 전용·W-01 위반). 해시 불변 테스트에 `rglob("__pycache__") == []` 를 함께 둔다 (T-005)
  - `aidlc.py check` 는 스크립트 위치(`parents[2]`)를 루트로 쓰므로 fixture 루트에 `aidlc/scripts/aidlc.py`·`aidlc/hooks/memory_cascade.py`·`aidlc/templates/{user,project,memory}` 를 복사해야 Gate·엔진이 fixture 를 본다(`tests/unit/backend_support.install_engine`) (T-005)
  - Host 0개·2개·빈 Host 는 httpx 로 못 만든다 → `backend_support.asgi_http(app, http_scope(...))` 로 원시 scope 를 넣는다(H-16~H-19) (T-005)
  - 아직 없는 대상 라우트(health·control·events)는 같은 경로의 대역 라우트를 뒤에 붙여 "가드 통과 → 핸들러 도달" 을 검증한다. 실제 라우트가 먼저 등록되면 대역은 가려진다 (T-005)
  - FastAPI 0.161 의 `app.routes` 는 포함된 라우터를 `_IncludedRouter` 로 감싸 `path` 가 없다 — 라우트 존재 확인은 요청으로 한다 (T-005)
  - ruff 0.17.2 기본 규칙에 B008(Depends 기본값)·SIM117·PLW1510·TRY004·UP012 가 걸린다 → `Annotated[..., Depends()]`, `check=False` 명시 (T-005)
- 이슈/리스크:
  - I-21 해소 근거: FastAPI 0.161.1 `APIRoute(GET)` 의 methods = {GET} → `HEAD /api/v1/pipeline` 405 `Allow: GET`(실측). 순수 Starlette `Route(GET)` 는 {GET, HEAD} → T-011 의 `/api/v1/events` 는 `APIRoute` 로 등록하거나 HEAD 405 를 테스트로 고정해야 함 (T-005)
  - fastapi 0.161.1 이 전이 의존성으로 `opentelemetry-api`(Apache-2.0)·`annotated-doc`(MIT) 를 끌어온다 — ADR-006 Context 의 전이 목록에 없음 (T-005)
  - Starlette 1.9 TestClient 가 `httpx` 사용 시 `StarletteDeprecationWarning`(“install httpx2”) 을 낸다 — ADR-006 dev 목록은 httpx (T-005)
  - privacy.md §5.2 C-01~C-03 "통과" 와 H-01~H-03 POST 대상은 지금 대역 핸들러 200 기준이다. T-008 실제 `/control/pause` 는 활성 루프가 없으면 409 이므로 기대값을 "400/403/415/422 아님" 으로 바꿔야 한다 (T-005)
- 교훈:
  - "읽기 전용" 은 파일 열기 모드만이 아니라 import 부수 효과(.pyc)까지 본다 — 실측(임시 디렉터리에서 기본 로더 실행) 으로 잡았다 (T-005)
  - 프레임워크 버전이 문서 작성 시점보다 새로우면(FastAPI 0.161 텔레메트리 래핑, APIRoute HEAD 미추가) 소스를 직접 읽고 테스트로 고정한다 — LTM 의 Starlette 함정 설명과 실제 동작이 달랐다 (T-005)

## 5. 새로 발견된 Task (Task 후보)
- [cicd] T-007: `monitor/backend/requirements.txt` 는 40 §1.1 상 cicd 소유인데 실행에 필요해 T-005 가 작성함(런타임 14개, `pip freeze` 재현 확인). 고정 정책 확정·`requirements-dev.txt`(pytest 9.1.1, pytest-cov 7.1.0, httpx 0.28.1(+httpcore 1.0.9, certifi 2026.10.23), coverage 7.17.0, ruff 0.17.2, jsonschema 계열) 작성, `.coverage` 무시 확인(이미 등록). pytest 설정 파일은 만들지 않음 — `tests/{unit,api}/conftest.py` 가 sys.path 를 보강하므로 `cd monitor/backend && python -m pytest` 와 저장소 루트 `python -m pytest monitor/backend/tests` 모두 동작
- [architecture] ADR-006 Context/Decision 1 의 전이 의존성 목록에 `opentelemetry-api`(Apache-2.0, fastapi 0.161 필수)·`annotated-doc`(MIT) 추가, dev 목록의 httpx vs Starlette 1.9 권고 `httpx2` 결정 — 02 §9 라이선스·1년 기준 확인
- [architecture] T-005 API 명세(openapi.json) 리뷰 — 봉투 모델 이름(`Envelope_PipelineData_` 등), 단계 상태 enum(`done|in_progress|waiting|unknown`), Gate 필드(`target_missing`, `no_documents`, `error_code`), `pending_cascade` enum(`none|ltm|tasks|plan|unknown`), operationId = 함수 이름
- [ops] T-006: `app/api/health.py` 는 `router = APIRouter()` 에 `@router.get("/health")` 로 두면 `create_app` 이 `/api/v1` 아래 자동 연결, `app/logging_config.py` 의 `setup_logging()` 은 `python -m app`·`app.main:app` 경로에서 자동 호출(없으면 basicConfig). 소스 상태는 `app.state.services`(pipeline/tasks/memory/gates) 로 접근 가능 — `source_status()`·`warmup.progress()` 는 T-010 과 함께 backend 가 제공 예정
- [backend] T-008: privacy.md §5.2·§5.1 POST 대상의 "통과" 기대를 실제 라우트에 맞게 "400/403/415/422 아님"(활성 루프 없음 = 409) 으로 조정, `.control.json` 해시 비교는 거부 케이스 유지
- [backend] T-011: `/api/v1/events` 출처 검사(경로 기준, 복수 헤더 403)는 `OriginGuardMiddleware` 에 이미 구현·테스트됨(`test_write_guard_cases.py`). T-011 은 라우트를 FastAPI `APIRoute` GET 으로 등록해 HEAD 405 를 유지하고(I-21), 슬롯 카운트·`/api/v1/%65vents`·끝 슬래시 우회 테스트만 추가
- [qa] `fixtures/workspace.py` 에 엔진 복사 옵션(또는 `engine_root` fixture) 추가 검토 — 지금은 backend 가 `install_engine()` 으로 Hook·aidlc.py·템플릿을 복사. fixture 루트에 엔진이 없으면 패널이 "AI-DLC 엔진을 찾을 수 없음" 이 된다
- [product] FR-001 R7 외 확인 질문: `## Blocked` 항목 줄의 T-ID 중 첫 번째만 막힘으로 보는 해석(FR-002 §2 "T-ID 가 항목 줄에 있음") 확인
- [architecture] T-005 리뷰 후속(비차단): ADR-006 Context/Decision 에 opentelemetry-api·annotated-doc 전이 의존성과 'FastAPI 0.161 네이티브 텔레메트리 = SDK·exporter 미설치·auto_configure 꺼짐 → 외부 전송 없음(QS-13)' 기록, httpx vs httpx2 결정(T-007 과 함께), ADR-009 Context 의 '모듈 import 자체는 부작용 없음' 을 '기본 로더는 __pycache__ 를 쓴다 → no-bytecode 로더 필수' 로 정정, ADR-011 §4 '가장 바깥 등록' 을 `MonitorApp.__call__` 감싸기로·§9 정적 서빙을 `router.default` + `redirect_slashes=False` 로 명시, 20 §4 디렉터리 트리(api/tasks.py 가 /plan 포함, services/memory·panel, app/errors·security·static_files)와 'StaticFiles(html=True)' 문구 갱신
- [backend] `create_app` 에서 FastAPI 텔레메트리를 명시적으로 끄는 것 검토(`telemetry={...}` 인자) — 사용자 환경변수 `FASTAPI_OTEL_AUTO_CONFIGURE`/`OTEL_*` 에 의한 동작 변화 차단, 테스트로 고정

## 6. 결과 & 인수인계
- 산출물(파일/PR):
  - 앱: `monitor/backend/app/{__init__,__main__,config,errors,security,static_files,main}.py`, `app/api/{deps,pipeline,tasks,memory}.py`, `app/models/{envelope,errors,pipeline,tasks,memory}.py`, `app/services/{aidlc_reader,gates,panel,pipeline,tasks,memory}.py` (ops 3파일 미작성, 훅만)
  - 스크립트: `monitor/backend/scripts/export_openapi.py` (`--check` 지원)
  - 테스트: `monitor/backend/tests/unit/{conftest,backend_support,test_config_settings,test_gate_service,test_task_line_parsing,test_stage_rules,test_hook_adapter,test_app_factory}.py`, `tests/api/{conftest,test_host_guard_cases,test_write_guard_cases,test_error_contract,test_static_dist,test_pipeline_api,test_plan_tasks_api,test_memory_api,test_readonly_guarantees,test_openapi_contract,test_panel_isolation}.py`
  - 계약·문서: `workspace/project/contracts/openapi.json`(export), `docs/api/reference.md`(재생성)
  - 의존성: `monitor/backend/requirements.txt` ([cicd] 후보 참조)
- 검증 결과 (2026-10-23 실행):
  - `cd monitor/backend && ../.venv/bin/python -m pytest --cov=app -q -p no:cacheprovider` → `521 passed, 1 warning in 19.87s` (기존 qa 95 + 신규 426), `TOTAL 1341 33 98%` (라인 커버리지 98% ≥ 70%). 경고 1건 = Starlette httpx 폐기 예고
  - 저장소 루트 `monitor/.venv/bin/python -m pytest monitor/backend/tests -q` → `521 passed`; `tests/scenarios` 단독 `95 passed`
  - `../.venv/bin/ruff format --check .` → `60 files already formatted`; `../.venv/bin/ruff check .` → `All checks passed!`
  - `python monitor/backend/scripts/export_openapi.py --check` → `openapi.json 최신`; `python3 aidlc/scripts/openapi_docs.py render workspace/project/contracts/openapi.json -o docs/api` → `created docs/api/reference.md`
  - `python3 -m unittest discover -s aidlc/tests` → `Ran 31 tests … OK`; `aidlc.py check project` / `check docs` → GATE PASS
  - 실제 서버: `AIDLC_MONITOR_PORT=18799 ../.venv/bin/python -m app` → `Uvicorn running on http://127.0.0.1:18799`, curl `GET /api/v1/memory` 200, `Host: evil.example` 400 BAD_HOST, `POST /api/v1/nope text/plain` 403 FORBIDDEN_ORIGIN, `http://localhost:18799/` 200(dist 없음 안내)
  - 새 venv 에 `pip install -r monitor/backend/requirements.txt` 후 `pip freeze` 가 파일과 정확히 일치
  - DoD 대응: H-01~H-22 × 4대상(원시 ASGI, H-18 포함)·C-01~C-11 × pause/resume·N-03, ADR-011 §9(9코드 enum·`detail` 0건·404/405+Allow·OPTIONS·`/api` 밖 404)·§10(websocket 1008·lifespan 통과)·§11(events 경로 기준 403, 복수 헤더)·§12(400→403→404/405→422 순서), FR-001 AC-1~17·FR-002 AC-1~16·FR-003 AC-1~14, 5종 workspace(closed_stm 포함) 해시 불변 + `__pycache__` 0, Hook 쓰기 함수 7종 raising fake, `status` 서브프로세스 0(spy)
  - 미실행: `run.bat`/`run.sh` 화면 확인(런처·dist 는 T-007·T-012 범위), pip-audit(D-01, 릴리스 전)
- 남은 일:
  - 리뷰 게이트: qa(필수), security(Host/Origin 가드·읽기 전용), architecture(openapi.json 신규 명세)
  - §5 후보 반영(cascade 2/3)

## 7. 리뷰 기록 (리뷰 게이트)
<!-- /aidlc-run 이 리뷰 게이트 대상 팀을 리뷰 모드로 호출하면 각 팀이 한 줄씩 추가 -->
| 팀 | 결과 | 근거 | 필요한 조치 |
|----|------|------|-------------|
| architecture | PASS | (1) openapi.json 3.1.0: 경로 4개(pipeline/plan/tasks/memory, 20 §5 M1 중 T-005 범위) 일치, `Envelope[T]={data,meta}` + Meta(status ok/partial/empty/error/warming, warnings, error=SourceError 또는 null, generated_at, source_mtime), ErrorResponse `{error:{code,message}}`, ErrorCode enum 9개 = ADR-011 §9 일치(415 없음), SourceErrorCode 6개 = 20 §5. 신규 명세라 하위 호환 문제 없음. `export_openapi.py --check` → 최신, `openapi_docs.py render` 재실행 결과 docs/api/reference.md 와 diff 0. (2) ADR-001: `create_app(settings)` 단일 앱·127.0.0.1·포트 단일 출처 OK. ADR-009: 허용 목록(read_doc·as_int·*_RE·Memory.exists/phases/archived/latest_seq/pending/load_state)만, `_NoBytecodeLoader`, Gate 실행기 `check` 외 서브커맨드 거부 + PYTHONDONTWRITEBYTECODE, `status` 호출 0 확인. ADR-011: 실측 HEAD /api/v1/pipeline 405 Allow GET, 끝 슬래시 404(redirect_slashes=False), OPTIONS 405, POST text/plain 403 → JSON POST 405 → 422 → 나쁜 Host 가 422 보다 먼저 400(§12 순서), /x.js 404(SPA 폴백 없음), nosniff 헤더. 가드를 `MonitorApp.__call__` 로 감싼 것은 §4 '가장 바깥' 의도(텔레메트리·ServerErrorMiddleware 보다 바깥)를 add_middleware 보다 더 잘 지키므로 수용 — ADR-011 §4/§12 문구 갱신 필요(비차단). router.default 정적 서빙은 §9 '405 가로채지 않음' 충족. ADR-006: opentelemetry-api 1.45.1(Apache-2.0)·annotated-doc 0.0.5(MIT)는 fastapi 0.161.1 필수 전이 의존성으로 Decision 1(전이는 pip freeze 로 == 고정) 범위 안 — 차단 아님. FastAPI 텔레메트리는 SDK/exporter 미설치·auto_configure 기본 False 라 외부 전송 없음(QS-13). httpx→httpx2 는 dev 전용 폐기 경고뿐이라 비차단, T-007 에서 결정. (3) 변경 파일은 backend 소유(app/**, tests/unit·api, scripts)+export 계약/레퍼런스뿐, ops 3파일(logging_config·api/health·models/health)·qa fixture 미변경, requirements.txt(cicd 소유)는 §5 [cicd] 로 인계됨. 20 §4 대비 api/plan 이 api/tasks.py 에 합쳐짐, services/memory·panel, app/errors·security·static_files 추가 — 경계 위반 아님, 20 §4 트리 갱신 대상. (4) I-21 해소 근거 §4 기록, T-011 APIRoute 지시 §5 기록. pytest 521 passed(1 warning=httpx 폐기) 재실행 확인 | 비차단: [architecture] ADR-006 전이 목록·텔레메트리·httpx 결정, ADR-009 'import 부작용 없음' 정정(.pyc), ADR-011 §4 구현 문구(MonitorApp.__call__)·§9 정적 서빙(router.default), 20 §4 트리/StaticFiles(html=True) 문구 갱신 / [backend] FastAPI(telemetry=...) 로 텔레메트리 명시 비활성 검토 |
| security | PASS | pytest 521 passed(재실행). 코드: `MonitorApp.__call__` → HostGuard(최외곽, scope headers 개수 1·frozenset 정확 일치, port=settings.port) → OriginGuard(비안전 메서드 Content-Type 1개·미디어 타입 정확 일치, Origin 있으면 정확 일치, events 경로 기준) → 보안헤더 → ErrorShield(로그는 예외 종류만). grep: TrustedHostMiddleware·415·CORS·0.0.0.0·shell=True 0건, host/content-type 비교에 startswith/in-문자열 없음, 쓰기 API(open w/write_text/os.replace/mkdir 등) 0건. BIND_HOST 상수·호스트 옵션 0, 포트 0·선행 0 거부, 경로는 env 만. 에러 9코드 고정 문구(요청 값 미포함). static: `..`·숨김·`\`·NUL·`:` 세그먼트 거부 + resolve 후 dist 하위 확인(symlink 이탈 테스트 있음). Gate 서브프로세스 `[sys.executable, aidlc.py, check, layer]` 고정·timeout 10s·shell 없음·layer 화이트리스트, Hook 로더 .pyc 미기록. 실서버 probe(127.0.0.1:18831): Host evil/HTTP1.0 무Host/X-Forwarded-Host → 400 BAD_HOST, absolute-form(evil 권한부+정상 Host) → 404, 중복 Host 2종 → h11 이 400 으로 거부, `..`/`%2e%2e`/`%2f`/`%5c`/`%00` → 404, POST text/plain·Content-Type 중복·evil Origin → 403, OPTIONS·타 Origin → 405 + CORS 헤더 없음, 422 에 입력 원문 없음, 서버 로그에 경로·값 없음, 서버 종료 후 git status 깨끗·aidlc/hooks/__pycache__ mtime 불변. pip-audit -r requirements.txt(스크래치 venv) → No known vulnerabilities. npm audit 은 frontend 변경 없어 미실행 | 차단 조치 없음. 권고: (1) uvicorn `server_header=False` 로 `server: uvicorn` 노출 제거(저위험), (2) 중복 Host 는 h11 평문 400(보안 헤더·봉투 없음) — 거부는 되므로 수용, (3) opentelemetry-api·annotated-doc 전이 의존성은 §5 [architecture] ADR-006 갱신 후보로 D-04 마무리 |
