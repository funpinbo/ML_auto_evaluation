---
doc: development-standards
layer: user
version: 0.1
---
# 02. 개발 표준 정의서

> **작성자: 사용자.** 모든 팀 Agent 가 코드를 쓸 때 이 문서를 "법"으로 따릅니다.
> `{{ }}` = 필수. 팀 문서(`workspace/teams/*/charter.md`)는 이 문서를 팀 상황에 맞게 구체화만 하고, 어기지 못합니다.

## 1. 언어 & 런타임
| 영역 | 언어/버전 | 프레임워크 | 패키지 매니저 |
|------|-----------|------------|---------------|
| Backend | {{예: Python 3.12}} | {{예: FastAPI}} | {{예: uv}} |
| Frontend | {{예: TypeScript 5}} | {{예: Next.js 15}} | {{예: pnpm}} |
| Data | <!-- 예: Python, SQL, dbt --> | | |
| Infra | <!-- 예: Terraform --> | | |

## 2. 코드 스타일
- **Formatter / Linter:** {{예: ruff format + ruff check / eslint + prettier}}
- **네이밍 규칙:** {{예: 파일 snake_case, 클래스 PascalCase, 상수 UPPER_SNAKE}}
- **타입:** {{예: Python type hint 필수 + mypy strict / TS strict mode}}
- **주석/문서화:** <!-- 예: public 함수 docstring 필수, 주석은 "왜"만 -->
- **최대 함수 길이 / 복잡도:** <!-- 선택 -->

## 3. 디렉토리 구조 규칙
```
{{예:
src/
  api/        # 라우터
  domain/     # 비즈니스 로직 (프레임워크 의존 금지)
  infra/      # DB, 외부 API 어댑터
tests/
}}
```

## 4. Git 전략
- **브랜치 전략:** {{예: trunk-based, feature/* → main}}
- **커밋 메시지:** {{예: Conventional Commits — feat:, fix:, chore:}}
- **PR 규칙:** {{예: 리뷰 1명 이상 승인, CI 통과 필수, 400 라인 이하}}
- **머지 방식:** <!-- squash / rebase / merge -->

## 5. 테스트 표준
- **테스트 도구:** {{예: pytest, vitest, playwright}}
- **커버리지 기준:** {{예: 라인 80% 이상, 도메인 로직 90%}}
- **필수 테스트 종류:** {{예: 단위 + API 통합, 핵심 흐름 E2E}}
- **테스트 데이터 규칙:** <!-- 예: 실제 개인정보 사용 금지, fixture 사용 -->

## 6. API 규칙
- **스타일:** {{예: REST + OpenAPI 3.1}}
- **버저닝:** <!-- 예: /v1 경로 -->
- **에러 응답 포맷:** {{예: {"error": {"code": "...", "message": "..."}}}}
- **인증/인가:** <!-- 예: OAuth2 + JWT -->

## 7. 에러 처리 & 로깅
- **로깅 포맷:** {{예: JSON structured log, trace_id 포함}}
- **로그 레벨 기준:** <!-- 예: ERROR=사용자 영향, WARN=복구됨 -->
- **금지:** {{예: 개인정보/토큰 로그 출력 금지}}

## 8. 보안 코딩
- **비밀값 관리:** {{예: 환경변수 + Secret Manager, 코드 커밋 금지}}
- **입력 검증:** <!-- 예: 모든 외부 입력은 schema validation -->
- **의존성 취약점 점검:** <!-- 예: dependabot, pip-audit -->

## 9. 의존성 관리
- **새 라이브러리 도입 기준:** {{예: 라이선스 MIT/Apache, 최근 6개월 내 릴리스, ADR 작성}}

## 10. Definition of Done (공통)
<!-- 모든 Task 가 "완료"로 인정되기 위한 최소 조건. STM outcome: done 의 기준이 됩니다. -->
- [ ] {{예: 테스트 작성 및 통과}}
- [ ] {{예: lint/type check 통과}}
- [ ] 관련 문서 갱신
- [ ] 

## 11. AI Agent 작업 규칙
<!-- Agent 에게만 적용되는 추가 규칙 -->
- **Agent 가 사람 승인 없이 하면 안 되는 일:** {{예: DB 마이그레이션 실행, 운영 배포, 외부 API 키 생성}}
- **변경 단위:** <!-- 예: 한 Task = 한 PR -->
- **불확실할 때:** <!-- 예: 추측하지 말고 STM 에 질문으로 남기고 blocked 처리 -->
