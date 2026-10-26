---
doc: test-strategy
layer: project
owner: qa
sources: [user/02 §5·§10, 20 §2 QS-01~QS-11, 40 §1.1, qa charter, security/privacy.md §1~§7, contracts/README §2·§3, ADR-002, ADR-004, ADR-006, ADR-009, ADR-011, LTM D-02·D-07·D-13]
status: draft
---
# AI-DLC Monitor 테스트 전략

이 문서는 qa 가 Monitor 의 테스트 범위·소유·fixture·실행 방법을 정한 기준이다. 상위 규칙은 user/02 §5(테스트 표준)·§10(공통 DoD)이고, 보안 통과 기준은 `workspace/project/security/privacy.md`(체크리스트 ID P-/N-/W-/D-/T-)가 정의한다. 이 문서는 그 ID 를 **참조만** 한다.

## 1. 원칙
1. **실제 `~/.claude` 를 쓰지 않는다** (02 §5, CON-06, privacy.md P-30). 모든 입력은 `tmp_path` 에 만든 합성 workspace·합성 CLAUDE_HOME 이다. `conftest.py` 가 3겹으로 막는다: (a) `pytest_configure` 에서 세션 임시 홈으로 `HOME`/`USERPROFILE` 을 바꾸고 `AIDLC_ROOT`/`CLAUDE_HOME`/`CLAUDE_CONFIG_DIR`/`XDG_CONFIG_HOME` 을 지운다(session·module fixture·수집 시점 import 포함), (b) autouse `_isolate_home` 이 테스트마다 같은 치환을 반복한다, (c) `fixtures/home_guard.py` 의 `sys.addaudithook` 가드가 시작 시 기록한 실제 홈(환경 변수 + `pwd`) 아래 `open`/`os.listdir`/`os.scandir` 를 시스템 호출 전에 막고 기록한다(테스트가 예외를 삼켜도 `_home_guard_check` 가 실패시킴). 저장소·`sys.prefix`·`sys.path`·임시 디렉터리는 허용 목록이고, 실제 홈 자체·그 조상·`~/.claude` 류 민감 경로는 허용 목록에 넣을 수 없다. 감사 hook 은 제거할 수 없으므로 `enabled` 플래그로 끄고 켜며, 음성 테스트는 `home_guard.expect()` 블록 안에서 접근을 시도한다(`scenarios/test_home_guard.py`). 앱에 경로를 주는 방법은 환경 변수 주입(`app_env`)뿐이다.
2. **결정적이다.** 생성기는 seed 고정(`DEFAULT_SEED = 20261023`), 시각은 `FIXED_NOW = 2026-10-23T09:00:00Z` 기준. 같은 인자 → 같은 바이트. 시계·난수·네트워크 의존 테스트는 만들지 않는다.
3. **기대값은 생성기가 함께 계산하고, 독립 구현으로 교차 검증한다.** `JsonlManifest.expected_buckets`(생성기)와 `reference_parser.aggregate`(파일을 다시 읽는 오라클)가 같아야 하며, 앱 수집기는 둘과 비교한다.
4. **음성 케이스도 실제로 실행한다.** 계약 스키마는 examples 뿐 아니라 위반 입력까지 jsonschema 로 돌린다(LTM 패턴: `format` 비강제, `$` 끝 개행).
5. **skip/삭제로 통과시키지 않는다.** 환경상 불가능한 케이스(예: symlink 권한 없는 Windows)만 사유를 적고 `pytest.skip` 한다.
6. 실행하지 않은 검증은 통과로 기록하지 않는다.

## 2. 테스트 피라미드
| 층 | 대상 | 도구 | 위치 | 작성 팀 | 비중(목표) |
|----|------|------|------|---------|-----------|
| 단위 | services(상태 리더, 수집기, 프라이버시 필터, 루프 CLI 함수), models | pytest | `monitor/backend/tests/unit/` | backend | 많음 (커버리지 대부분) |
| 단위 | health·logging_config | pytest | `monitor/backend/tests/ops/` | ops | 적음 |
| 단위 | Vue 컴포넌트·composable | vitest + @vue/test-utils + jsdom | `monitor/frontend/src/**/*.spec.ts` | frontend | 중간 |
| API | REST 라우터·envelope·에러 포맷·Host/Origin 가드 (FastAPI TestClient) | pytest + httpx | `monitor/backend/tests/api/` | backend | 중간 |
| 시나리오/통합 | 가드레일(500 0건, 본문 0건, 해시 불변), FR-005 일시정지/재개 E2E, Hook 규칙 대조, fixture smoke | pytest | `monitor/backend/tests/scenarios/` | **qa** | 적음, 고가치 |
| 프론트 통합 | fixture API 응답으로 대시보드 전체 렌더 (패널 empty/error/warming) | vitest | `monitor/frontend/tests/` | **qa** | 적음 |
| 성능 | Task 100 + 30일 JSONL 첫 화면, 증분 처리 | pytest (marker `perf`) | `monitor/backend/tests/perf/` | **qa** | 소수, 수동/게이트 선택 |
| 수동 | `run.sh`/`run.bat` 실행 화면 확인(02 §10), UAT | 사람 | `workspace/project/uat/` | product | - |

## 3. 소유 경계 (40 §1.1, qa charter §2)
| 경로 | 소유 | qa 의 역할 |
|------|------|-----------|
| `monitor/backend/tests/conftest.py`, `tests/fixtures/`, `tests/scenarios/`, `tests/perf/` | qa | 작성·유지 |
| `monitor/frontend/tests/` | qa | 작성·유지 |
| `workspace/project/qa/` (이 문서, `test-cases/FR-xxx.md`, Phase 품질 리포트) | qa | 작성 |
| `monitor/backend/tests/unit/`, `tests/api/` | backend | 리뷰만 |
| `monitor/backend/tests/ops/` | ops | 리뷰만 |
| `monitor/frontend/src/**/*.spec.ts` | frontend | 리뷰만 |
| `requirements-dev.txt`, `package.json`, 로컬 게이트 | cicd | 명령·기준 제공(§7·§8) |

- 개발 팀은 qa fixture 를 **읽기만** 한다. 새 fixture·변형이 필요하면 STM §5 에 `[qa]` 후보로 남긴다.
- `tests/` 에는 `__init__.py` 를 두지 않는다. pytest 기본 import 모드가 `tests/` 를 `sys.path` 에 넣으므로 `from fixtures... import ...` 로 가져오며, `conftest.py` 가 `--import-mode=importlib` 에서도 경로를 보강한다. 테스트 **파일 이름은 디렉터리가 달라도 겹치지 않게** 짓는다(rootdir 기준 basename 충돌 방지).
- 결함은 qa 가 고치지 않는다. 재현 절차와 함께 담당 팀 Task 후보로 STM §5 에 남긴다.

## 4. 시나리오 목록 (T-013 에서 구현, 위치 `tests/scenarios/`·`tests/perf/`)
각 시나리오는 아래 fixture(§6)만 사용한다. "기준" 열은 통과 조건이다.

| ID | 시나리오 | 입력 fixture | 기준 | 근거 |
|----|----------|--------------|------|------|
| S-01 | 깨진 입력에서 500 0건 | `broken_workspace`, `write_claude_status(..., "broken")`, JSONL edge case(깨진 줄·UTF-8 아님·잘린 꼬리·`message.usage` 비-dict) | 모든 GET 엔드포인트 전수 호출에서 HTTP 500 = 0, 해당 패널만 `meta.status = error`, 프로세스 생존. WARN 로그에 줄 내용 없음(T-08) | NFR-002, QS-03 |
| S-02 | 빈/일부 workspace | `empty_workspace`, `partial_workspace` | 500 = 0, 패널 `meta.status = empty`(없는 파일) | NFR-002, QS-03 |
| S-03 | 데이터 소스 부재 3종 | 스냅샷 `none`, `no_rate_limits`, `claude_home_factory(root, with_jsonl=False)` | 500 = 0, 사용량 패널 "한도 정보 없음"/토큰만/디렉터리 없음 안내 100% | NFR-002, QS-04 |
| S-04 | 오래된 스냅샷 | 스냅샷 `stale` | `captured_at` 경과 표시(SNAPSHOT_STALE 류) | QS-04 |
| S-05 | 본문 비노출 (응답) | `app_env` + `claude_home.forbidden_strings()` | 모든 REST 응답 본문·헤더, SSE 프레임에서 `assert_no_markers(..., extra=forbidden_strings)` 통과 | NFR-003, QS-06, privacy T-01·P-09 |
| S-06 | 본문 비노출 (로그) | S-05 와 같음 + `caplog`/`capsys` | 캡처 로그(WARN 포함)에 표식·경로·dir_name 0회 | T-02·P-10 |
| S-07 | 본문 비노출 (메모리 집계) | `claude_home` | 집계 구조를 재귀 순회해 표식 0회, 문자열 값은 모델명·warnings 뿐. 거짓 양성 토큰 `FALSE_POSITIVE_TOKENS=777777`·symlink 이탈 토큰 `424242` 가 합계에 섞이지 않음 | T-03·P-03·P-11 |
| S-08 | 사전 필터·content 비접근 | `claude_home` + `json.loads` spy / content trap | usage 없는 줄에서 `json.loads` 0회, `message.content` 접근 0 | T-05·T-06·P-06 |
| S-09 | `transcript_dir_name` 재검증 + symlink 이탈 | `runtime_files.INVALID_DIR_NAMES`/`VALID_DIR_NAMES`, `symlink_escape` | 음성 이름 전부 거부 → 폴백, symlink 디렉터리·파일·하위 디렉터리 링크를 열지 않음, 실패 로그에 값 없음 | T-07·P-25~P-29, D-13 |
| S-10 | 읽기 전용 (해시 불변) | **`closed_stm_workspace`**, `full_workspace`, `broken_workspace` | 모든 조회 API·SSE 반복 호출 전후 `hash_tree(root)` 동일. `diff_manifests` 로 새 파일 0 (POST control 시나리오에서만 `workspace/memory/.control.json` 추가 허용). **ADR-009 Decision 2**: `memory_cascade` 의 쓰기 함수 `write_doc`, `reset_stm`, `archive_stm_if_closed`, `snapshot_stm`, `save_state`, `handle`, `main` 을 호출 즉시 예외를 던지는 가짜로 바꾼(monkeypatch) 상태에서 모든 조회 API·SSE 를 호출해 전부 성공해야 한다 | CON-03, QS-07, T-04·W-01·W-03 |
| S-11 | Hook 규칙 대조 | `full_workspace`, `closed_stm_workspace`, 변형 tasks(rev/synced 불일치) | API 의 pending cascade·Phase 집계가 `memory_cascade.Memory` 판정과 같은 결론. `aidlc.py status` 는 **복사본 workspace 에서만** 실행해 비교(D-07: closed STM 을 아카이브하는 부작용). 비교 중에도 S-10 과 같은 ADR-009 Decision 2 가짜 쓰기 함수(`write_doc`…`main` 7종 예외)를 건 채 API 결론을 구한다 | FR-003, QS-09 |
| S-12 | 일시정지/재개 E2E | `runtime_files.LOOP_SCENARIOS`, `control_doc`, `app_env` | POST pause → `.control.json` 스키마 통과 → CLI `wait-resume` exit 10(대기) → POST resume → exit 0, 남은 반복 진행. `pause_over_limit` → exit 20(STM 무변경), `heartbeat_expired` → "세션 없음" 표시, `.control.json` 깨짐 → exit 2. exit 64(인자 오류)·1(예기치 못한 오류)·`NO_LOOP` 응답(D-09 exit 계약, ADR-004 루프 제어, ADR-011 에러 코드)은 이 E2E 범위가 아니라 **backend T-008 단위 테스트** 범위다(qa 는 리뷰로 확인) | FR-005, QS-11, D-09~D-11 |
| S-13 | Host/Origin 가드 회귀 | `app_env` | privacy N-02~N-06 표의 케이스 전수 (단위 테스트는 backend `tests/api/`, qa 는 회귀 묶음만) | QS-05 |
| P-01 | 첫 화면 성능 | `workspace_100_tasks` + 30일 JSONL(§5) | 접속 → 모든 Must 패널 REST 응답(값 또는 warming) ≤ 2초, 패널 응답 p95 ≤ 200 ms | NFR-001, QS-01 |
| P-02 | 증분 처리 | P-01 + JSONL 1 MB 추가 | 증분 처리 ≤ 10 ms(기준 PC), 변경 반영 ≤ 5초 | QS-02 |

FR 별 수용 기준 → 테스트 ID 추적은 product 스토리(T-004) 확정 후 `workspace/project/qa/test-cases/FR-xxx.md` 로 만든다.

## 5. 성능 fixture 와 측정 절차
- 크기 조절: `write_project_jsonl(project_dir, responses_per_day=..., body_pad=...)`. `body_pad` 는 줄마다 붙이는 본문 채움 바이트다(본문 표식은 유지).
- 실측(2026-10-23, 이 저장소 venv, Python 3.13): 기본값(12/일, pad 0) 1.6 MB·52 파일·1,684 줄·0.03 s / `responses_per_day=300, body_pad=3000` 129.4 MB·33,891 줄·1.09 s / `300, 8000` 298.9 MB·2.04 s. 크기는 pad 에 대략 선형 → **하한 329 MB 는 `300, 9000`, 상한 658 MB 는 `300, 18000` 근처**(추정치, perf 테스트가 `manifest.bytes_written` 을 기록해 확인).
- perf 테스트는 `@pytest.mark.perf` 로 표시한다. marker 는 `conftest.py` 가 등록하고, `-m` 식에 perf 가 없으면 수집 단계에서 제외한다(`check.py` 게이트 영향 없음). 켜기: `pytest monitor/backend/tests/perf -m perf -s`, 전체와 함께: `-m "perf or not perf"`. 측정값은 Phase 품질 리포트에 기록한다(charter §7 "NFR 측정값 기록").
- 생성은 `tmp_path_factory` 의 session 범위로 1회만 하고, 측정 대상은 서버 기동 후 첫 요청부터 모든 Must 패널 응답까지의 벽시계 시간이다.

- **실측 (T-013, 2026-10-25, Linux, Python 3.13, 페이지 캐시 따뜻함)**: `300, 9000` = 332.8 MB·33,891 줄·52 파일·생성 2.9 s (추정 329 MB 와 1% 차이) / `300, 18000` = 637.8 MB·생성 5.3 s (추정 658 MB 와 3% 차이). 줄 수는 pad 와 무관. 이 크기에서 서버 프로세스 시작→health 0.6 s, Must 패널 8개 동시 요청 전부 응답 0.3 s(사용량은 warming 부분값), 데우기 완료 약 1 s, REST p95 ≤ 7 ms, 변경→SSE 0.5 s. 콜드 캐시·느린 디스크 측정은 하지 않았다.

## 6. Fixture 카탈로그와 사용 규칙
모듈은 `monitor/backend/tests/fixtures/`, pytest fixture 는 `tests/conftest.py`.

### 6.1 pytest fixture (`conftest.py`)
| fixture | 제공 |
|---------|------|
| `_isolate_home` (autouse) | `HOME`/`USERPROFILE` → 임시 경로, `AIDLC_ROOT`/`CLAUDE_HOME`/`CLAUDE_CONFIG_DIR`/`XDG_CONFIG_HOME` 삭제 |
| `_home_guard_check` (autouse) / `home_guard` / `session_home` | 감사 hook 가드 위반이 있으면 테스트 실패 / 가드 객체(`expect()`, `disabled()`, `take()`) / `pytest_configure` 가 만든 세션 임시 홈 |
| `fixed_now` | `FIXED_NOW` |
| `workspace_factory(kind, task_count=12, name=None)` | 매번 새 디렉터리에 workspace 생성 |
| `empty_workspace` / `partial_workspace` / `full_workspace` / `broken_workspace` / `closed_stm_workspace` | 종류별 workspace (§6.2) |
| `workspace_100_tasks` | Task 100개 full workspace (NFR-001) |
| `claude_home_factory(workspace_root, **options)` | 합성 CLAUDE_HOME (`write_project_jsonl` 옵션 전달, `with_jsonl`, `with_decoys`) |
| `claude_home` | `full_workspace` 에 대응하는 30일 JSONL + edge case + decoy |
| `symlink_escape` | CLAUDE_HOME 밖을 가리키는 symlink 3종(디렉터리·파일·하위 디렉터리) + CLAUDE_HOME 안 decoy 를 가리키는 상대 링크 `projects/<enc>/creds-link.jsonl -> ../../.credentials.json`(프로젝트 디렉터리 기준으로 막아야 함, P-28·P-30). 만들 수 없는 환경이면 skip |
| `app_env` | full workspace + 정상 스냅샷(`transcript_dir_name` = 합성 dir_name) + CLAUDE_HOME 을 환경 변수로 주입. `AppEnv.env` 로 앱 팩토리 설정에도 쓸 수 있음 |

### 6.2 가짜 workspace (`fixtures/workspace.py`, AIDLC_ROOT 로 주입)
| kind | 내용 | 쓰는 시나리오 |
|------|------|--------------|
| `empty` | `workspace/` 만 있음 | S-02 |
| `partial` | idle STM + tasks.md(최대 5개)만 | S-02 |
| `full` | 4계층 메모리(active STM, LTM rev 3, tasks synced 3, plan), archive 2건, user/project/teams/aidlc 최소 문서. Hook 판정상 pending cascade 없음, P1 60%/P2 40%, P1 앞 절반 완료 | 기본, S-05~S-11 |
| `broken` | 미종결 frontmatter STM, 숫자 아닌 LTM rev, UTF-8 아닌 꼬리의 tasks.md, 빈 plan, 잘못된 archive 이름·바이너리 archive, 잘린 `loop-status.json`, 객체가 아닌 `.control.json` | S-01, S-10 |
| `closed_stm` | full 과 같되 STM `status: closed`, outcome done, 아직 아카이브 안 됨. Hook/`aidlc.py status` 가 건드리면 파일이 바뀌는 상태 | **S-10 필수**, S-11 |

`WorkspaceInfo` 는 `memory`, `monitor_dir`, `control_file`, `loop_status_file`, `claude_status_file` 경로를 제공한다. fixture 문서에는 표식 문자열을 넣지 않는다(표식은 Claude 기록 쪽에만).

### 6.3 가짜 JSONL 생성기 (`fixtures/jsonl_gen.py`, 30 EDA `bench_synthetic.py` 이식)
- 하루 1세션 파일(30일), `subagent_every` 일마다 `<세션>/subagents/agent-*.jsonl`(isSidechain true).
- EDA 특성 재현: requestId 중복(응답 1개 최대 7줄, `duplicate_ratio=0.45`), `"usage":` 키는 있으나 `message.usage` 없는 줄(약 1/8), 본문에 `"usage":` 문구(직렬화 시 이스케이프), 한 줄 약 236 KB 거대 줄, timestamp UTC `Z`, 파일 mtime = 마지막 줄 시각.
- edge case(`edge_cases=True`): usage 없는 줄, 빈 줄, `message.usage` 가 문자열, 깨진 JSON 2종(잘린 객체, UTF-8 아님), requestId 없는 응답, 같은 requestId 값 다른 2응답(last-wins), 잘린 마지막 줄 파일, mtime 40일 전 만료 파일(기대값 제외).
- `JsonlManifest`: `files`, `expired_files`, `truncated_files`, 줄 분류 `counts`, `bytes_written`, `expected_buckets`(키 `(UTC 시각 'YYYY-MM-DDTHH:00:00Z', 모델, isSidechain)` → `UsageTotals`), `expected_totals`, `unique_responses`.

### 6.4 본문 표식 (`fixtures/markers.py`, privacy.md §7)
- 12종 고유 표식(`ALL_MARKERS`): 본문, 도구 입출력, 본문 속 경로, `cwd`, sessionId, uuid/parentUuid, requestId, 허용 목록 밖 임의 키, `transcript_dir_name`, settings.json statusLine 명령, decoy 자격 증명, symlink 이탈 파일. 영숫자만 사용(경로 인코딩 `[^A-Za-z0-9] → -` 에도 보존).
- `assert_no_markers(*texts, extra=..., where=...)` — 실패 메시지에는 라벨(`BODY` 등)과 `extra[i]` 인덱스만 적는다. 표식 값·extra 값(경로·dir_name)·주변 내용은 적지 않는다. `ClaudeHome.forbidden_strings()` 를 `extra` 로 넘기면 dir_name·CLAUDE_HOME 경로·프로젝트 경로까지 검사한다.

### 6.5 합성 CLAUDE_HOME (`fixtures/claude_home.py`)
- `<tmp>/claude_home/projects/<enc>/` (enc = workspace 루트 인코딩 + `-<DIR_NAME 표식>`), `settings.json`(statusLine + 읽으면 안 되는 `env` 키), decoy `.credentials.json`·`history.jsonl`(열리면 표식으로 드러남, P-21·P-30).
- `with_jsonl=False` → 프로젝트 디렉터리 없음(QS-04). `encode_project_path()` 는 Claude Code 인코딩(D-13).
- `add_symlink_escapes()` → `EscapeCase`(P-28·P-29).

### 6.6 런타임 파일 (`fixtures/runtime_files.py`, contracts 스키마 통과)
- `.control.json`: `control_doc(state, seq, max_pause_sec=7200)`.
- `loop-status.json`: `loop_status_doc(scenario)` — `running`, `paused`(30분째), `resumed`, `pause_over_limit`(2시간+60초), `pause_timeout`, `done`, `heartbeat_expired`(120+60초).
- `claude-status.json`: `write_claude_status(path, kind)` — `normal`, `no_rate_limits`, `none`(파일 없음), `stale`(30분 전), `broken`(잘린 JSON). `session_hash` 는 sha256 앞 12자(ADR-003).
- `VALID_DIR_NAMES` / `INVALID_DIR_NAMES` — privacy P-26 음성 케이스 전부(끝 개행·NUL·256자 포함).

### 6.7 해시 (`fixtures/hashing.py`)
- `tree_manifest(root, exclude=())` → `상대경로 → 지문`(파일 sha256, symlink 대상, 빈 디렉터리 포함). `hash_tree()` 단일 sha256, `diff_manifests()` → added/removed/changed.
- 조회 전 `before = tree_manifest(ws.root)` → 호출 → `assert not diff_manifests(before, tree_manifest(ws.root))`. 런타임 디렉터리 제외는 그 쓰기가 허용된 시나리오에서만 명시적으로.

### 6.8 계약·오라클
- `fixtures/contracts.py`: `schema_errors(instance, name)` / `is_valid()` — `control`, `loop-status`, `claude-status` 를 Draft 2020-12 로 검증(`format` 비강제, pattern 으로 강제). 오류 메시지는 입력 값을 담을 수 있으므로 로그에 쓰지 않는다.
- `fixtures/reference_parser.py`: ADR-002 규칙의 최소 독립 구현(사전 필터 → loads → `message.usage` dict 확인 → requestId last-wins → UTC 시간 버킷, symlink·만료 파일 제외). **앱 코드가 아니며** 앱에서 import 하지 않는다.

### 6.8a 시나리오 도우미 (T-013)
- `fixtures/engine.py`: `install_engine(root)` — Hook·`aidlc.py`·`loop_control.py`·템플릿을 workspace 로 복사(루프 CLI 는 자기 위치로 저장소 루트를 계산하므로 복사본으로 실행한다).
- `fixtures/live_server.py`: `live_server(root, claude_home, work_dir)` — `python -m app` 을 임시 포트·127.0.0.1·환경 변수 경로로 기동, 로그 파일 수집, `sse_frames()`.
- `fixtures/endpoints.py`: GET 엔드포인트 전수 목록(`MUST_PANELS`, `ALL_GETS`). 새 라우트가 생기면 `test_endpoint_list_covers_app_routes` 가 실패한다.
- `scenarios/guardrail_support.py`: 인프로세스 클라이언트, workspace 5종 × 소스 변형 7종.

구현된 시나리오(T-013 축소판, D-51): S-01~S-03 `test_guardrail_no_500.py`, S-05~S-07 `test_no_body_exposure.py`, S-10 `test_readonly_hash.py`, S-12 `test_pause_resume_e2e.py`, P-01·P-02 `perf/test_first_screen_perf.py`. 나머지(S-04, S-08, S-09, S-11, S-13 대조 보강 등)는 Backlog T-032.

### 6.9 사용 규칙
- fixture 가 만든 파일은 테스트 안에서 바꿔도 되지만(그 테스트 전용 `tmp_path`), 모듈 상수·생성 규칙은 바꾸지 않는다. 변형이 필요하면 생성기 인자로 하고, 없는 인자는 `[qa]` 후보로 요청한다.
- 실제 저장소의 `workspace/` 를 AIDLC_ROOT 로 쓰지 않는다(해시 불변 검증·cascade 부작용).
- 표식 문자열을 앱 코드·로그 메시지에 상수로 넣지 않는다(검사 무력화).

## 7. 실행 방법
환경: `monitor/.venv`(gitignore). 전역 설치 금지(02 §11). dev 패키지 고정은 cicd(T-007)의 `requirements-dev.txt`.

```bash
# backend 전체 (저장소 루트 또는 monitor/backend 에서)
cd monitor/backend && ../.venv/bin/python -m pytest -q
# 커버리지 (pytest-cov 필요, 라인 ≥ 70%)
cd monitor/backend && ../.venv/bin/python -m pytest --cov=app --cov-report=term-missing
# 시나리오만 / 성능 제외
../.venv/bin/python -m pytest tests/scenarios -q
../.venv/bin/python -m pytest -m "not perf"
# 린트 (02 §2)
monitor/.venv/bin/ruff check monitor/backend && monitor/.venv/bin/ruff format --check monitor/backend
# frontend
cd monitor/frontend && npm test && npm run build
```
Windows: `monitor\.venv\Scripts\python -m pytest`.

현재 사용 중인 dev 패키지(2026-10-23 venv): pytest 9.1.1, jsonschema 4.26.0(+ referencing, jsonschema-specifications, rpds-py, attrs), ruff 0.17.2. 미설치: pytest-cov, httpx, fastapi(백엔드 앱 코드 생성 T-005 이후 필요). jsonschema 는 ADR-006 의 dev 의존성 목록에 아직 없다 → ADR 갱신 필요(T-008 DoD 와 같은 조건).

## 8. 게이트·커버리지 기준 (cicd 에 제공)
| 게이트 | 기준 | 시점 |
|--------|------|------|
| backend 테스트 | `python -m pytest` 전체 통과(skip 은 사유 있는 환경 skip 만) | 모든 코드 변경 Task |
| backend 커버리지 | `--cov=app` 라인 ≥ 70% (02 §5, QS-09) | `app/` 가 생긴 뒤(T-005~) 모든 backend Task, T-013 최종 |
| 린트 | `ruff check` + `ruff format --check` 0 오류 | 모든 Python 변경 |
| frontend | `npm test`, `vue-tsc`, `npm run build` 통과 + dist 신선도 | frontend 변경 Task |
| 가드레일 | S-01~S-03, S-05~S-10 통과 | T-013 이후 회귀 스위트 |
| 성능 | P-01 ≤ 2초 측정값 기록 | T-013, Phase 품질 리포트 |

## 9. privacy.md / contracts 추적
| 기준 | 제공 fixture | 시나리오 |
|------|--------------|----------|
| privacy §7 합성 fixture 규칙(표식: 본문·경로·cwd·sessionId·uuid·도구·임의 키, 본문 속 `"usage":`) | markers, jsonl_gen | S-05~S-08 |
| §7 케이스: usage 없음, 중복 requestId, requestId 없음, 깨진 JSON, 잘린 꼬리, subagents, symlink 이탈, 거대 줄 | jsonl_gen edge case, `symlink_escape` | S-01, S-07, S-09 |
| T-01·T-02·T-03 | `assert_no_markers` + `forbidden_strings()` | S-05·S-06·S-07 |
| T-04·W-01·W-03 | hashing | S-10 |
| T-05·T-06·P-06 | `claude_home` (+ 테스트 측 spy) | S-08 |
| T-07·P-25~P-29, contracts/README §3 | `INVALID_DIR_NAMES`, `symlink_escape`, `claude_status_doc(transcript_dir_name=...)` | S-09 |
| T-08·P-07 | 깨진 줄·잘린 꼬리(표식 포함) | S-01, S-06 |
| P-21·P-23·P-30 | decoy 자격 증명·history, settings.json `env` 키 | S-05·S-06 |
| P-31 | `claude-status` 스키마(`additionalProperties: false`) 음성 케이스 | smoke(이미 존재) |
| contracts §2 런타임 파일 3종 | runtime_files + contracts 검증 | S-12, smoke |
| N-02~N-06 | `app_env` | S-13 (단위는 backend) |

## 10. 미결·리스크
- perf 크기(§5)는 선형 추정. T-013 에서 실측 크기와 시간을 기록해 보정한다.
- 커버리지는 `app/` 코드와 pytest-cov 가 생긴 뒤에만 측정 가능하다(현재 미측정).
- `aidlc.py status` 대조(S-11)는 부작용 때문에 반드시 복사본에서 실행한다. 출력 형식이 바뀌면 대조 기준을 Hook 함수 결론으로 우선한다.
- symlink 시나리오는 symlink 권한이 없는 Windows 에서 skip 된다 → Linux/macOS 실행 결과를 근거로 기록한다.
