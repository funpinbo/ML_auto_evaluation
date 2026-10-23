---
rev: 3
synced_ltm_rev: 2
---
# Tasks

> **계층 2.** Plan 의 Phase 를 실행 가능한 Task 로 분해한다.
> 갱신 시점: (1) `/aidlc-plan` 최초 생성 (2) Hook cascade 2/3 — LTM rev 가 증가했을 때.
> **규칙:** 이 파일은 cascade 2/3 단계(또는 /aidlc-plan)에서만 수정한다. 작업 중 결과는 STM 에 기록한다.
>
> 형식: `- [ ] T-001 [team] 제목 — FR-001 | deps: T-000 | DoD: 완료 조건`
> Phase 섹션 제목은 반드시 `## P<숫자> ...` 로 시작해야 Hook 이 완료 여부를 판정한다.

## P1 — MVP (M1)
- [x] T-001 [architecture] 파일 계약 3종(.control.json, loop-status.json, claude-status.json JSON Schema) + loop-cli.md(서브커맨드·exit code) + sse-events.md + contracts/README — FR-004, FR-005, FR-008 | deps: - | DoD: workspace/project/contracts/ 에 스키마·문서 존재, ADR-003·004·011 과 일치
- [x] T-020 [cicd] `.gitignore` 에 런타임 파일 등록(`workspace/memory/.control.json`, `workspace/memory/.monitor/`) — I-01 | deps: T-001 | DoD: `git check-ignore` 로 두 경로 무시 확인 (출처: STM-0001 §5)
- [ ] T-002 [security] threat-model.md(STRIDE) + privacy.md(허용 필드 화이트리스트, `~/.claude` 접근 범위, Host/Origin 정책) — NFR-003, Q2 | deps: - | DoD: workspace/teams/security/ 에 문서, 이후 리뷰 체크리스트로 사용 가능
- [ ] T-003 [qa] test-strategy.md + 공용 fixture(conftest: 빈/일부/전체/깨짐/closed STM workspace, 가짜 JSONL 생성기 — 본문 표식 문자열 포함, 스냅샷 fixture) — NFR-001, NFR-002 | deps: T-001 | DoD: fixture 를 import 하는 smoke 테스트 통과
- [ ] T-004 [product] P1 스토리 6건(FR-001~005, SCOPE-01) + UAT 체크리스트 + 단계 판정 기준(A11) 확정 — FR-001~005, SCOPE-01 | deps: - | DoD: workspace/project/stories/ 에 FR 별 파일, 수용 기준이 테스트 가능
- [ ] T-005 [backend] API 앱 셸(앱 팩토리, 응답 envelope, 에러 포맷, Host/Origin 가드, dist 마운트, 설정 주입) + AI-DLC 상태 리더(읽기 전용) + GET /pipeline /plan /tasks /memory — FR-001, FR-002, FR-003 | deps: T-001, T-003, T-020 | DoD: 단위·API 테스트 통과, 조회 전후 workspace 해시 불변, `status` 서브프로세스 미사용
- [ ] T-006 [ops] logging_config + GET /api/v1/health(소스 접근 가능 여부·데우기 진행률·앱 식별자) + 런북 — NFR-002, CON-05 | deps: T-005 | DoD: health 테스트 통과, 로그에 본문·경로·ID 없음
- [ ] T-007 [cicd] run.py / run.sh / run.bat 원클릭 런처(Python 탐지, venv, 해시 마커 재설치 생략, 포트 선택, 헬스 대기, 브라우저 열기) + requirements 고정 + .gitignore + 로컬 게이트·dist 신선도 검사 — SCOPE-01, KPI-02 | deps: T-006 | DoD: 깨끗한 상태에서 `bash run.sh --no-browser` 로 서버 기동·health 200 확인, dist 가 무시되지 않음 확인(I-03)
- [ ] T-008 [backend] 루프 제어 CLI(aidlc/scripts/loop_control.py + aidlc.py loop-start/loop-check/wait-resume/loop-end) + GET /control, POST /control/pause·resume + R-01 스파이크 — FR-005 | deps: T-001, T-005, T-020 | DoD: exit code 계약(D-09: 0/10/20/2/64/1) 테스트·일시정지/재개/episode 상한 초과·NO_LOOP 시나리오 테스트 통과, 쓰기 결과를 contracts 스키마로 검증하는 테스트(jsonschema 를 dev 의존성으로 쓰면 ADR-006 갱신), 스파이크 결과 STM 기록
- [ ] T-009 [architecture] aidlc-run SKILL.md 루프 경계 로직(loop-start → 사이클마다 loop-check → 일시정지면 wait-resume 반복 → loop-end, Windows Python 안내) + ADR-004 확정(D-09·D-10 반영) + ADR-011·20 §5 에러 코드에 `TOO_MANY_STREAMS` 추가 — FR-005, I-02 | deps: T-008 | DoD: SKILL.md 가 loop-cli.md 계약과 일치, R-01 결과 반영, I-02 해소 (출처: STM-0001 §5)
- [ ] T-010 [backend] 사용량 수집기(프로젝트 폴더 해석, 증분 커서, `"usage":` 사전 필터, 허용 필드, requestId 중복 제거, 시간 버킷, 데우기) + statusline.sh/py(허용 필드 스냅샷, 원자적 쓰기, 전역 statusLine 체이닝) + settings.json statusLine 등록 + GET /usage/summary, /usage/timeseries — FR-004 | deps: T-002, T-003, T-005, T-020 | DoD: 본문 비노출 테스트·중복 제거 테스트·폴백(스냅샷 없음) 테스트 통과, `transcript_dir_name` 재검증 + `~/.claude/projects` 직속 하위 경계 검사(symlink 포함) 테스트, 응답·로그에 transcript_dir_name 미포함 테스트 (D-13, 출처: STM-0001 §5)
- [ ] T-011 [backend] 변경 감지(1초 stat 폴링) + SSE 허브 GET /events(topic: pipeline, plan, tasks, memory, usage, control) — FR-008(최소) | deps: T-005, T-008, T-010 | DoD: 파일 변경 후 5초 이내 이벤트 수신 테스트 통과, sse-events.md 계약(D-12: retry 5000, keep-alive 15 s, 연결 상한 503 TOO_MANY_STREAMS) 테스트
- [ ] T-012 [frontend] Vue 3 대시보드(Grafana 다크 테마, 패널 그리드, KPI-01 상단 행, Pipeline/Plan/Task/Memory/사용량 게이지·시계열/루프 제어 패널, API 클라이언트, EventSource + 폴링 폴백) + dist 빌드·커밋 — FR-001~005, FR-008 | deps: T-005, T-008, T-010, T-011 | DoD: vue-tsc·vitest·build 통과, 실제 서버에서 화면 확인(스크린샷)
- [ ] T-013 [qa] 통합 시나리오·가드레일·성능 테스트(500 0건, 본문 0건, 해시 불변, 일시정지/재개 E2E, Task 100 + 30일 JSONL 첫 응답 ≤ 2초) — NFR-001~003, FR-005 | deps: T-012 | DoD: 전체 테스트 통과, 커버리지 ≥ 70%
- [ ] T-014 [product] UAT(KPI-01 질문 3개, KPI-02 설치 리허설) + 문서화 — /aidlc-docs(OpenAPI export → docs/api, 사용자 가이드, monitor/README) | deps: T-013 | DoD: aidlc.py check docs 통과, UAT 기록

## P2 — 운영 편의 (M2)
- [ ] T-015 [backend] 타임라인(파일 변화 추론 + 링 버퍼) GET /timeline — FR-006 | deps: T-011 | DoD: 추정 이벤트 표시 테스트
- [ ] T-016 [backend] 팀 현황·리뷰 결과 GET /teams — FR-007 | deps: T-005 | DoD: charter·STM §7 파싱 테스트
- [ ] T-017 [backend] 예상 비용(설정 단가) GET /usage/cost + 경고 GET /alerts — FR-009, FR-010 | deps: T-010 | DoD: 단가 없음/있음 테스트
- [ ] T-018 [frontend] Timeline·Teams·비용·경고 배너 패널 + 전 패널 SSE 갱신 — FR-006~010 | deps: T-015, T-016, T-017 | DoD: build 통과, 화면 확인
- [ ] T-019 [product] P2 UAT + 문서 갱신 — /aidlc-docs | deps: T-018 | DoD: aidlc.py check docs 통과

## Backlog (Phase 미배정)
- events.jsonl Hook 이벤트 로그 (ADR-010 보류, 사용자 승인 필요)

## Blocked
- (없음)
