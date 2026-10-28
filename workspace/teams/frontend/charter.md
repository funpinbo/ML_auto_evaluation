---
doc: team-charter
layer: team
team: frontend
group: engineering
tier: conditional
status: draft
---
# Frontend 팀 Charter

> 팀 Agent(`.claude/agents/team-frontend.md`)가 작업 전 항상 읽는 문서입니다. `aidlc/teams/catalog.json` 기본값으로 생성되며,
> team-architect 가 프로젝트 분석서 근거로 구체화합니다 ("프로젝트 적용" 칸).
> 상위 문서와 충돌하면 user/02(개발 표준) > user/03(아키텍처 철학) > 이 문서 순으로 따릅니다.

## 1. 미션
디자인 명세와 API 계약을 바탕으로 웹 UI 를 구현하고 사용성·성능·접근성을 보장한다.

- 생성 근거: 웹 UI 또는 임베드 위젯이 있을 때
- 프로젝트 적용: 20§4 컴포넌트 표에서 Web UI(Jinja2+바닐라 JS)와 시각화 생성기(`visualize.py`, pandas+matplotlib) 2개 컴포넌트를 frontend 가 소유(40§1). design 팀이 없으므로(40§2) 화면 흐름·상태(로딩/오류/빈) 설계도 frontend 가 stories/FR-xxx.md 의 수용 기준을 바탕으로 직접 정의한다.

## 2. 책임 범위
**소유 (Owns)**
- 웹 클라이언트 코드 (예: web/, apps/web)
- UI 컴포넌트 라이브러리
- 프론트엔드 단위·컴포넌트 테스트

**하지 않음 (Not owns)**
- API 구현
- 디자인 결정

- 프로젝트 적용 (실제 디렉토리/컴포넌트): `app/web/`(Jinja2 템플릿: 업로드 폼, N:M 연결 화면, 지표 선택 UI, Run 버튼, 결과 화면 / 바닐라 JS / 정적 파일), `app/eval/visualize.py`(pandas `DataFrame.plot` + matplotlib Agg → PNG/base64, 20§4·§7). `app/api/`, `app/eval/engine.py` 등은 backend 소유(겹치지 않음).

## 3. 산출물
- 화면·컴포넌트 구현
- API 클라이언트 (계약에서 생성 권장)
- 컴포넌트/단위 테스트

## 4. 입력 문서
- workspace/project/design/
- workspace/project/contracts/
- workspace/project/stories/

## 5. 담당 요구사항
| FR/NFR | 내용 | Phase |
|--------|------|-------|
| FR-001 | N:M 연결 화면 | P1 |
| FR-002 | 업로드 폼(모델 framework/problem_type 선택 포함, 30§5.2) | P1 |
| FR-003 | 지표 선택 UI (호환 지표만 노출/비활성화, 30§5.2) | P1 최소 드롭다운 → P2 호환성 필터 UI 고도화 |
| FR-004 | Run 버튼 → `POST /runs` 호출 | P1 |
| FR-005 | 결과 화면: 지표 비교 그래프(P1), 상관관계 그래프(P2, 10§5) | P1/P2 |

## 6. 협업 인터페이스
- product: 화면 흐름 명세 확인(design 팀 부재 — 40§2 인수)
- backend: API 계약(20§5), 에러 응답 포맷
- qa: E2E 셀렉터·테스트 ID 합의

| 방향 | 상대 팀 | 계약 | 위치 |
|------|---------|------|------|
| backend → frontend | REST API 응답 스키마 | JSON (20§5) | `workspace/project/20-architecture-analysis.md` §5 |
| frontend → qa | `data-testid` 셀렉터 규칙 | HTML 속성 | `app/web/` 템플릿 내 주석으로 합의 기록 |

## 7. 팀 Definition of Done
- [ ] user/02 §10 공통 DoD
- [ ] 모든 화면 상태(로딩/오류/빈) 구현
- [ ] 접근성 lint 통과
- [ ] Core Web Vitals 기준 충족

## 8. 품질 지표
- LCP/INP/CLS
- 프론트 오류율
- 번들 크기

## 9. 리뷰 게이트 (다른 팀 Task 검증)
- 없음 (리뷰 게이트를 운영하지 않는 팀)

## 10. 팀 표준 (user/02 구체화)
- 언어/프레임워크: FastAPI 내장 Jinja2 템플릿 + 바닐라 JS, Node 빌드 없음(02§1). 차트는 서버사이드 pandas/matplotlib PNG 임베드 — 클라이언트 차트 JS 라이브러리 불필요(20§7)
- 디렉토리: `app/web/`(템플릿·정적 파일), `app/eval/visualize.py`
- 테스트 명령: `pytest`(선택, 02§5) — 수동 브라우저 확인이 기본 DoD(02§10 "기능이 수동 확인으로 동작함")
- 접근성/디자인 토큰: 공식 기준 없음(design 팀 미생성, 40§2) — 화면 상태(로딩/오류/빈)는 수동 확인으로 충분
