---
adr: 011
title: API 계약 규칙과 로컬 보안 가드 (응답 봉투·에러 포맷·Host/Origin)
status: proposed
date: 2026-10-23
author: architecture-analyst
related: [NFR-002, NFR-003, CON-02, CON-05, QS-05, 02 §6, 02 §8, 03 §2, 03 §8, D-12, D-14]
---
# ADR-011. API 계약 규칙과 로컬 보안 가드

## Context
- 02 §6: REST + OpenAPI(→ `workspace/project/contracts/openapi.json`), `/api/v1`, 에러 `{"error": {"code", "message"}}`, 인증 없음(127.0.0.1 바인딩). 02 §8: 모든 입력 Pydantic 검증, 요청에서 파일 경로를 받지 않음.
- NFR-002: 파일 없음·깨짐에도 서버 생존, 해당 패널에만 안내. 패널은 서로 독립적으로 그려야 한다.
- 127.0.0.1 바인딩만으로는 브라우저 기반 공격(DNS rebinding, 다른 사이트의 form POST)이 남는다. 유일한 쓰기 API 가 `POST /control/pause|resume` 이다.

## Decision
1. **응답 봉투(조회 API)**: `{"data": T | null, "meta": {"status": "ok"|"partial"|"empty"|"error"|"warming", "warnings": [str], "error": {"code","message"} | null, "generated_at", "source_mtime"}}`. 데이터 소스 문제는 HTTP 200 + `meta.status`. 패널 단위 실패가 다른 패널·HTTP 상태에 영향을 주지 않는다.
2. **요청 오류**는 HTTP 상태 + `{"error":{"code","message"}}`. FastAPI 기본 422 본문(`detail`)을 `VALIDATION_ERROR` 로 바꾸는 예외 핸들러, 처리되지 않은 예외는 `INTERNAL_ERROR` 500(메시지에 경로·내용 미포함, 로그에는 예외 종류만).
3. **입력**: 쿼리·본문은 enum/범위가 있는 Pydantic 모델(`range`, `bucket`, `group`, `team`(정규식 `^[a-z][a-z0-9-]{1,30}$`), `status`, `limit ≤ 200`, `max_pause_sec 600~86400`). 파일 경로·임의 문자열 경로 파라미터 없음.
4. **Host 가드 (호스트 + 포트 검사, T-021 확정)**: `Host` 헤더가 정확히 `127.0.0.1:<bound port>` 또는 `localhost:<bound port>` 일 때만 통과, 그 밖에는 400 `BAD_HOST`(DNS rebinding 차단, QS-05 문구와 일치). GET·POST·SSE·정적 dist 를 포함한 모든 HTTP 요청에 적용.
   - 근거: 보안은 품질 속성 2순위(03 §2)이고 03 §8 "127.0.0.1 바인딩" 을 브라우저 경로까지 지키려면 포트까지 보는 편이 엄격하다(같은 PC 의 다른 로컬 서비스 포트로 향한 rebinding/혼동 요청 거부). 서버는 자기 바인딩 포트를 설정으로 이미 안다. 구현은 20줄 안팎의 표준 라이브러리 코드라 새 의존성이 없다(원칙 3).
   - 구현: Starlette `TrustedHostMiddleware` 는 포트를 떼고 호스트만 비교하므로 **쓰지 않는다**. 대신 `app/security.py` 에 순수 ASGI 미들웨어(`HostGuardMiddleware`)를 두고 앱 팩토리 `create_app(settings)` 가 **가장 바깥**에 등록한다. 허용 집합 = `{f"127.0.0.1:{settings.port}", f"localhost:{settings.port}"}`. 비교 규칙: 헤더값 `strip()` 후 소문자화, 정확 일치만 허용(접두·접미 일치 금지 → `localhost.evil.com:<port>` 거부, 끝 점 `localhost.:<port>` 거부). 포트 생략(`127.0.0.1`, 기본 80 의미), 다른 포트, 빈/누락 Host, `[::1]`(IPv6 미바인딩)은 거부. 거부 응답은 2번과 같은 `{"error":{"code":"BAD_HOST","message":...}}`, 메시지에 받은 Host 값을 넣지 않는다.
   - 포트 단일 출처: `settings.port` 는 uvicorn 바인딩과 Host·Origin 가드가 함께 쓰는 하나의 값이다. 런처가 빈 포트를 골라 다음 포트로 넘어가면(20 §4 런처) 그 실제 포트를 `--port`/환경변수로 서버에 넘기고, 앱은 그 값으로 가드를 만든다. 포트 0(임의 할당)은 허용하지 않는다(가드가 실제 포트를 알 수 없으므로). 값이 어긋나면 런처의 `/api/v1/health` 대기가 400 으로 즉시 실패해 드러난다.
   - 테스트 영향: `TestClient` 기본 Host(`testserver`)는 거부되므로 테스트는 `base_url="http://127.0.0.1:<fixture port>"` 로 만든다.
5. **쓰기 가드**: POST 는 `Content-Type: application/json` 필수(단순 form CSRF 차단) + `Origin` 헤더가 있으면 `http://127.0.0.1:<port>` 또는 `http://localhost:<port>` 와 같아야 함, 아니면 403 `FORBIDDEN_ORIGIN`. CORS 미들웨어는 붙이지 않는다.
   - **비-JSON Content-Type 도 403 `FORBIDDEN_ORIGIN`** 으로 거부한다(D-14). `Content-Type` 누락, `application/x-www-form-urlencoded`, `multipart/form-data`, `text/plain` 등 미디어 타입이 `application/json` 이 아닌 상태 변경 요청 전부가 대상이며 `.control.json` 을 건드리기 전에 거부한다. 매개변수는 허용(`application/json; charset=utf-8` 통과). 415 는 닫힌 에러 코드 집합(9번)에 없으므로 쓰지 않는다 — 415 응답은 계약 위반이다. 근거: 두 검사 모두 "브라우저 교차 출처 쓰기 차단" 이라는 한 가지 목적이라 코드 하나로 묶는다(20 §1 QS-05).
   - Origin 비교에 쓰는 `<port>` 는 4번과 같은 `settings.port` 다.
6. **보안 헤더**: `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `Content-Security-Policy: default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'`(ECharts 인라인 스타일 허용).
7. **OpenAPI**: `monitor/backend/scripts/export_openapi.py` 가 `app.openapi()` 를 `workspace/project/contracts/openapi.json` 으로 저장(정적 파일 경로 제외). 명세가 바뀌면 같은 Task 안에서 `aidlc/scripts/openapi_docs.py render` 로 `docs/api/reference.md` 재생성(CLAUDE.md). 깨지는 변경은 architecture 리뷰.
8. **로그·응답 금지 항목**: 대화 본문, 파일 경로(홈 디렉터리 포함), sessionId·requestId 원문, settings.json 내용.
9. **HTTP 에러 코드 (닫힌 집합, 20 §5 와 동일)**: `VALIDATION_ERROR`(422), `NOT_FOUND`(404), `BAD_HOST`(400), `FORBIDDEN_ORIGIN`(403), `NO_ACTIVE_LOOP`(409), `TOO_MANY_STREAMS`(503, SSE 동시 연결 상한 초과 — `contracts/sse-events.md`, D-12), `CONTROL_WRITE_FAILED`(500), `INTERNAL_ERROR`(500). 새 코드를 더하려면 이 ADR 과 20 §5 를 함께 갱신한다.

## Alternatives
- **소스 오류를 HTTP 503 + 에러 포맷으로**: 02 형식에 더 직접적이지만 프론트가 패널별로 "부분 데이터"(예: 토큰은 있고 한도는 없음)를 표현하기 어렵다. 봉투 안 `meta.error` 도 같은 `{code, message}` 형식이라 규칙 정신 유지. 기각.
- **Host 가드에 Starlette `TrustedHostMiddleware` 사용(포트 무시)**: 내장이라 코드가 없지만 포트를 보지 않아 QS-05 의 `127.0.0.1:<port>` 기준을 만족하지 못하고, 같은 PC 의 다른 포트로 향한 Host 도 통과시킨다. 자체 미들웨어도 표준 라이브러리만 쓰는 수십 줄이라 비용 차이가 작다. 기각(T-021).
- **비-JSON Content-Type 을 415 로 응답**: HTTP 의미상 자연스럽지만 에러 코드 집합이 늘고, 같은 CSRF 방어 항목이 두 코드로 갈라진다. 기각(D-14).
- **토큰 기반 인증(실행 시 난수 토큰 URL)**: CSRF 를 더 강하게 막지만 02 §6 "인증 없음" 과 다르고 사용 흐름이 복잡해짐. Host/Origin 가드로 충분. 기각.

## Consequences
- (+) 패널 독립성(NFR-002)과 02 에러 포맷을 함께 만족.
- (+) 로컬 웹 공격면 축소(QS-05).
- (−) 모든 조회 모델이 봉투 제네릭을 가져야 해 Pydantic 모델이 약간 장황 → `Envelope[T]` 제네릭 하나로 통일.
- (−) Host 가드가 포트까지 보므로 서버가 실제 바인딩 포트를 설정으로 정확히 받아야 한다(런처·config 책임, 4번 "포트 단일 출처").
- 테스트(qa): 잘못된 Host(포트 생략·포트 불일치 `127.0.0.1:1` 포함)/Origin/Content-Type 거부(비-JSON 은 403 `FORBIDDEN_ORIGIN`, 415 아님), 422 변환, 패널 오류 격리, SSE 상한 초과 503 `TOO_MANY_STREAMS`, 응답에 경로·ID 문자열 미포함.

## 변경 이력
- 2026-10-23 T-021: §4 Host 가드 포트 검사 확정(자체 ASGI 미들웨어), §5 비-JSON Content-Type → 403 `FORBIDDEN_ORIGIN` 명시(D-14), §9 에러 코드 집합에 `TOO_MANY_STREAMS`(503) 추가(I-02 중 에러 코드 부분).
