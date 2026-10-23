---
adr: 011
title: API 계약 규칙과 로컬 보안 가드 (응답 봉투·에러 포맷·Host/Origin)
status: proposed
date: 2026-10-23
author: architecture-analyst
related: [NFR-002, NFR-003, CON-02, CON-05, 02 §6, 02 §8, 03 §8]
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
4. **Host 가드**: Starlette `TrustedHostMiddleware(allowed_hosts=["127.0.0.1", "localhost"])` → 다른 Host 는 400 `BAD_HOST`(DNS rebinding 차단).
5. **쓰기 가드**: POST 는 `Content-Type: application/json` 필수(단순 form CSRF 차단) + `Origin` 헤더가 있으면 `http://127.0.0.1:<port>` 또는 `http://localhost:<port>` 와 같아야 함, 아니면 403 `FORBIDDEN_ORIGIN`. CORS 미들웨어는 붙이지 않는다.
6. **보안 헤더**: `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `Content-Security-Policy: default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'`(ECharts 인라인 스타일 허용).
7. **OpenAPI**: `monitor/backend/scripts/export_openapi.py` 가 `app.openapi()` 를 `workspace/project/contracts/openapi.json` 으로 저장(정적 파일 경로 제외). 명세가 바뀌면 같은 Task 안에서 `aidlc/scripts/openapi_docs.py render` 로 `docs/api/reference.md` 재생성(CLAUDE.md). 깨지는 변경은 architecture 리뷰.
8. **로그·응답 금지 항목**: 대화 본문, 파일 경로(홈 디렉터리 포함), sessionId·requestId 원문, settings.json 내용.

## Alternatives
- **소스 오류를 HTTP 503 + 에러 포맷으로**: 02 형식에 더 직접적이지만 프론트가 패널별로 "부분 데이터"(예: 토큰은 있고 한도는 없음)를 표현하기 어렵다. 봉투 안 `meta.error` 도 같은 `{code, message}` 형식이라 규칙 정신 유지. 기각.
- **토큰 기반 인증(실행 시 난수 토큰 URL)**: CSRF 를 더 강하게 막지만 02 §6 "인증 없음" 과 다르고 사용 흐름이 복잡해짐. Host/Origin 가드로 충분. 기각.

## Consequences
- (+) 패널 독립성(NFR-002)과 02 에러 포맷을 함께 만족.
- (+) 로컬 웹 공격면 축소(QS-05).
- (−) 모든 조회 모델이 봉투 제네릭을 가져야 해 Pydantic 모델이 약간 장황 → `Envelope[T]` 제네릭 하나로 통일.
- 테스트(qa): 잘못된 Host/Origin/Content-Type 거부, 422 변환, 패널 오류 격리, 응답에 경로·ID 문자열 미포함.
