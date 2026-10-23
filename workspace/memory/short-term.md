---
status: active
task: T-025
team: architecture
outcome: done
opened_at: 2026-10-23T13:52:10+00:00
---
# Short-term Memory

> **계층 4 (작업 단위).** Task 1개를 수행하는 동안의 작업 메모리. 한 번에 하나만 열린다.
> 수명: `status: active` 로 열고 → 작업 → `outcome` 기록 → `status: closed` 로 닫는다.
> 닫히는 순간 Hook 이 이 파일을 `archive/STM-xxxx_<task>.md` 로 옮기고 Long-term memory 갱신(cascade 1/3)을 요구한다.
> frontmatter 값: status(idle|active|closed) / outcome(done|partial|blocked)

## 1. 목표
- Task: T-025 [architecture] ADR-011 §9 보강: 405(OPTIONS 포함)·Starlette 기본 HTTPException 매핑 규칙(기존 코드로 매핑 또는 `METHOD_NOT_ALLOWED` 추가 결정), 기본 `{"detail":...}` 본문 금지, HostGuard 의 websocket scope 거부·lifespan 통과, SSE GET 에 Origin 검사 적용 여부 결정(교차 출처 EventSource 슬롯 소모 가용성 위험), §4 에 Host 헤더 정확히 1개 규칙·선행 0·userinfo·추가 세그먼트 거부 명시, §5 에 미디어 타입 대소문자 무시 정확 일치·422 보다 먼저 403 명시(D-25, privacy.md §5.1·§5.2 와 정합) — I-14 | deps: T-021
- 완료 조건(DoD): ADR-011·20 §5·sse-events.md 정합, 결정 근거 기록 (출처: STM-0005 §5) + user/02 §10 공통 DoD

## 2. 로드한 컨텍스트
- 관련: LTM I-14(405·HTTPException 매핑, websocket/lifespan scope, SSE Origin), D-18~D-20, D-25(privacy.md §5.1·§5.2 케이스 단일 정의), D-12(SSE 연결 상한 503)
- 근거: workspace/project/adr/ADR-011, 20-architecture-analysis.md §5, contracts/sse-events.md, security/privacy.md §5, STM-0005·STM-0008 §5 의 [architecture] 후보

## 3. 작업 로그
<!-- 시간순으로 짧게. 무엇을 했고 무엇을 봤는지 -->
- charter, user/02 §6, user/03 §1·§2·§8, LTM D-18·D-20·D-25·I-14, ADR-011, ADR-005·007, 20 §4·§5, sse-events.md, privacy.md §5 를 읽음. ADR-007 이 vue-router 미사용(뷰 1개) → SPA 폴백 불필요 근거.
- ADR-011 갱신: §2 기본 `{"detail"}`·평문 본문 금지, §4 Host 정확히 1개(`scope["headers"]` 계수)·문자열 정확 일치(파싱 정규화 없음 → 선행 0·userinfo·추가 세그먼트 자동 거부)·H-01~H-22 참조, §5 쓰기 가드 범위(GET/HEAD/OPTIONS 외 전 메서드·경로 무관)·미디어 타입(첫 `;` 앞, strip·소문자, 정확 일치)·422/404 보다 먼저 403·C-01~C-11 참조, §9 `METHOD_NOT_ALLOWED`(405) 추가 + 프레임워크 오류 매핑 표 + 정적 모르는 경로 404(SPA 폴백 없음) + Starlette Mount FULL/PARTIAL 함정 주의, §10 scope 처리(http 검사·websocket 항상 거부 close 1008·lifespan 통과·그 밖 무시), §11 SSE 출처 검사(Origin 불일치 또는 Sec-Fetch-Site ∉ {same-origin,none} → 403, 슬롯 소모 전, 다른 GET 미적용), §12 처리 순서, Alternatives 4건, Consequences·변경 이력.
- 20 §5 에러 코드 목록에 `METHOD_NOT_ALLOWED`·`detail` 금지·처리 순서 반영, 20 §4 API 앱 셸 행에 dist 서빙 방식·scope 처리 반영. sse-events.md §1 에 출처 검사·판정 순서 추가(추가 동작이라 schema_version 유지 — 이벤트 형식 무변경).
- Starlette/FastAPI 가 이 환경에 설치돼 있지 않아 FULL/PARTIAL 라우팅 동작은 실행 확인하지 못함 → ADR 에 "결과가 계약, T-005 테스트로 고정" 으로 기록.
- `python3 aidlc/scripts/aidlc.py check project` → GATE PASS (미작성 0, 누락 0).

## 4. 발견 사항 (LTM 후보)
- 결정: HTTP 에러 코드 닫힌 집합에 `METHOD_NOT_ALLOWED`(405) 추가 → 9개, 상태↔코드 1:1(500 만 2개). OPTIONS 도 405 + `Allow`, CORS 헤더 0 (ADR-011 §9, 근거 03 §2 유지보수성·원칙 3)
- 결정: 프레임워크 기본 오류 매핑 — `/api` 모르는 경로 404(메서드 무관), 메서드 불일치 405, RequestValidationError 422, 그 밖 4xx HTTPException 422, 5xx·미처리 500. `{"detail":...}`·평문 본문 0건. 정적 모르는 경로 404, SPA 폴백 없음(ADR-007 vue-router 없음)
- 결정: HostGuard scope — http 검사, websocket 항상 거부(accept 없이 close 1008, JSON 본문 예외), lifespan 통과, 그 밖 무시 (ADR-011 §10)
- 결정: SSE `GET /api/v1/events` 만 출처 검사 — Origin 있고 불일치(null 포함) 또는 Sec-Fetch-Site ∉ {same-origin, none} → 403 `FORBIDDEN_ORIGIN`, 슬롯 잡기 전. 다른 GET 미적용(SOP·읽기 전용·no-cors 는 Origin 없음) (ADR-011 §11)
- 결정: 처리 순서 scope → Host 400 → 출처·미디어 타입 403 → 라우팅 404/405 → 검증 422 → 핸들러 (ADR-011 §12). 쓰기 가드는 GET/HEAD/OPTIONS 외 모든 메서드에 경로 무관 적용
- 패턴: Host 값은 파싱·정규화 없이 strip+소문자 후 허용 문자열과 정확 일치 → 선행 0·userinfo·추가 세그먼트가 별도 분기 없이 거부됨
- 이슈/리스크: Starlette 라우터는 FULL 매치를 PARTIAL(메서드 불일치)보다 우선 → `Mount("/", StaticFiles)` 나 `/api` 캐치올이 405 를 가로채 정적 405/404 로 바꿀 수 있음. 정적 서빙은 no-match 경로(라우터 기본 처리기)에 둘 것 — 미검증(환경에 FastAPI 없음), T-005 테스트로 확인
- 이슈/리스크: no-cors 서브리소스(`<img src=/api/v1/events>`)는 Origin 을 보내지 않음 → SSE 슬롯 보호는 Sec-Fetch-Site 로 보완. 두 헤더 없는 구형 브라우저는 잔여 위험(상한 8 + 끊김 감지)
- 교훈: 에러 코드 집합을 "닫힌 집합" 으로 선언하면 프레임워크 기본 응답(404/405/422/websocket)까지 매핑 표로 덮어야 계약이 완결된다

## 5. 새로 발견된 Task (Task 후보)
- [security] privacy.md §5 에 ADR-011 T-025 결정 반영: 표에 SSE 출처 행·405/OPTIONS 행·websocket 거부 행 추가, SSE 출처 케이스 표(예: Origin evil/null/다른 포트, Sec-Fetch-Site cross-site/same-site → 403 이고 슬롯 미소모, 같은 출처·헤더 없음 → 통과), 405/404 매핑 케이스(`POST /api/v1/health`, `GET /api/v1/control/pause`, `OPTIONS /api/v1/control/pause`, `POST /api/v1/nope`→403/404, `GET /nope`·`/assets/nope.js` → 404, `detail` 키 0건), websocket scope 거부·lifespan 통과 케이스 정의. threat-model.md 에 "교차 출처 SSE 슬롯 소모(D)" 위협 행 추가 — ADR-011 §9~§12 (T-005 전)
- [backend] T-005 DoD 에 ADR-011 §9 매핑 표·§10 scope·§11 SSE 출처·§12 순서 테스트 포함, `METHOD_NOT_ALLOWED` 를 에러 코드 enum 에 추가하고 openapi.json export·docs/api 재생성 (T-005 범위 확장)
- [frontend] 에러 코드 처리에 `METHOD_NOT_ALLOWED` 추가(모르는 코드는 일반 오류로 처리하는지 확인) — ADR-011 §9
- [architecture] (security 리뷰 FAIL) ADR-011 §11·sse-events.md §1 정합: SSE 출처 검사를 `/api/v1/events` 경로의 모든 메서드에 적용하거나 HEAD 를 405 로 명시 — HEAD 로 출처 검사 없이 슬롯을 잡는 우회 차단. Origin·Sec-Fetch-Site 복수 헤더 거부, Sec-Fetch-Site 값 소문자 정확 일치 명시 (T-025 안에서 처리 권장)
- [security] T-022 에 접기(T-005 비차단 — 동의): privacy.md §5 에 SSE 출처·405/OPTIONS·websocket/lifespan 케이스 표, threat-model.md 70행 'SSE 연결 고갈' 을 '교차 출처 SSE 슬롯 소모(D)' 로 갱신(완화 ADR-011 §11, 잔여 위험 구형 브라우저). 조건: ① 새 케이스는 ADR-011 §9 표·§11 예시와 같은 값으로 정의(D-25 단일 출처 충돌 방지) ② T-013 전 완료
- [backend] T-005 DoD 에 ADR-011 §9~§12 테스트 직접 포함 시, SSE 출처 403·슬롯 미소모 테스트는 /events 가 생기는 T-011 DoD 에도 명시(T-005 는 가드 단위 테스트 + 스텁 경로, T-011 은 실제 슬롯 카운트 검증)

## 6. 결과 & 인수인계
- 산출물(파일/PR): workspace/project/adr/ADR-011-api-contract-and-local-security.md (§2·§4·§5·§9 보강, §10~§12 신설, Alternatives·Consequences·변경 이력), workspace/project/20-architecture-analysis.md (§4 API 앱 셸 행, §5 에러 코드 목록), workspace/project/contracts/sse-events.md (§1 출처 검사·판정 순서)
- 검증 결과: `python3 aidlc/scripts/aidlc.py check project` GATE PASS. ADR-011 §9 ↔ 20 §5 에러 코드 9개 일치 확인(문서 대조). Starlette 라우팅 동작(FULL/PARTIAL)은 실행 검증하지 않음(FastAPI 미설치) — T-005 테스트 몫
- 남은 일: §5 후보 3건(security privacy.md/threat-model 반영, backend T-005 범위, frontend 코드 enum). LTM: D-20 갱신(코드 9개, METHOD_NOT_ALLOWED), I-14 해결 처리

## 7. 리뷰 기록 (리뷰 게이트)
<!-- /aidlc-run 이 리뷰 게이트 대상 팀을 리뷰 모드로 호출하면 각 팀이 한 줄씩 추가 -->
| 팀 | 결과 | 근거 | 필요한 조치 |
|----|------|------|-------------|
| security | FAIL | git show 881156e 대조 + threat-model §D·privacy.md §5 대조(문서 Task 라 pytest/audit 미실행). PASS 항목: (1) SSE 출처 규칙 — 교차 출처 EventSource 는 CORS 모드라 항상 Origin 을 보내 차단, no-cors 서브리소스는 Sec-Fetch-Site 로 차단, 같은 출처 대시보드(Origin 없음/허용값, Sec-Fetch-Site same-origin)와 주소창 직접 열기(none)는 통과 → 오탐 없음. 두 헤더 없는 구형 브라우저(예: Sec-Fetch 미지원 Safari·구형 Firefox)의 no-cors 서브리소스는 잔여 위험이며 §11 에 수용 근거(상한 8·끊김 감지·5초 폴링 폴백, 영향=가용성만) 기록됨 → 로컬 도구로 수용 가능. (2) websocket accept 없이 close 1008(=HTTP 403), lifespan 통과(네트워크 입력 없음), 그 밖 scope 무시(기본 거부) → 안전. (3) 순서 400→403→404/405→422: 비-GET 은 경로 무관 403 이 먼저라 교차 출처 쓰기로 라우트 탐색 불가, 405 Allow 는 SOP 로 교차 출처가 못 읽고 OpenAPI 와 같은 정보 → 수용. (4) 정적 모르는 경로 404·SPA 폴백 없음 적절. (5) 쓰기 가드 GET/HEAD/OPTIONS 외 전 메서드·경로 무관, Content-Type 복수 거부, 미디어 타입 정확 일치 확인. FAIL 사유: §11 이 'SSE GET' 에만 출처 검사를 건다고 쓰는데 sse-events.md §1 은 'GET·HEAD 외 405' 로 HEAD 를 허용 → HEAD 가 스트림 핸들러에 닿으면(Starlette StreamingResponse 는 HEAD 에도 제너레이터를 돌림) 출처 검사 없이 슬롯을 잡는 우회로(교차 출처 fetch HEAD no-cors 는 단순 요청). 미검증 추정이라 보수적 FAIL | [architecture] ADR-011 §11·sse-events.md §1: 출처 검사를 메서드 무관 경로 `/api/v1/events` 기준으로 걸거나 HEAD 를 405 로 명시(어느 쪽이든 슬롯 잡는 모든 메서드가 검사 뒤). 같은 수정에서 Origin·Sec-Fetch-Site 헤더 복수면 거부(Host·Content-Type 과 동일), Sec-Fetch-Site 값 소문자 정확 일치 명시 권장. T-005/T-022 접기: 동의(아래 §5 조건) |
