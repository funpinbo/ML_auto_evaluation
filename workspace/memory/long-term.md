---
rev: 9
last_merged_stm: 9
---
# Long-term Memory

> **계층 3.** 프로젝트 전체에서 재사용할 지식. STM 이 끝날 때마다(cascade 1/3) 정제되어 쌓인다.
> 규칙: 사실만 기록, 출처 STM 번호 표기(예: `(STM-0003)`), 중복 금지, 틀린 항목은 삭제하지 말고 ~~취소선~~ + 대체 항목 링크.
> 이 파일이 갱신되면(rev 증가) Hook 이 Task 갱신(cascade 2/3)을 요구한다.

## 1. 결정 사항 (Decisions)
| ID | 결정 | 근거 | 대안 | 출처 |
|----|------|------|------|------|
| D-01 | 단일 FastAPI 프로세스(127.0.0.1)가 /api/v1 REST·SSE 와 커밋된 Vue dist 를 함께 서빙, `run.py` 원클릭 실행 | 03 원칙 1, 가중 점수 125/140 | stdlib+vanilla(83), 수집기+SQLite(84) | (ADR-001) |
| D-02 | 사용량은 `~/.claude/projects/<enc>/**/*.jsonl` 에서 `"usage":` 사전 필터 후 허용 필드만 복사, requestId 중복 제거(last-wins), 메모리 증분 캐시 | 30 EDA: 중복 57.95%, 4.4 ms/MB | Admin API(키 필요) | (ADR-002) |
| D-03 | 한도 %는 statusLine 스냅샷(`workspace/memory/.monitor/claude-status.json`)에서, 전역 statusLine 은 체이닝 | 00 Q4 | 전역 설정 수정(02 §11 금지) | (ADR-003) |
| D-04 | 루프 제어: 대시보드는 `.control.json` 만, CLI 는 `loop-status.json` 만 쓴다(파일당 쓰기 주체 1개). wait-resume exit 0/10/20/2 | 경쟁 조건 제거 | 단일 파일 공유 | (ADR-004) |
| D-05 | 프론트 dist 를 저장소에 커밋, `.build-meta.json` 으로 신선도 검사 | 사용자 PC 에 Node 불필요 | 실행 시 빌드 | (ADR-005) |
| D-06 | 변경 감지는 1초 stat 폴링, watchfiles 미사용 | 03 원칙 3 | watchfiles | (ADR-008) |
| D-07 | AI-DLC 상태는 memory_cascade 의 읽기 함수만 사용, `aidlc.py status` 서브프로세스 금지(closed STM 을 아카이브하는 부작용) | 30 EDA 발견 | status 호출 | (ADR-009) |
| D-08 | 응답 envelope `{data, meta}`, 에러 `{"error":{code,message}}`, Host/Origin 가드 | user/02 §6 | - | (ADR-011) |
| D-09 | 루프 CLI exit code: 0 재개/정상, 10 계속 대기, 20 일시정지 상한 초과, 2 제어 파일 broken(계속 진행), 64 사용법 오류, 1 예기치 못한 예외(경고 후 계속). 루프를 멈추는 것은 일시정지 요청뿐. stdout 은 `AIDLC-LOOP <sub> <RESULT> k=v` 한 줄, 스킬은 exit code 로만 분기 | argparse 기본 2 와 broken 충돌 회피, 원칙 2 | - | (STM-0001, contracts/loop-cli.md) |
| D-10 | 일시정지 상한은 일시정지 1회(episode) 기준 — paused_since 는 반복 wait-resume 을 넘어 유지, 재개 시 null. 활성 루프가 없으면 loop-check·wait-resume·loop-end 는 쓰지 않고 exit 0(NO_LOOP) | 00 Q5 해석 | 루프 전체 누적 | (STM-0001) |
| D-11 | heartbeat 로 세션 생존을 판정하는 것은 paused 상태(120 s 기준)에서만. running 에서는 사이클 경계에서만 갱신되므로 판정하지 않음 | 오탐 방지 | - | (STM-0001) |
| D-12 | SSE: 첫 프레임 `retry: 5000`, keep-alive 15 s, id 미사용, ready = 사용량 캐시 데우기 완료, alerts 는 memory/tasks/usage 발행 시 파생, 연결 상한 초과 503 `TOO_MANY_STREAMS`(신규 에러 코드), 프론트는 45 s 무프레임 시 재연결 | ADR-011 보완 | - | (STM-0001, contracts/sse-events.md) |
| D-13 | `transcript_dir_name` 은 `^(?!\.{1,2}(?![\s\S]))[A-Za-z0-9._-]{1,255}(?![\s\S])` 로 제한, reader 는 재검증 + resolve 결과가 `~/.claude/projects/` 직속 하위인지 확인(실패 시 폴백, 값 없이 코드만 기록), API 응답·SSE·로그 노출 금지 | security 리뷰 FAIL 조치 | 관대한 reader | (STM-0001, contracts/README §2·§3) |
| D-14 | 비-JSON Content-Type 의 변경 요청도 403 `FORBIDDEN_ORIGIN` 으로 거부 (415 는 계약 위반=FAIL) | 20 §QS-05 가 명시, 20 §8 에러 코드는 닫힌 집합(415 없음), ADR-011 §5 가 같은 항목에서 묶어 서술 | 415 | (STM-0003, architecture 리뷰) |
| D-15 | Origin 헤더 없는 로컬 POST 는 잔여 위험으로 수용 | ADR-011 이 토큰 인증을 기각 | 토큰 인증 | (STM-0003, threat-model.md) |
| D-16 | 테스트는 실제 `~/.claude` 를 쓰지 않는다: autouse 로 `HOME`/`USERPROFILE` 을 임시 경로로 바꾸고 `AIDLC_ROOT`/`CLAUDE_HOME` 을 지우며, 앱 경로 주입은 `app_env` 환경 변수로만 (CON-06) | user/02 §5, privacy.md §7 | 실제 기록 사용 | (STM-0004) |
| D-17 | 사용량 집계 검증은 3자 대조: 생성기 기대값(`JsonlManifest.expected_buckets`) ↔ 독립 오라클(`reference_parser.aggregate`) ↔ 앱 수집기 | 오라클 오류 차단 | 생성기만 신뢰 | (STM-0004) |
| D-18 | Host 가드는 호스트+포트 정확 일치(`127.0.0.1:<port>`, `localhost:<port>`, 소문자화), 자체 순수 ASGI `HostGuardMiddleware` 를 가장 바깥에 둔다. TrustedHostMiddleware 미사용(포트 무시). `[::1]`·끝 점·포트 생략·빈 Host 거부, 메시지에 받은 Host 미포함 | 03 §2 보안 2순위, DNS rebinding, QS-05 | TrustedHostMiddleware | (STM-0005, ADR-011 §4) |
| D-19 | `settings.port` 가 uvicorn 바인딩·Host 가드·Origin 가드의 단일 출처, 포트 0 금지 | 불일치 방지 | 각자 계산 | (STM-0005, ADR-011 §4) |
| ~~D-20~~ | HTTP 에러 코드는 ADR-011 §9 의 닫힌 집합(VALIDATION_ERROR, NOT_FOUND, BAD_HOST, FORBIDDEN_ORIGIN, NO_ACTIVE_LOOP, CONTROL_WRITE_FAILED, INTERNAL_ERROR, TOO_MANY_STREAMS). 415 미사용 | 계약 고정 | 열린 집합 | (STM-0005, ADR-011 §9) → D-26 으로 대체 (STM-0009) |
| D-21 | FR-001 단계 판정(A11 확정안, PO 화면 리뷰 전까지 assumption): 상태 4종(완료/진행/대기/확인 불가 — 확인 불가는 판정 파일이 깨졌을 때만), 단계 독립 판정, 현재 단계 = 완료가 아닌 최소 번호, 단계 4 완료 = tasks `rev ≥ 1` + Phase 에 Task ≥ 1, 단계 5 완료 = 전 Phase `[x]` + 미처리 cascade 없음 + STM 비활성, 단계 6 완료 = docs Gate PASS + `docs/README.md` 존재 | 템플릿 직후 오판 방지(실행 확인) | Phase 존재만 확인 | (STM-0006, stories/FR-001 §2) |
| D-22 | FR-005 화면 라벨 6종(V1~V6)과 종료 사유 문구는 stories/FR-005 §2.1·§2.3 이 단일 기준. qa 는 문구 포함 여부로 검증 | 문구 흩어짐 방지 | - | (STM-0006) |
| D-23 | KPI 측정 규칙: KPI-01 타이머 = 질문 읽기 시작~답, 첫 화면 = 스크롤·클릭 없는 영역(창 크기 기록), 정답은 파일에서 직접(`aidlc.py status` 금지). KPI-02 타이머 = 실행 동작~상단 행 표시, 다운로드 제외 | 측정 재현성 | - | (STM-0006, uat/uat-checklist) |
| D-24 | 테스트 홈 격리 3겹: `pytest_configure` 세션 치환 + autouse 테스트별 치환 + `sys.addaudithook` 가드(`RealHomeAccessError`). 가드는 제거 불가라 `enabled` 플래그로 켜고 끄며 음성 테스트는 `home_guard.expect()` 사용. 위반은 예외 전에 기록되어 삼켜도 teardown 에서 드러남 | D-16 강화, security 리뷰 | function 범위만 | (STM-0007) |
| D-25 | Host·Content-Type 검증 케이스의 단일 정의는 privacy.md §5.1(H-01~H-22: 4개 대상 GET/POST/SSE/dist)·§5.2(C-01~C-11: pause·resume). Content-Type 은 미디어 타입(첫 `;` 앞)이 대소문자 무시로 `application/json` 과 정확히 일치, 422 검증보다 먼저 403. 잘못된 Host 는 403·404 보다 먼저 400. Host 헤더 개수는 가드가 `scope["headers"]` 에서 판정 | ADR-011 정확 일치 규칙의 구체화 | ADR 문구만 | (STM-0008) |
| D-26 | 에러 코드 닫힌 집합 9개 = D-20 + `METHOD_NOT_ALLOWED`(405, OPTIONS 포함, `Allow` 헤더, CORS 없음). 기본 `{"detail":...}`·평문 404/405 본문 금지. `/api` 아래 모르는 경로 404, RequestValidationError 422, 기타 프레임워크 4xx → 422, 5xx·미처리 예외 500. `/api` 밖 모르는 경로 404(SPA 폴백 없음) | 상태↔코드 1:1 | 405 를 404 로 접기 | (STM-0009, ADR-011 §9) |
| D-27 | scope 처리: http 검사, websocket 은 accept 없이 close 1008(JSON 에러 포맷의 유일한 예외), lifespan 통과, 기타 무시 | 기본 거부 | - | (STM-0009, ADR-011 §10) |
| D-28 | SSE `/api/v1/events` 는 GET 만(HEAD 포함 나머지 405 `Allow: GET`, Starlette 자동 HEAD 를 backend 가 막아야 함). 출처 검사는 **경로 기준**(메서드 무관)으로 라우팅·슬롯 획득 전: Origin 불일치/null, 또는 `Sec-Fetch-Site` 가 strip·소문자 정확 일치로 `same-origin`/`none` 이 아니면 403. `Origin`·`Sec-Fetch-Site` 복수 헤더 403. 400·403·405 는 슬롯 미소모. 다른 GET 에는 출처 검사 미적용(SOP·읽기 전용) | SSE 슬롯 소모(가용성) 방지, security 재리뷰 PASS | GET 만 검사(HEAD 우회) | (STM-0009, ADR-011 §11) |
| D-29 | 처리 순서: scope → Host 400 → 출처·미디어 타입 403 → 라우팅 404/405 → 검증 422 → 핸들러. events 경로는 400 → 403 → 405 → 503 → 스트림 | 정보 노출 최소 | - | (STM-0009, ADR-011 §12) |

## 2. 확립된 패턴 & 컨벤션 (Patterns)
- 공통 DoD: 테스트 통과, ruff/eslint/타입 검사, frontend 변경 시 dist 재빌드, 문서 갱신, run 스크립트로 화면 확인 (user/02§10)
- Claude 기록에서는 usage·model·timestamp·requestId·isSidechain 만 읽는다. 실제 `~/.claude` 기록은 테스트에 쓰지 않는다 (user/02§5, 00 Q2)
- Windows 에서는 `python3` 대신 `python`/`py`, 셸 스크립트는 LF (CLAUDE.md 실행 환경)
- (예: 모든 API 응답은 `{data, error}` 래퍼 사용 (STM-0002))
- 파일 계약: 스키마는 작성자를 검증(additionalProperties false), 읽는 쪽은 관대하되 schema 버전 불일치는 broken(SOURCE_PARSE_ERROR). 단, 보안 필드는 reader 도 재검증 (STM-0001)
- 파일당 쓰기 주체 1개: `.control.json` = 대시보드, `.monitor/loop-status.json` = 루프 CLI, `.monitor/claude-status.json` = statusline 스크립트 (STM-0001, contracts/README)
- JSON Schema 2020-12 의 `format` 은 기본 annotation 이라 강제되지 않는다 → 시각 등은 `pattern` 으로 함께 강제 (STM-0001)
- JSON Schema pattern 의 끝 앵커는 `$` 대신 `(?![\s\S])` — Python `re` 의 `$` 는 끝 개행 앞에서도 매치된다. Python·ECMA 동일 동작 (STM-0001)
- 존재하지 않는 경로의 무시 여부는 `git check-ignore --no-index -v <path>` 로 확인. 디렉터리 패턴은 하위 파일 경로로 검사 (STM-0002)
- 보안 리뷰 체크리스트 ID 체계: P-(개인정보) / N-(네트워크 Host·Origin) / W-(쓰기 경로) / D-(의존성) / T-(본문 비노출 테스트). threat-model 의 검증 열이 이 ID 를 가리킨다. ID 는 한 문서(privacy.md)에서 정의하고 다른 문서는 참조만 한다 (STM-0003)
- 주의: privacy.md 의 체크리스트 D-01~D-04(의존성)는 이 파일 §1 결정 D-01~ 과 번호가 겹친다. 맥락(문서)으로 구분하고, 인용 시 출처 문서를 함께 적는다 (STM-0003)
- 본문 표식(content marker)은 영숫자만 — Claude Code 경로 인코딩(`[^A-Za-z0-9] → -`)에서 깨지지 않게 (STM-0004)
- `tests/` 에 `__init__.py` 없음 → `from fixtures...` import, 테스트 파일 basename 은 디렉터리가 달라도 중복 금지 (STM-0004)
- 실패 메시지는 표식 종류·키 이름만 출력하고 주변 내용·경로 원문은 출력하지 않는다 — 테스트 로그도 노출 경로다 (STM-0004)
- 시나리오 ID(S-01~S-13, P-01~P-02)는 `workspace/project/qa/test-strategy.md` §4 에서만 정의하고 다른 문서는 참조만 (STM-0004)
- 미들웨어·API 테스트의 TestClient 는 `base_url="http://127.0.0.1:<fixture port>"` 필수 — 기본 Host `testserver` 는 BAD_HOST (STM-0005)
- Host 헤더는 정확히 1개여야 한다 — 판정은 서버 파서(h11)에 맡기지 않고 가드에서 한다 (STM-0005, security 리뷰)
- 스토리 AC 는 `AC-n (요약)` + Given/When/Then, 테스트는 test-strategy §4 S-xx/P-xx 를 참조만 (STM-0006)
- 패널 화면 상태는 `meta.status` 5종(ok/partial/empty/error/warming)으로 스토리마다 표를 둔다 (STM-0006)
- 가드 음성 테스트는 실제 홈 아래 **존재하지 않는 이름**만 쓰고 `RealHomeAccessError` 를 단언해 "시스템 호출 전 차단" 을 증명한다(실제 파일을 읽지 않음) (STM-0007)
- 감사 hook 가드는 인자 없는 호출(None 인자, 예: `os.listdir()`)을 cwd 로 해석해 판정해야 한다 (STM-0007, security 리뷰)
- 보안 점검은 케이스 표(케이스 id, 요청, 대상, 기대 상태/코드) + 코드 점검 grep(TrustedHostMiddleware 0건, `startswith`/`in` 비교 금지, 415 경로 없음)으로 써서 구현 Task 가 그대로 테스트로 옮기게 한다 (STM-0008)
- 중복 Host(H-18)는 httpx TestClient 로 보내기 어려우므로 ASGI scope 를 직접 만들어 테스트한다 (STM-0008)
- Starlette 는 경로+메서드 일치를 경로만 일치보다 우선한다 → `Mount("/")`·`/api` 캐치올이 405 를 가로챌 수 있으니 정적 서빙은 어떤 라우트에도 안 맞을 때로 둔다 (STM-0009)

## 3. 알려진 이슈 & 리스크 (Known Issues)
| ID | 내용 | 영향 범위 | 상태 | 출처 |
|----|------|-----------|------|------|
| ~~I-01~~ | ~~`.gitignore` 에 런타임 파일 미등록~~ | 저장소(public) | 해결 (STM-0002): 런타임·build 블록 추가 | (STM-0001, STM-0002) |
| I-03 | 전역 `dist/` 같은 넓은 무시 패턴이 추가되면 커밋 대상 dist 가 무시됨(ADR-005 위반) | 배포 | 감시: 리뷰 시 `git check-ignore --no-index monitor/frontend/dist/index.html` 가 exit 1 | (STM-0002) |
| I-02 | `TOO_MANY_STREAMS`(503), loop-cli 결정(exit 64/1, episode 상한, NO_LOOP) 이 ADR-004·ADR-011·20 §5 에 아직 없음 | 문서 정합성 | 열림 → T-009 | (STM-0001) → 일부 해소: TOO_MANY_STREAMS 는 ADR-011 §9·20 §5 반영 (STM-0005), loop-cli 결정은 T-009 |
| ~~I-04~~ | ADR-011 §4: Host 가드(TrustedHostMiddleware)가 포트를 검사할지 미정. 현재는 포트 무시인데 privacy.md N-02 는 포트 불일치 거부를 요구 | 보안 체크리스트 정합성 (비차단) | 열림: 검사하면 구현 방식을 ADR 에 명시, 안 하면 N-02 포트 케이스를 선택 항목으로 유지 | (STM-0003) → **해소** (STM-0005, ADR-011 §4·§5 / ADR-006) |
| ~~I-05~~ | ADR-011 §5 에 비-JSON Content-Type 도 403 `FORBIDDEN_ORIGIN` 이라는 한 줄 보강 필요 (D-14) | 문서 정합성 (비차단) | 열림 → [architecture] 후보 | (STM-0003) → **해소** (STM-0005, ADR-011 §4·§5 / ADR-006) |
| I-06 | 보안 통제가 모두 "요구" 상태(구현 전). 구현 후 P/N/W/T 항목을 실제 실행 근거와 함께 재확인 필요 | 보안 | 열림: backend 구현 후 security 리뷰 | (STM-0003) |
| I-07 | tasks.md T-002 DoD 경로 `workspace/teams/security/` 가 실제 경로 `workspace/project/security/` 와 불일치 | 문서 정합성 | 열림 → cascade 2/3 에서 정정 | (STM-0003) |
| ~~I-08~~ | jsonschema(dev) 가 ADR-006 dev 목록에 없음 | 문서 정합성 | 열림 → T-021 | (STM-0004) → **해소** (STM-0005, ADR-011 §4·§5 / ADR-006) |
| ~~I-09~~ | 홈 격리가 function 범위라 session 범위 fixture·수집 시점 import 는 실제 HOME 을 볼 수 있음, `CLAUDE_CONFIG_DIR` 미처리 | 테스트 신뢰성·개인정보 | 열림 → T-023 (T-005 전) | (STM-0004) → **해소** (STM-0007: 3겹 격리 + audit-hook 가드, 95 passed) |
| I-10 | 하드 링크는 `resolve()` 경계 검사로 탐지 불가 | 경로 이탈 | 열림 → T-022 (방침 결정) | (STM-0004) |
| I-11 | 30일 JSONL 329~658 MB 크기는 선형 추정(pad 9000~18000) | 성능 테스트 정확도 | 열림 → T-013 실측 | (STM-0004) |
| I-12 | `jsonschema-specifications 2025.9.1` 이 02 §9 "최근 1년 내 릴리스" 경계(약 13개월) — dev·전이 전용이라 수용 | 의존성 정책 | 감시 → T-007 고정 시 최신 확인 | (STM-0005) |
| ~~I-13~~ | privacy.md N-02·N-04 가 ADR-011 §4·§5 와 불일치(포트 검사 "선택", TrustedHost 문구), 중복 Host·선행 0·userinfo·Content-Type 접두 함정 케이스 없음 | T-005 리뷰 기준 | 열림 → T-024 (T-005 전) | (STM-0005) → **해소** (STM-0008: privacy.md §5.1 H-01~H-22, §5.2 C-01~C-11) |
| ~~I-14~~ | ADR-011 §9 에 405(OPTIONS 포함)·Starlette 기본 HTTPException 매핑 규칙과 기본 `{"detail":...}` 본문 금지가 없음, HostGuard 의 websocket/lifespan scope 처리 미정, SSE GET Origin 검사 여부 미정(교차 출처 EventSource 로 슬롯 소모 → 가용성) | 앱 셸 구현 | 열림 → T-025 (T-005 전) | (STM-0005) → **해소** (STM-0009, ADR-011 §9~§12) |
| I-15 | `aidlc.py check docs` 는 검사 대상 문서가 0개여도 PASS(exit 0) → P1 종료 조건·T-014 DoD 가 문서 없이 충족될 수 있음. 대시보드는 D-21 의 `docs/README.md` 조건으로 보완. 프레임워크 Gate 변경은 별도 승인 필요 | Gate 신뢰성 | 열림 → 사용자 질문 Q-P2 | (STM-0006) |
| I-16 | 루프 도중 `.control.json` 이 깨지거나 삭제되면 대시보드가 seq 1 을 써서 `baseline_seq` 이하가 되어 CLI 가 새 pause/resume 을 무시 | FR-005 신뢰성 | 열림 → T-026 (T-008 전) | (STM-0006) |
| I-17 | FR-002 Phase 진행률 바: `plan` SSE topic 이 M2 라 P1 에서 실시간 갱신 보장 안 됨(01 §5.1 흐름 3 과 어긋남) | UX | 열림 → T-012 에서 `tasks` 이벤트 시 `/plan` 재조회 | (STM-0006) |
| I-18 | PO 미답 질문: Q-P1(단계 3 에 `.claude/agents` 요구?), Q-P2(docs Gate 빈 대상), Q-P3(run.bat 실패 시 창 유지), Q-P4(R-01 실패 시 후퇴안은 01 §10 과 다름 → PO 결정) | 수용 기준 | 열림 → 사용자에게 질문 | (STM-0006) |
| I-19 | home_guard 빈틈: 인자 없는 `os.listdir()` 통과(None 인자), 경로 판정 중 OSError 시 통과, 원래 `XDG_CONFIG_HOME/claude` 미등록. 가드 밖: 정수 fd·`dir_fd`·`os.stat`/`os.readlink`·서브프로세스 서버 — test-strategy 에 미기재 | 테스트 격리 | 열림 → T-013 (비차단) | (STM-0007) |
| I-20 | 출처 가드의 경로 비교 기준(디코드된 `scope["path"]` vs `raw_path`, 끝 슬래시) 미정 → `/api/v1/%65vents` 등으로 우회 가능성 | SSE 가용성 | 열림 → T-011 (가드는 라우터와 같은 디코드 path 로 비교 + 우회 경로 슬롯 카운트 테스트) | (STM-0009) |
| I-21 | Starlette 자동 HEAD·405 가로채기 동작은 이 환경에 FastAPI 가 없어 실행 미확인 | 계약 준수 | 열림 → T-005·T-011 테스트로 고정 | (STM-0009) |

## 4. 팀별 지식 (Team Knowledge)
<!-- /aidlc-teams 가 생성된 팀마다 "### <team-id>" 소제목을 추가한다 -->

### product
- (아직 없음)
- 스토리 6건(FR-001~005, SCOPE-01, AC 114개) + uat-checklist. A11 은 T-014 화면 리뷰 후 assumption 해제 (STM-0006)

### architecture
- (아직 없음)
- ADR 변경은 20 의 에러 코드 목록(§5)·컴포넌트 표 문구까지 같이 고친다. Task 문구의 절 번호는 grep 으로 실제 위치를 확인 (STM-0005)

### qa
- (아직 없음)
- fixture 9종(workspace, jsonl_gen, claude_home, hashing, markers, contracts, runtime_files, reference_parser) + smoke 72건. 실행: `monitor/.venv/bin/python -m pytest monitor/backend/tests -q` (STM-0004)
- home_guard + test_home_guard(21건). 전체 95 passed. 반쪽 커밋 재개 때 실패 원인은 `import os` 누락 하나였다 (STM-0007)

### cicd
- (아직 없음)
- .gitignore 의 Monitor 항목은 런타임 / build·dev 두 주석 블록. dist 는 의도적으로 제외(ADR-005) (STM-0002)

### ops
- (아직 없음)

### security
- (아직 없음)
- 보안 문서 경로는 `workspace/project/security/` (threat-model.md = STRIDE 6영역, privacy.md = 허용 필드·접근 범위·Host/Origin·체크리스트). charter·40·타 팀 charter 모두 이 경로를 참조 (STM-0003)
- 보안 경계는 "허용 필드 allow-list 복사"다. `"usage":` 사전 필터는 성능용이며 보안 경계가 아니다 (본문에 usage 문자열이 있어도 유입되지 않음) (STM-0003)
- 체크리스트 ID 체계는 §2 참조 (P-/N-/W-/D-/T-). 비-JSON Content-Type 도 403 FORBIDDEN_ORIGIN 이 기준 (D-14) (STM-0003)
- 쓰기 경로는 `.control.json` 1개뿐 (R-10·QS-07). Origin 없는 로컬 POST 는 수용된 잔여 위험 (D-15) (STM-0003)
- 런타임 감사: 임시 audit-hook 플러그인으로 전체 테스트 중 실제 HOME 아래 open/listdir/scandir 0건 확인하는 방식이 유효했다 → conftest 상시 가드로 승격 예정 (STM-0004)

### backend
- (아직 없음)

### frontend
- (아직 없음)
- 계약 문서는 jsonschema Draft202012 로 check_schema + examples + 음성 케이스까지 돌려 검증한다 (STM-0001)
- 경로성 필드는 패턴 검증 + resolve 후 경계 검사 + 노출 금지 3종을 같이 요구한다. symlink 우회 여부는 backend reader 리뷰 때 재확인 (STM-0001)

## 5. 교훈 (Lessons Learned)
- (반복하지 말아야 할 실수, 효과가 있었던 방법)
- examples 만이 아니라 음성 케이스까지 스키마로 돌려야 `format` 비강제, `$` 끝 개행 같은 구멍이 드러난다 (STM-0001)
- 보안 리뷰는 계약 단계에서도 효과가 있다 — 구현 전에 경로 이탈(`..`) 위험을 막았다 (STM-0001)
- 번호 참조를 문서 두 개에 나눠 쓰면 어긋나기 쉽다 — 한 문서에서 ID 를 정의하고 다른 문서는 참조만 한다 (STM-0003)
- 리뷰 모드가 문서 대조만으로도 구현 전 모순(415 vs 403, Host 포트 무시 vs N-02)을 잡아냈다 (STM-0003)
- 중단된 세션을 이어받을 때는 테스트 통과만 보지 말고 모듈을 끝까지 읽고 `git status`·커밋과 대조해 반쯤 쓴 파일이 없는지 확인한다 (STM-0004)
- Task 문구에 적힌 문서 절 번호는 틀릴 수 있다(20 §8 → 실제 §5). 수정 전에 grep 으로 위치를 확인한다 (STM-0005)
- 가정을 확정할 때는 프레임워크 스크립트를 실제로 돌려 경계 동작(템플릿 직후 상태, 빈 대상 PASS)을 확인해야 오판을 막는다 (STM-0006)
- 중단 후 커밋된 반쪽 변경은 실패 원인이 사소한 경우가 많다 — 갈아엎기 전에 먼저 실행해 원인을 확인한다 (STM-0007)
- ADR 이 확정되면 그 ADR 을 인용하는 체크리스트의 "선택"/"후보" 문구를 같은 Phase 안에 정리한다 (STM-0008)
- 한정 자원(연결 슬롯)을 잡는 경로의 보안 검사는 메서드가 아니라 경로로 건다 — 프레임워크가 자동으로 붙이는 메서드(HEAD)로 우회되지 않게 (STM-0009)

## 6. 용어집 (Glossary)
| 용어 | 정의 |
|------|------|
