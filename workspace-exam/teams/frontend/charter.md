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
- 프로젝트 적용: 01 §5.1 흐름 2~4 의 브라우저 대시보드, 20 §4 프론트 앱 셸 & 레이아웃·패널 컴포넌트·API 클라이언트 & 실시간의 소유 팀이 frontend → create_when "웹 UI" 충족. 40 §2 에서 design(화면 명세) 책임을 인수 (40 §1)

## 2. 책임 범위
**소유 (Owns)**
- 웹 클라이언트 코드 (예: web/, apps/web)
- UI 컴포넌트 라이브러리
- 프론트엔드 단위·컴포넌트 테스트
- (design 인수) 화면 명세 `workspace/project/design/` — 레이아웃, 패널별 empty/error/warming 상태, 문구
- 빌드 산출물 `monitor/frontend/dist/**` (커밋, ADR-005)

**하지 않음 (Not owns)**
- API 구현
- 디자인 결정 — 단, design 팀 미생성으로 화면 명세(`workspace/project/design/`)는 frontend 가 작성하고 product 가 수용 기준 관점에서 리뷰한다 (40 §2)

- 프로젝트 적용 (실제 디렉토리/컴포넌트):
  - `monitor/frontend/src/**` — `App.vue`, `views/DashboardView.vue`, `components/panels/*.vue`, `api/client.ts`·`types.ts`, `composables/useEventStream.ts`·`usePanel.ts`, colocated `*.spec.ts`
  - `monitor/frontend/dist/**` (`.build-meta.json` 포함)
  - `monitor/frontend/index.html`, `vite.config.ts`, `tsconfig*.json`, `eslint.config.*`, `.prettierrc*`
  - `workspace/project/design/` (design 인수)
  - **하지 않음:** `package.json`·`package-lock.json`(cicd), `monitor/frontend/tests/`(qa)

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
| FR-001 | Pipeline/Gate 패널 (첫 화면 상단 KPI-01 행) | P1 |
| FR-002 | Plan 진행률 바 + Task 표(팀·상태 필터) | P1 |
| FR-003 | Memory/cascade 패널(현재 Task·팀·경과 시간) | P1 |
| FR-004 | 사용량 패널: 5h·7d 게이지, 토큰 시계열 스택 차트, 모델별 표, "한도 정보 없음" 안내 | P1 |
| FR-005 | 루프 제어 버튼·상태(running/pause_requested/paused/resume_requested/no_session/ended) | P1 |
| FR-008 | EventSource 구독 → topic 별 재조회, 실패 시 5초 폴링 폴백 | P1(최소) / P2(전 패널) |
| NFR-001 | 첫 화면 ≤ 2초 (트리 셰이킹 ECharts, 패널 먼저 그리기) | P1 |
| FR-006 / FR-007 / FR-009 / FR-010 | Timeline, Teams, 비용 stat, 상단 경고 배너 | P2 |

## 6. 협업 인터페이스
- design: 명세 확인
- backend: API 계약
- qa: E2E 셀렉터·테스트 ID 합의

| 방향 | 상대 팀 | 계약 | 위치 |
|------|---------|------|------|
| 사용 | backend | REST + SSE 계약 | `workspace/project/contracts/openapi.json`, `sse-events.md` |
| 사용 | product | 화면 흐름·상태 문구 | `workspace/project/stories/` |
| 제공 | cicd | dist + `.build-meta.json` | `monitor/frontend/dist/` |
| 협의 | qa | `data-testid` 규칙, fixture 응답 | `monitor/frontend/tests/fixtures/` |

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
- 언어/프레임워크: TypeScript 5 strict, Vue 3.5 (Composition API, `<script setup>`), Vite 8, ECharts 6 (`echarts/core` 모듈 import). 라우터·상태관리·차트 래퍼 라이브러리 없음(ADR-007)
- 디렉토리: 위 "프로젝트 적용" 목록. 컴포넌트 PascalCase.vue, composable useXxx.ts
- 테스트 명령: `cd monitor/frontend && npm test` (vitest), `npm run lint`, `npx vue-tsc --noEmit`, 빌드 `npm run build` → dist 를 같은 커밋에 포함
- 규칙: CDN·웹폰트·외부 URL 로드 0건(QS-13). Grafana 스타일 다크 테마, 12열 패널 그리드
