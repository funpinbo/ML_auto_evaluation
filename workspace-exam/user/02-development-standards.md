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
| Backend | Python 3.11+ | FastAPI + uvicorn | pip + requirements.txt |
| Frontend | TypeScript 5 | Vue 3 + Vite, 차트 ECharts | npm (프론트 수정 시에만 필요) |
| Data | Python (표준 라이브러리) | - | - |
| Infra | N/A (로컬 실행, 인프라 없음) | | |

## 2. 코드 스타일
- **Formatter / Linter:** Backend ruff format + ruff check / Frontend eslint + prettier
- **네이밍 규칙:** Python 파일·함수 snake_case, 클래스 PascalCase / Vue 컴포넌트 PascalCase.vue, composable useXxx.ts
- **타입:** Python type hint 필수, API 입출력은 Pydantic 모델 / TypeScript strict mode
- **주석/문서화:** public 함수 docstring, 주석은 "왜"만
- **최대 함수 길이 / 복잡도:** <!-- 선택 -->

## 3. 디렉토리 구조 규칙
```
monitor/
  backend/app/     # FastAPI (api/ 라우터, services/ 파일 읽기·집계, models/ Pydantic)
  backend/tests/
  frontend/src/    # Vue (views/, components/panels/, api/)
  frontend/dist/   # 빌드 결과 — 저장소에 포함 (사용자는 Node 불필요)
run.py             # 원클릭 실행 (설치 + 서버 + 브라우저)
run.bat / run.sh   # run.py 래퍼
```

## 4. Git 전략
- **브랜치 전략:** 작업 브랜치 → main (PR)
- **커밋 메시지:** Conventional Commits — feat:, fix:, docs:, chore:, test:
- **PR 규칙:** 테스트 통과 필수, frontend 소스를 바꾸면 dist 재빌드 결과를 같은 PR 에 포함
- **머지 방식:** squash

## 5. 테스트 표준
- **테스트 도구:** pytest (+ FastAPI TestClient), vitest
- **커버리지 기준:** backend 라인 70% 이상
- **필수 테스트 종류:** backend 단위 + API 테스트, 일시정지/재개 시나리오 테스트, 깨진 파일·빈 workspace 테스트
- **테스트 데이터 규칙:** 실제 `~/.claude` 기록을 테스트에 쓰지 않는다. fixture 로 만든 가짜 기록만 사용

## 6. API 규칙
- **스타일:** REST + OpenAPI (FastAPI 자동 생성 명세를 `workspace/project/contracts/openapi.json` 으로 내보냄), 실시간 갱신은 SSE
- **버저닝:** `/api/v1` 경로
- **에러 응답 포맷:** {"error": {"code": "STRING_CODE", "message": "사람이 읽는 메시지"}}
- **인증/인가:** 없음 (127.0.0.1 바인딩으로 대체)

## 7. 에러 처리 & 로깅
- **로깅 포맷:** 콘솔 텍스트 로그 (시각, 레벨, 메시지)
- **로그 레벨 기준:** ERROR=패널을 못 그림, WARN=파일 누락·형식 오류로 일부 생략
- **금지:** Claude 대화 내용, 토큰/키를 로그에 출력하지 않는다

## 8. 보안 코딩
- **비밀값 관리:** 비밀값을 쓰지 않는다. `~/.claude` 의 인증 파일은 절대 읽지 않는다
- **입력 검증:** 모든 API 입력은 Pydantic 으로 검증, 파일 경로를 요청에서 받지 않는다
- **의존성 취약점 점검:** pip-audit, npm audit (릴리스 전 수동)

## 9. 의존성 관리
- **새 라이브러리 도입 기준:** 표준 라이브러리로 안 되는 경우만. MIT/Apache/BSD 라이선스, 최근 1년 내 릴리스. requirements.txt 는 버전 고정

## 10. Definition of Done (공통)
- [ ] 테스트 작성 및 통과 (pytest / vitest)
- [ ] ruff, eslint, 타입 검사 통과
- [ ] frontend 변경 시 dist 재빌드 포함
- [ ] 관련 문서 갱신
- [ ] `run.bat` / `run.sh` 로 실행해 화면 확인

## 11. AI Agent 작업 규칙
- **Agent 가 사람 승인 없이 하면 안 되는 일:** `~/.claude` 안의 파일 수정·삭제, 사용자 전역 설정(`~/.claude/settings.json`) 변경, 패키지 전역 설치
- **변경 단위:** 한 Task = 한 커밋 묶음
- **불확실할 때:** 추측하지 말고 STM 에 질문으로 남기고 blocked 처리
