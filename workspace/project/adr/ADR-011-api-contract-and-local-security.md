---
adr: 011
title: API 계약 규칙과 로컬 보안 가드 (응답 봉투·에러 포맷·Host/Origin)
status: proposed
date: 2026-10-23
author: architecture-analyst
related: [NFR-002, NFR-003, CON-02, CON-05, QS-05, 02 §6, 02 §8, 03 §2, 03 §3, 03 §8, D-12, D-14, D-18, D-20, D-25, I-14]
---
# ADR-011. API 계약 규칙과 로컬 보안 가드

## Context
- 02 §6: REST + OpenAPI(→ `workspace/project/contracts/openapi.json`), `/api/v1`, 에러 `{"error": {"code", "message"}}`, 인증 없음(127.0.0.1 바인딩). 02 §8: 모든 입력 Pydantic 검증, 요청에서 파일 경로를 받지 않음.
- NFR-002: 파일 없음·깨짐에도 서버 생존, 해당 패널에만 안내. 패널은 서로 독립적으로 그려야 한다.
- 127.0.0.1 바인딩만으로는 브라우저 기반 공격(DNS rebinding, 다른 사이트의 form POST)이 남는다. 유일한 쓰기 API 가 `POST /control/pause|resume` 이다.

## Decision
1. **응답 봉투(조회 API)**: `{"data": T | null, "meta": {"status": "ok"|"partial"|"empty"|"error"|"warming", "warnings": [str], "error": {"code","message"} | null, "generated_at", "source_mtime"}}`. 데이터 소스 문제는 HTTP 200 + `meta.status`. 패널 단위 실패가 다른 패널·HTTP 상태에 영향을 주지 않는다.
2. **요청 오류**는 HTTP 상태 + `{"error":{"code","message"}}`. FastAPI 기본 422 본문(`detail`)을 `VALIDATION_ERROR` 로 바꾸는 예외 핸들러, 처리되지 않은 예외는 `INTERNAL_ERROR` 500(메시지에 경로·내용 미포함, 로그에는 예외 종류만). 프레임워크 기본 오류의 매핑 규칙은 9번 표가 단일 기준이다. **Starlette/FastAPI 기본 본문 `{"detail": ...}` 와 평문 `Not Found`/`Method Not Allowed` 본문은 어떤 경로에서도 금지**(앱이 만든 응답 기준 0건).
3. **입력**: 쿼리·본문은 enum/범위가 있는 Pydantic 모델(`range`, `bucket`, `group`, `team`(정규식 `^[a-z][a-z0-9-]{1,30}$`), `status`, `limit ≤ 200`, `max_pause_sec 600~86400`). 파일 경로·임의 문자열 경로 파라미터 없음.
4. **Host 가드 (호스트 + 포트 검사, T-021 확정 / T-025 보강)**: `Host` 헤더가 **정확히 1개**이고 그 값이 정확히 `127.0.0.1:<bound port>` 또는 `localhost:<bound port>` 일 때만 통과, 그 밖에는 400 `BAD_HOST`(DNS rebinding 차단, QS-05 문구와 일치). GET·POST·SSE·정적 dist 를 포함한 모든 HTTP 요청에 적용(존재하지 않는 경로 포함 — 404/405 보다 먼저).
   - **개수 판정**: 가드가 ASGI `scope["headers"]` 에서 이름이 `host`(바이트 소문자 비교)인 항목 수를 직접 센다. 0개·2개 이상(같은 값 중복 포함)은 거부. 서버 파서(h11/uvicorn)의 병합·거부 동작에 의존하지 않는다(D-25).
   - **값 판정**: 값을 latin-1 로 디코드 → `strip()` → 소문자화 후 허용 집합과 **문자열 정확 일치**만 허용. 파싱(`urlsplit`, `int(port)` 등)으로 정규화하지 않으므로 다음은 모두 자동으로 거부된다 — 선행 0 포트(`127.0.0.1:08765`), userinfo(`user@127.0.0.1:<port>`), 추가 세그먼트(`127.0.0.1:<port>:x`), 접두·접미 일치, 포트 생략, 다른 포트, `[::1]`, 끝 점, 빈 값.
   - 케이스 정의는 `security/privacy.md` §5.1 **H-01~H-22** 가 단일 출처다(D-25). 이 ADR 은 규칙만 정하고 케이스를 다시 정의하지 않는다.
   - 근거: 보안은 품질 속성 2순위(03 §2)이고 03 §8 "127.0.0.1 바인딩" 을 브라우저 경로까지 지키려면 포트까지 보는 편이 엄격하다(같은 PC 의 다른 로컬 서비스 포트로 향한 rebinding/혼동 요청 거부). 서버는 자기 바인딩 포트를 설정으로 이미 안다. 구현은 20줄 안팎의 표준 라이브러리 코드라 새 의존성이 없다(원칙 3).
   - 구현: Starlette `TrustedHostMiddleware` 는 포트를 떼고 호스트만 비교하므로 **쓰지 않는다**. 대신 `app/security.py` 에 순수 ASGI 미들웨어(`HostGuardMiddleware`)를 두고 앱 팩토리 `create_app(settings)` 가 **가장 바깥**에 등록한다. 허용 집합 = `{f"127.0.0.1:{settings.port}", f"localhost:{settings.port}"}`. 비교 규칙: 헤더값 `strip()` 후 소문자화, 정확 일치만 허용(접두·접미 일치 금지 → `localhost.evil.com:<port>` 거부, 끝 점 `localhost.:<port>` 거부). 포트 생략(`127.0.0.1`, 기본 80 의미), 다른 포트, 빈/누락 Host, `[::1]`(IPv6 미바인딩)은 거부. 거부 응답은 2번과 같은 `{"error":{"code":"BAD_HOST","message":...}}`, 메시지에 받은 Host 값을 넣지 않는다.
   - 포트 단일 출처: `settings.port` 는 uvicorn 바인딩과 Host·Origin 가드가 함께 쓰는 하나의 값이다. 런처가 빈 포트를 골라 다음 포트로 넘어가면(20 §4 런처) 그 실제 포트를 `--port`/환경변수로 서버에 넘기고, 앱은 그 값으로 가드를 만든다. 포트 0(임의 할당)은 허용하지 않는다(가드가 실제 포트를 알 수 없으므로). 값이 어긋나면 런처의 `/api/v1/health` 대기가 400 으로 즉시 실패해 드러난다.
   - 테스트 영향: `TestClient` 기본 Host(`testserver`)는 거부되므로 테스트는 `base_url="http://127.0.0.1:<fixture port>"` 로 만든다.
5. **쓰기 가드**: 메서드가 `GET`·`HEAD`·`OPTIONS` 가 **아닌** 모든 요청(경로 무관 — `POST /api/v1/nope`, `POST /` 포함)에 적용. `Content-Type: application/json` 필수(단순 form CSRF 차단) + `Origin` 헤더가 있으면 `http://127.0.0.1:<port>` 또는 `http://localhost:<port>` 와 정확히 같아야 함(`null` 거부), 아니면 403 `FORBIDDEN_ORIGIN`. CORS 미들웨어는 붙이지 않는다.
   - **비-JSON Content-Type 도 403 `FORBIDDEN_ORIGIN`** 으로 거부한다(D-14). `Content-Type` 누락, `application/x-www-form-urlencoded`, `multipart/form-data`, `text/plain` 등 미디어 타입이 `application/json` 이 아닌 상태 변경 요청 전부가 대상이며 `.control.json` 을 건드리기 전에 거부한다. 415 는 닫힌 에러 코드 집합(9번)에 없으므로 쓰지 않는다 — 415 응답은 계약 위반이다. 근거: 두 검사 모두 "브라우저 교차 출처 쓰기 차단" 이라는 한 가지 목적이라 코드 하나로 묶는다(20 §1 QS-05).
   - **미디어 타입 비교 (T-025)**: 헤더값에서 첫 `;` 앞 부분을 `strip()`·소문자화한 문자열이 `application/json` 과 **정확히 일치**할 때만 통과. 매개변수는 무시(`application/json; charset=utf-8` 통과), 대소문자 무시(`Application/JSON` 통과). `startswith`/`in` 비교 금지 — `application/jsonx`, `application/json-patch+json` 거부. Content-Type 헤더가 여러 개면 거부.
   - **순서**: 이 검사는 본문 파싱·Pydantic 검증(422)과 라우팅(404/405)보다 **먼저** 수행한다 → 비-JSON 본문 + `text/plain` 은 422 가 아니라 403. 케이스 정의는 `security/privacy.md` §5.2 **C-01~C-11** 이 단일 출처다(D-25).
   - `OPTIONS` 는 쓰기 가드 대상이 아니고 라우팅 단계에서 405 가 된다(9번). Origin 비교에 쓰는 `<port>` 는 4번과 같은 `settings.port` 다.
6. **보안 헤더**: `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `Content-Security-Policy: default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'`(ECharts 인라인 스타일 허용).
7. **OpenAPI**: `monitor/backend/scripts/export_openapi.py` 가 `app.openapi()` 를 `workspace/project/contracts/openapi.json` 으로 저장(정적 파일 경로 제외). 명세가 바뀌면 같은 Task 안에서 `aidlc/scripts/openapi_docs.py render` 로 `docs/api/reference.md` 재생성(CLAUDE.md). 깨지는 변경은 architecture 리뷰.
8. **로그·응답 금지 항목**: 대화 본문, 파일 경로(홈 디렉터리 포함), sessionId·requestId 원문, settings.json 내용.
9. **HTTP 에러 코드 (닫힌 집합, 20 §5 와 동일)**: `VALIDATION_ERROR`(422), `NOT_FOUND`(404), `METHOD_NOT_ALLOWED`(405, T-025 추가), `BAD_HOST`(400), `FORBIDDEN_ORIGIN`(403), `NO_ACTIVE_LOOP`(409), `TOO_MANY_STREAMS`(503, SSE 동시 연결 상한 초과 — `contracts/sse-events.md`, D-12), `CONTROL_WRITE_FAILED`(500), `INTERNAL_ERROR`(500). 새 코드를 더하려면 이 ADR 과 20 §5 를 함께 갱신한다. 상태 코드와 에러 코드는 1:1 (500 만 2개).
   - **프레임워크 기본 오류 매핑 (T-025)** — 앱은 `starlette.exceptions.HTTPException`(FastAPI `HTTPException` 의 부모) 과 `RequestValidationError`, `Exception` 에 핸들러를 등록해 아래로 바꾼다. 원래 상태 코드는 유지하고 본문만 바꾼다(아래 "그 밖" 행 제외).

     | 발생 원인 | 응답 |
     |-----------|------|
     | 라우트 없음 — `/api/...` 아래 모르는 경로(메서드 무관, `/api/v1` 밖의 `/api/v2/x` 포함) | 404 `NOT_FOUND` |
     | 정적 영역(`/api` 밖) GET/HEAD 에 해당 파일 없음(`/nope`, `/assets/nope.js`) | 404 `NOT_FOUND` (index.html 폴백 없음, 아래) |
     | 경로는 있으나 메서드가 다름 — `OPTIONS` 포함(`GET /api/v1/control/pause`, `POST /api/v1/health`, `OPTIONS /api/v1/control/pause`, `PUT /`) | 405 `METHOD_NOT_ALLOWED` + `Allow` 헤더(허용 메서드), `Access-Control-*` 헤더 0개 |
     | `RequestValidationError` (쿼리·본문 검증, 깨진 JSON 본문 포함) | 422 `VALIDATION_ERROR` — 메시지·본문에 입력 원문 미포함(`detail`/`input` 키 금지) |
     | 그 밖 프레임워크 `HTTPException` 4xx (앱 코드에서 발생시키지 않음 — 예상 외) | 422 `VALIDATION_ERROR` |
     | 그 밖 5xx `HTTPException`, 처리되지 않은 예외 | 500 `INTERNAL_ERROR` |
   - 앱 코드는 `HTTPException` 을 직접 쓰지 않고 닫힌 집합 코드를 가진 앱 예외(예: `AppError(code, status)`) 만 던진다.
   - **405 를 새 코드로 둔 근거**: 404 `NOT_FOUND` 로 접으면 상태↔코드 1:1 이 깨지거나(405+`NOT_FOUND`) HTTP 의미를 바꿔야 해서(경로가 있는데 404) 읽는 사람에게 혼동을 준다(03 §2 유지보수성 3순위, 02 §6 에러 포맷 정신). 새 의존성·코드량 증가는 없다(원칙 3). OPTIONS 를 별도 응답(204 등)으로 두지 않는 것은 CORS 를 두지 않는 결정(5번)과 같은 근거다 — preflight 가 실패해 교차 출처 쓰기가 막힌다.
   - **정적 dist 의 모르는 경로 → 404 (SPA 폴백 없음)**: 프론트는 뷰 1개, vue-router 없음(ADR-007)이라 history 경로가 존재하지 않는다. 폴백을 두면 오타 경로·`/assets/*` 누락이 200 HTML 로 숨겨져 dist 신선도 문제(R-07)가 늦게 드러난다. `/` 는 `index.html`(ADR-005 §2·§3 그대로).
   - **구현 주의 (결과가 계약, 방식은 backend)**: Starlette 라우터는 FULL 매치를 PARTIAL(메서드만 다름) 보다 우선하므로 `Mount("/", StaticFiles)` 를 라우터 목록에 두면 `POST /api/v1/health` 같은 405 대상이 정적 마운트로 넘어가고, `/api` 캐치올 라우트를 두면 405 가 404 로 바뀐다. 정적 서빙은 "어떤 라우트와도 맞지 않을 때" 경로(예: 라우터 기본 처리기)에 두고, `/api` 접두는 거기서 404 로 끝내는 방식을 권장한다. 위 표의 예시는 T-005 테스트로 고정한다. ADR-005 §2 의 "`/` 마운트" 는 이 결과(API 우선 + dist 서빙)를 뜻한다.
   - 서버(uvicorn/h11)가 ASGI 앱에 넘기기 전에 거부하는 잘못된 HTTP 메시지는 앱 응답이 아니므로 이 계약 범위 밖이다.
10. **ASGI scope 처리 (HostGuardMiddleware, T-025)**: `scope["type"]` 별로 —
   - `http`: 4번 Host 검사(그다음 5번·11번 가드).
   - `websocket`: Host 값과 무관하게 **항상 거부**. 앱에 WebSocket 엔드포인트가 없다(실시간은 SSE, 03 §3). `websocket.connect` 를 받은 뒤 accept 없이 `{"type": "websocket.close", "code": 1008}` 을 보낸다(핸드셰이크 거부 — 서버가 HTTP 403 으로 응답). 프로토콜상 JSON 에러 본문을 실을 수 없으므로 2번 에러 포맷의 유일한 예외로 둔다. 내부 앱을 호출하지 않는다.
   - `lifespan`: 검사 없이 그대로 내부 앱에 넘긴다(startup/shutdown — 감시기·캐시 데우기 시작에 필요).
   - 그 밖 타입: 내부 앱을 호출하지 않고 반환한다.
11. **SSE `GET /api/v1/events` 출처 검사 (T-025)**: 교차 출처 페이지가 `EventSource`/서브리소스로 연결을 열면 응답을 읽지 못해도 서버는 연결 끊김을 감지할 때까지(keep-alive 15초 주기) 슬롯을 잡고 있어 동시 연결 상한 8 을 소모시킬 수 있다(가용성, `TOO_MANY_STREAMS` 로 정상 대시보드가 폴링 폴백). 그래서 이 경로에 한해 슬롯을 잡기 **전에** 다음 중 하나라도 맞으면 403 `FORBIDDEN_ORIGIN`:
   - `Origin` 헤더가 있고 5번 허용 Origin 2개와 정확히 일치하지 않음(`null` 포함). 교차 출처 `EventSource` 는 CORS 모드라 브라우저가 항상 `Origin` 을 보낸다. 같은 출처 `EventSource` 는 보내지 않거나 허용값을 보낸다.
   - `Sec-Fetch-Site` 헤더가 있고 값이 `same-origin`·`none` 이 아님(`cross-site`, `same-site`). `<img src>` 같은 no-cors 서브리소스 요청은 `Origin` 을 보내지 않으므로 이 헤더로 막는다.
   - 두 헤더가 모두 없으면(curl 등 비브라우저, 구형 브라우저) 통과 — 잔여 위험으로 수용(상한 8 과 끊김 감지로 한정).
   - 순서: Host(400) → 이 검사(403) → 상한 검사(503) → 스트림 시작. 403 응답은 스트림이 아닌 JSON 에러 본문이다.
   - **다른 GET(조회 API·정적 dist)에는 적용하지 않는다**: 응답 읽기는 SOP 가 막고, 요청은 짧게 끝나며 mtime 캐시로 비용이 한정된다. no-cors GET 은 `Origin` 을 보내지 않아 Origin 검사로는 실효가 없고, 조회 API 는 읽기 전용(원칙 2)이라 무결성 위험이 없다. 단순함 유지(03 §2 개발 속도 1순위·원칙 3).
12. **처리 순서 (T-025, 모든 HTTP 요청 공통)** — 앞 단계에서 거부되면 뒤 단계는 실행되지 않는다:
   1. scope 분기(10번) — `lifespan` 통과, `websocket` 거부
   2. Host 가드(4번) → 400 `BAD_HOST`
   3. 출처·미디어 타입 가드(5번 쓰기 가드, 11번 SSE 출처) → 403 `FORBIDDEN_ORIGIN`
   4. 라우팅(9번 표) → 404 `NOT_FOUND` / 405 `METHOD_NOT_ALLOWED`
   5. 입력 검증 → 422 `VALIDATION_ERROR`
   6. 핸들러 → 200 / 409 `NO_ACTIVE_LOOP` / 503 `TOO_MANY_STREAMS` / 500 `CONTROL_WRITE_FAILED`·`INTERNAL_ERROR`
   - 1~3 은 순수 ASGI 미들웨어(가장 바깥 = Host 가드, 그 안 = 출처·미디어 타입 가드)라 라우팅보다 먼저 돈다. 6번 보안 헤더는 거부 응답을 포함한 모든 응답에 붙는다(websocket 거부 제외).

## Alternatives
- **소스 오류를 HTTP 503 + 에러 포맷으로**: 02 형식에 더 직접적이지만 프론트가 패널별로 "부분 데이터"(예: 토큰은 있고 한도는 없음)를 표현하기 어렵다. 봉투 안 `meta.error` 도 같은 `{code, message}` 형식이라 규칙 정신 유지. 기각.
- **Host 가드에 Starlette `TrustedHostMiddleware` 사용(포트 무시)**: 내장이라 코드가 없지만 포트를 보지 않아 QS-05 의 `127.0.0.1:<port>` 기준을 만족하지 못하고, 같은 PC 의 다른 포트로 향한 Host 도 통과시킨다. 자체 미들웨어도 표준 라이브러리만 쓰는 수십 줄이라 비용 차이가 작다. 기각(T-021).
- **비-JSON Content-Type 을 415 로 응답**: HTTP 의미상 자연스럽지만 에러 코드 집합이 늘고, 같은 CSRF 방어 항목이 두 코드로 갈라진다. 기각(D-14).
- **405 를 404 `NOT_FOUND` 로 접기(코드 추가 없음)**: 집합이 그대로지만 상태↔코드 대응이 깨지거나 HTTP 의미가 바뀐다. 기각(T-025).
- **정적 영역 SPA 폴백(모르는 경로 → index.html)**: history 라우팅이 없는 앱이라 이득이 없고 404 를 숨긴다. 기각(T-025).
- **모든 GET 에 Origin/Sec-Fetch-Site 검사**: no-cors 부하 요청까지 줄이지만 읽기 전용 조회에 무결성 이득이 없고 규칙·테스트 표면이 커진다. SSE 슬롯처럼 한정 자원을 잡는 경로에만 적용. 기각(T-025).
- **WebSocket scope 를 내부 앱에 통과**: 엔드포인트가 없어 라우터가 닫겠지만 Host 검사 없이 앱 안쪽까지 들어간다. 가장 바깥에서 거부. 기각(T-025).
- **토큰 기반 인증(실행 시 난수 토큰 URL)**: CSRF 를 더 강하게 막지만 02 §6 "인증 없음" 과 다르고 사용 흐름이 복잡해짐. Host/Origin 가드로 충분. 기각.

## Consequences
- (+) 패널 독립성(NFR-002)과 02 에러 포맷을 함께 만족.
- (+) 로컬 웹 공격면 축소(QS-05).
- (−) 모든 조회 모델이 봉투 제네릭을 가져야 해 Pydantic 모델이 약간 장황 → `Envelope[T]` 제네릭 하나로 통일.
- (−) Host 가드가 포트까지 보므로 서버가 실제 바인딩 포트를 설정으로 정확히 받아야 한다(런처·config 책임, 4번 "포트 단일 출처").
- 테스트(qa): privacy.md §5.1 H-01~H-22·§5.2 C-01~C-11 전 케이스, 422 변환, 9번 매핑 표 예시(404·405·OPTIONS, 본문에 `detail` 키 0건), websocket scope 거부·lifespan 통과(ASGI scope 직접 구성), SSE 교차 출처(`Origin: http://evil.example`, `Sec-Fetch-Site: cross-site`) 403 이 슬롯을 소모하지 않음, 12번 순서(예: 잘못된 Host + 모르는 경로 → 400, `text/plain` + 깨진 본문 → 403), 패널 오류 격리, SSE 상한 초과 503 `TOO_MANY_STREAMS`, 응답에 경로·ID 문자열 미포함.
- (−) 에러 코드가 9개로 늘어(`METHOD_NOT_ALLOWED`) 프론트·OpenAPI 의 에러 코드 enum 이 함께 바뀐다(추가만 — 하위 호환).

## 변경 이력
- 2026-10-23 T-021: §4 Host 가드 포트 검사 확정(자체 ASGI 미들웨어), §5 비-JSON Content-Type → 403 `FORBIDDEN_ORIGIN` 명시(D-14), §9 에러 코드 집합에 `TOO_MANY_STREAMS`(503) 추가(I-02 중 에러 코드 부분).
- 2026-10-23 T-025 (I-14): §9 에 `METHOD_NOT_ALLOWED`(405) 추가와 프레임워크 기본 오류 매핑 표(404·405·OPTIONS·422·500, `detail` 본문 금지, 정적 모르는 경로 404·SPA 폴백 없음), §10 ASGI scope 처리(websocket 거부·lifespan 통과), §11 SSE GET 출처 검사(Origin·Sec-Fetch-Site → 403, 슬롯 소모 방지, 다른 GET 미적용), §12 처리 순서, §4 Host 개수 1개·정확 일치로 선행 0·userinfo·추가 세그먼트 거부, §5 쓰기 가드 범위(GET/HEAD/OPTIONS 외 전 메서드)·미디어 타입 대소문자 무시 정확 일치·422/404 보다 먼저 403. 케이스 정의는 privacy.md §5.1·§5.2 참조(D-25).
