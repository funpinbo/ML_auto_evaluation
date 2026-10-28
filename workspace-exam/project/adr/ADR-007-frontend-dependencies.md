---
adr: 007
title: 프론트 외부 의존성 — Vue 3·ECharts 런타임 + Vite·TypeScript 개발 도구
status: proposed
date: 2026-10-23
author: architecture-analyst
related: [FR-001~010, CON-01, 원칙 3, 03 §4, 03 §9, 02 §1, 02 §2, 02 §5]
---
# ADR-007. 프론트 새 외부 의존성 (03 §9 필수)

## Context
- 02 §1: TypeScript 5, Vue 3 + Vite, 차트 ECharts, npm. 02 §2: eslint + prettier, TS strict, 컴포넌트 PascalCase.vue, composable useXxx.ts. 02 §5: vitest.
- 화면: Grafana 스타일 다크 대시보드 1개(패널 그리드, stat 타일, 5h/7d 게이지, 토큰 시계열, 표). 페이지 이동 거의 없음.
- 2026-10-23 확인: vue 3.5.44(MIT), vite 8.3.5(MIT, Node ^20.19 또는 ≥ 22.12), echarts 6.1.0(Apache-2.0), typescript latest 7.0.2(Apache-2.0) — 02 가 TS 5 를 지정하므로 5.x 로 고정.

## Decision
1. **런타임 의존성 2개**: `vue@3.5.44`, `echarts@6.1.0`. ECharts 는 `echarts/core` 에 GaugeChart, LineChart, BarChart, Grid/Tooltip/Legend/DataZoom 컴포넌트, CanvasRenderer 만 등록(트리 셰이킹).
2. **추가하지 않는 것**: vue-router(뷰 1개, 패널 접힘은 상태로), Pinia(composable `usePanel`·`useEventStream` 으로 충분), vue-echarts(얇은 `useChart.ts` composable 로 대체), axios(fetch), UI 키트(CSS 변수 다크 테마 직접), 날짜 라이브러리(`Intl.DateTimeFormat`).
3. **개발 의존성**: `vite@8.3.5`, `@vitejs/plugin-vue`, `typescript@~5`(5.x 마지막 안정판으로 고정, 정확한 버전은 구현 Task 에서 `package-lock.json` 에 기록), `vue-tsc`(TS 5 호환), `vitest`, `@vue/test-utils`, `jsdom`, `eslint`, `eslint-plugin-vue`, `typescript-eslint`, `prettier`. `package-lock.json` 커밋, `npm ci` 사용.
4. TS 타입은 `src/api/types.ts` 에 손으로 작성하고 `openapi.json` 과 맞춘다(코드 생성 도구 미도입). qa 의 계약 테스트가 주요 응답 필드 이름을 대조.
5. 실시간: 브라우저 `EventSource`(추가 라이브러리 없음), 실패 시 5초 폴링.

## Alternatives
- **TypeScript 7**: 최신이지만 02 §1 "TypeScript 5" 위반, vue-tsc 호환성 미확인. 기각(02 개정 시 재검토).
- **Chart.js / uPlot**: 더 가볍지만 03 §4 가 ECharts 선호, 게이지·시계열·dataZoom 을 한 라이브러리로. 기각.
- **vue-router + Pinia**: 규모 대비 과함(원칙 3). 기각.
- **openapi-typescript 로 타입 생성**: 동기화 자동화 장점, 의존성·빌드 단계 추가. M2 이후 엔드포인트가 늘면 재검토.

## Consequences
- (+) 런타임 2개 패키지, 사용자에게는 dist 만 전달(ADR-005).
- (−) 프론트 수정자는 Node 20.19+ 필요(사용자 아님, 02 §1 허용).
- (−) 타입 수동 동기화 → 계약 테스트로 보완.
- 릴리스 전 npm audit(security).
