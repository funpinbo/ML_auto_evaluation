---
adr: 005
title: 프론트 배포 — 빌드된 dist 를 저장소에 커밋
status: proposed
date: 2026-10-23
author: architecture-analyst
related: [CON-04, KPI-02, SCOPE-01, 원칙 1, 03 §9, 03 §10, 02 §3, 02 §4]
---
# ADR-005. 프론트 배포 방식 (dist 포함 여부, 03 §9 필수)

## Context
- 03 §10 안티패턴: "실행 전에 사용자가 Node 빌드를 해야 하는 구성". 02 §3: `frontend/dist/` 는 저장소에 포함. 02 §4: frontend 소스 변경 시 dist 재빌드를 같은 PR 에 포함. 02 §1: npm 은 프론트 수정 시에만.
- 원격 CI/CD 는 범위 밖(01 §3)이라 릴리스 아티팩트를 자동으로 만들 곳이 없다.

## Decision
1. `vite build` 결과 `monitor/frontend/dist/`(index.html + 해시된 `assets/*`)를 git 에 커밋한다. `.gitignore` 에서 제외하지 않고, `node_modules/` 는 무시.
2. FastAPI 가 API 라우터 등록 **뒤에** `StaticFiles(directory=dist, html=True)` 를 `/` 에 마운트. `/api/*` 는 정적 파일보다 우선. 해시된 assets 는 `Cache-Control: max-age=31536000, immutable`, `index.html` 은 `no-cache`.
3. dist 가 없으면 서버는 계속 뜨고 `/` 가 "dist 없음 — `npm ci && npm run build`" 안내 HTML 을 반환(NFR-002 정신), health 에 표시.
4. **신선도 검사**: 입력은 `monitor/frontend/` 의 `src/**`·`index.html`·`package-lock.json`·`vite.config.ts`. 해시 규칙의 **단일 출처는 `monitor/tools/check_dist_fresh.py`**(cicd 소유): 입력 파일을 `frontend/` 기준 POSIX 상대 경로로 정렬 → 파일마다 내용(CRLF→LF 정규화 후) sha256 → `<경로>\0<sha256>\n` 을 이어 붙여 다시 sha256. 프론트 빌드 스크립트는 `npm run build` 뒤 `python ../tools/check_dist_fresh.py --write` 를 호출해 `dist/.build-meta.json`(`{"schema": 1, "algorithm": "sha256", "source_hash", "inputs", "file_count"}`)을 기록하고, 해시 로직을 따로 구현하지 않는다. 검사는 로컬 게이트 `monitor/tools/check.py` 의 "dist 신선도" 단계(pytest 아님)가 실행 — 불일치·meta 없음이면 exit 1 → PR 전 로컬 점검에서 걸림. 프론트 디렉터리가 아직 없으면 "no dist yet" exit 0.
5. 외부 리소스 금지: 폰트·아이콘·ECharts 모두 번들에 포함, CDN 없음(03 §4, NFR-005).

## Alternatives
- **dist 미포함 + run.py 가 최초 실행 시 `npm ci && npm run build`**: 사용자 PC 에 Node 20.19+ 필요(Vite 8), 설치 시간 증가 → 원칙 1·KPI-02 위반. 기각.
- **GitHub Release 아티팩트로 배포**: CI 필요(범위 밖), 실행 동작 증가. 기각.
- **빌드 없는 ES 모듈 + CDN Vue**: 외부 네트워크 로드(03 §4), TS strict·SFC 불가(02 §2). 기각.

## Consequences
- (+) 사용자는 Node 없이 실행, KPI-02 달성 쉬움.
- (−) 저장소에 생성물이 들어가 diff 가 커지고, 소스와 dist 불일치 위험 → `check.py` 게이트의 신선도 검사로 방지.
- (−) 병합 충돌 시 dist 는 재빌드로 해결(수동 병합 금지) — cicd charter 에 규칙 명시.
- 크기 예산: ECharts 는 `echarts/core` + 사용하는 차트(gauge, line, bar)·컴포넌트만 등록해 gzip 기준 dist 전체 약 500 KB 이하 목표.

## 변경 이력
- 2026-10-23 T-007 architecture 리뷰 조치: Decision 4 를 구현과 일치시킴 — 해시 규칙 단일 출처 `monitor/tools/check_dist_fresh.py`(정렬 POSIX 경로, 파일별 sha256, CRLF→LF), 빌드 후 `--write` 로 `.build-meta.json` schema 1 기록, 검사는 `monitor/tools/check.py` 게이트(pytest 아님). 구조 결정 변경 없음.
