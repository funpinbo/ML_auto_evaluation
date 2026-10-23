---
name: aidlc-docs
description: 프로젝트 문서(docs/)를 생성·갱신한다. API 가 있으면 OpenAPI 명세를 찾거나 코드에서 추출해 REST API 레퍼런스(엔드포인트·파라미터·스키마·curl 예시)와 API 가이드(인증·에러·페이지네이션·버저닝)를 만들고, 사용자 가이드를 작성한다.
disable-model-invocation: true
argument-hint: "[api|guide] (생략 시 전체)"
---
# /aidlc-docs — 6단계: 문서화

인자 `$ARGUMENTS`: `api` 면 API 문서만, `guide` 면 사용자 가이드만, 생략 시 전체.
`.claude/agents/team-docs.md` 가 있으면 2~5단계를 `team-docs` 에 **작업 모드**로 위임하고, 없으면 직접 수행한다.

## 출력 구조
```
docs/
  README.md          문서 인덱스
  api/README.md      API 가이드 (사람이 쓰는 개요) — 템플릿: aidlc/templates/docs/api-overview.md
  api/reference.md   REST API 레퍼런스 (자동 생성, 직접 수정 금지)
  guide/README.md    사용자 가이드 — 템플릿: aidlc/templates/docs/user-guide.md
docs/aidlc/          AI-DLC 프레임워크 자체 문서 (이 단계에서 건드리지 않음)
```

## 1. API 탐지
1. `python3 aidlc/scripts/openapi_docs.py detect` — OpenAPI 3.x 명세 파일 탐색 (`aidlc/examples/` 의 샘플은 제외하고 판단).
2. 명세가 없으면 코드에서 API 존재 여부를 Grep 으로 확인한다:
   | 프레임워크 | 탐지 패턴 |
   |-----------|-----------|
   | FastAPI / Flask | `@app.get(`, `@router.post(`, `APIRouter(`, `@app.route(` |
   | Express / NestJS | `router.get(`, `app.post(`, `@Controller(`, `@Get(` |
   | Spring | `@RestController`, `@GetMapping`, `@RequestMapping` |
   | Django REST | `APIView`, `ViewSet`, `urlpatterns` |
   | Go | `http.HandleFunc(`, `gin.Default()`, `echo.New()` |
3. 판정:
   - **명세 있음** → 2단계
   - **코드 API 있음, 명세 없음** → 명세를 만든다. 프레임워크가 자동 생성할 수 있으면 그걸 우선 사용한다 (예: FastAPI `app.openapi()` 를 JSON 으로 저장).
     불가능하면 라우트 코드를 읽어 `workspace/project/contracts/openapi.json` 초안을 직접 작성하고 `info.description` 에
     "코드에서 역추출한 초안 — architecture 검토 필요" 라고 표시한 뒤, STM 이나 보고에 `[architecture]` 검토 Task 후보로 남긴다.
   - **API 없음** → API 문서는 건너뛰고 그 사실을 `docs/README.md` 에 적는다.

## 2. REST API 레퍼런스 생성 (결정적)
`python3 aidlc/scripts/openapi_docs.py render <spec> -o docs/api`
→ `docs/api/reference.md`: 엔드포인트 목록, 인증, 파라미터/요청/응답 필드 표, JSON 예시, curl 예시, 스키마.
명세가 여러 개면 서비스별로 `-o docs/api/<service>` 로 나눈다.

## 3. API 가이드 작성
`aidlc/templates/docs/api-overview.md` 구조로 `docs/api/README.md` 를 쓴다. 근거:
- 명세(servers, securitySchemes, Error 스키마, 페이지네이션 파라미터, deprecated)
- `workspace/user/02-development-standards.md` §6 API 규칙
- `workspace/memory/long-term.md` 의 API 관련 결정/패턴
규칙: 명세와 표준이 다르면(예: 에러 포맷 불일치) 문서에 "불일치" 로 표시하고 `[architecture]` Task 후보로 남긴다. 추측으로 채우지 않는다.

## 4. 사용자 가이드 작성
`aidlc/templates/docs/user-guide.md` 구조로 `docs/guide/README.md`. **구현 완료된 FR**(tasks.md 에서 `[x]` 인 Task 의 FR)만 쓴다.

## 5. 인덱스
`docs/README.md`: 문서 목록과 대상 독자, 마지막 생성 시각, 사용한 명세 경로, 운영 문서(ops 팀의 runbooks/slo.md)가 있으면 링크.

## 6. 검증
1. `python3 aidlc/scripts/aidlc.py check docs` — 미작성 `{{ }}` 0 이어야 한다.
2. api/README.md 의 엔드포인트·상태 코드·에러 코드가 reference.md 와 일치하는지 대조한다.
3. 로컬 서버를 띄울 수 있으면 reference.md 의 인증 불필요 GET 예시 하나를 실제로 호출해 응답 형태를 확인한다. 못 하면 "미검증" 이라고 보고한다.

## 보고
생성/갱신한 파일, API 탐지 결과(명세 경로 또는 역추출 여부), 엔드포인트 수, 불일치 목록, 검증 결과.
