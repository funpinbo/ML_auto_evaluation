---
rev: 5
synced_ltm_rev: 4
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
- [x] T-002 [security] threat-model.md(STRIDE) + privacy.md(허용 필드 화이트리스트, `~/.claude` 접근 범위, Host/Origin 정책) — NFR-003, Q2 | deps: - | DoD: workspace/project/security/ 에 문서, 이후 리뷰 체크리스트로 사용 가능 (경로 정정: LTM I-07, 출처: STM-0003)
- [ ] T-021 [architecture] ADR-011 보강: (a) §5 에 "비-JSON Content-Type 변경 요청도 403 `FORBIDDEN_ORIGIN`" 한 줄 명시(D-14), (b) §4 Host 가드가 포트를 검사할지 결정 — 검사하면 구현 방식 명시, 안 하면 privacy.md N-02 포트 케이스를 선택 항목으로 유지 — NFR-003 | deps: T-002 | DoD: ADR-011 에 두 항목 반영, 20 §8 에러 코드·privacy.md N-02 와 정합, LTM I-04·I-05 해소. (c) ADR-006 Decision 2 dev 의존성 목록에 jsonschema(+전이 4종, MIT) 추가 — I-08 해소 (출처: STM-0003 §5, STM-0004 §5; T-009 도 ADR-011 을 수정하므로 같은 파일 충돌 주의)
- [x] T-003 [qa] test-strategy.md + 공용 fixture(conftest: 빈/일부/전체/깨짐/closed STM workspace, 가짜 JSONL 생성기 — 본문 표식 문자열 포함, 스냅샷 fixture) — NFR-001, NFR-002 | deps: T-001 | DoD: fixture 를 import 하는 smoke 테스트 통과
- [ ] T-004 [product] P1 스토리 6건(FR-001~005, SCOPE-01) + UAT 체크리스트 + 단계 판정 기준(A11) 확정 — FR-001~005, SCOPE-01 | deps: - | DoD: workspace/project/stories/ 에 FR 별 파일, 수용 기준이 테스트 가능
- [ ] T-023 [qa] 홈 격리 강화 + test-strategy 보강: ① `pytest_configure`(또는 session autouse)에서도 HOME/USERPROFILE 치환·`AIDLC_ROOT`/`CLAUDE_HOME` 제거 ② `CLAUDE_CONFIG_DIR` 제거 또는 미설정 단언 ③ conftest `sys.addaudithook` 가드(실제 홈 아래 open/listdir/scandir 시 실패) ④ `assert_no_markers(extra=...)` 실패 메시지는 라벨/인덱스만 ⑤ decoy 인증 파일을 가리키는 symlink 음성 케이스 ⑥ `VALID_DIR_NAMES` 의 실제 경로 인코딩을 합성 이름으로 교체 ⑦ test-strategy S-10/S-11 에 ADR-009 Decision 2(쓰기 함수 가짜 예외) 검증, S-12 에 exit 64/1·NO_LOOP 는 T-008 범위 명시, sources 에 ADR-004·ADR-011 — I-09, NFR-003 | deps: T-003 | DoD: 기존 72건 + 새 가드 테스트 통과, 가드가 실제 홈 접근을 잡는 음성 테스트 포함 (출처: STM-0004 §5, security·architecture 리뷰 비차단 후속; 앱 코드 시작 전이라 T-005 앞)
- [ ] T-005 [backend] API 앱 셸(앱 팩토리, 응답 envelope, 에러 포맷, Host/Origin 가드, dist 마운트, 설정 주입) + AI-DLC 상태 리더(읽기 전용) + GET /pipeline /plan /tasks /memory — FR-001, FR-002, FR-003 | deps: T-001, T-003, T-020, T-021, T-023 | DoD: 단위·API 테스트 통과, 조회 전후 workspace 해시 불변, `status` 서브프로세스 미사용
- [ ] T-006 [ops] logging_config + GET /api/v1/health(소스 접근 가능 여부·데우기 진행률·앱 식별자) + 런북 — NFR-002, CON-05 | deps: T-005 | DoD: health 테스트 통과, 로그에 본문·경로·ID 없음
- [ ] T-007 [cicd] run.py / run.sh / run.bat 원클릭 런처(Python 탐지, venv, 해시 마커 재설치 생략, 포트 선택, 헬스 대기, 브라우저 열기) + requirements 고정 + .gitignore + 로컬 게이트·dist 신선도 검사 — SCOPE-01, KPI-02 | deps: T-006 | DoD: 깨끗한 상태에서 `bash run.sh --no-browser` 로 서버 기동·health 200 확인, dist 가 무시되지 않음 확인(I-03), `monitor/backend/requirements-dev.txt` 에 pytest==9.1.1, jsonschema==4.26.0(+referencing, jsonschema-specifications, rpds-py, attrs), ruff==0.17.2, pytest-cov, httpx 를 `pip freeze` 로 `==` 고정 (출처: STM-0004 §5)
- [ ] T-008 [backend] 루프 제어 CLI(aidlc/scripts/loop_control.py + aidlc.py loop-start/loop-check/wait-resume/loop-end) + GET /control, POST /control/pause·resume + R-01 스파이크 — FR-005 | deps: T-001, T-005, T-020 | DoD: exit code 계약(D-09: 0/10/20/2/64/1) 테스트·일시정지/재개/episode 상한 초과·NO_LOOP 시나리오 테스트 통과, 쓰기 결과를 contracts 스키마로 검증하는 테스트(jsonschema 를 dev 의존성으로 쓰면 ADR-006 갱신), 스파이크 결과 STM 기록
- [ ] T-009 [architecture] aidlc-run SKILL.md 루프 경계 로직(loop-start → 사이클마다 loop-check → 일시정지면 wait-resume 반복 → loop-end, Windows Python 안내) + ADR-004 확정(D-09·D-10 반영) + ADR-011·20 §5 에러 코드에 `TOO_MANY_STREAMS` 추가 — FR-005, I-02 | deps: T-008 | DoD: SKILL.md 가 loop-cli.md 계약과 일치, R-01 결과 반영, I-02 해소 (출처: STM-0001 §5)
- [ ] T-010 [backend] 사용량 수집기(프로젝트 폴더 해석, 증분 커서, `"usage":` 사전 필터, 허용 필드, requestId 중복 제거, 시간 버킷, 데우기) + statusline.sh/py(허용 필드 스냅샷, 원자적 쓰기, 전역 statusLine 체이닝) + settings.json statusLine 등록 + GET /usage/summary, /usage/timeseries — FR-004 | deps: T-002, T-003, T-005, T-020 | DoD: 본문 비노출 테스트·중복 제거 테스트·폴백(스냅샷 없음) 테스트 통과, `transcript_dir_name` 재검증 + `~/.claude/projects` 직속 하위 경계 검사(symlink 포함) 테스트, 응답·로그에 transcript_dir_name 미포함 테스트 (D-13, 출처: STM-0001 §5)
- [ ] T-011 [backend] 변경 감지(1초 stat 폴링) + SSE 허브 GET /events(topic: pipeline, plan, tasks, memory, usage, control) — FR-008(최소) | deps: T-005, T-008, T-010 | DoD: 파일 변경 후 5초 이내 이벤트 수신 테스트 통과, sse-events.md 계약(D-12: retry 5000, keep-alive 15 s, 연결 상한 503 TOO_MANY_STREAMS) 테스트
- [ ] T-012 [frontend] Vue 3 대시보드(Grafana 다크 테마, 패널 그리드, KPI-01 상단 행, Pipeline/Plan/Task/Memory/사용량 게이지·시계열/루프 제어 패널, API 클라이언트, EventSource + 폴링 폴백) + dist 빌드·커밋 — FR-001~005, FR-008 | deps: T-005, T-008, T-010, T-011 | DoD: vue-tsc·vitest·build 통과, 실제 서버에서 화면 확인(스크린샷)
- [ ] T-022 [security] `workspace/project/security/security-checklist.md` 작성(charter §2·§3 산출물) — privacy.md §4~§6 의 Host/Origin·접근 범위·쓰기 경로 체크리스트와 중복 없이 색인 문서로 만들거나 charter 를 privacy.md 로 정리할지 결정 — NFR-003 | deps: T-002 | DoD: 체크리스트 ID(P-/N-/W-/D-/T-)를 한 문서에서만 정의하고 참조 정합, T-013 에서 실행 근거 확인에 사용 가능, 하드 링크(`st_nlink > 1`) 처리 방침(건너뜀/수용)을 threat-model §2.4·privacy P-29 에 명시 — I-10 (출처: STM-0003 §5, STM-0004 §5; 배치 근거: 구현 전 문서만으로 가능하나 T-013 의 가드레일 검증과 I-06 재확인이 이 체크리스트를 쓰므로 P1 말, T-013 이전)
- [ ] T-013 [qa] 통합 시나리오·가드레일·성능 테스트(500 0건, 본문 0건, 해시 불변, 일시정지/재개 E2E, Task 100 + 30일 JSONL 첫 응답 ≤ 2초) — NFR-001~003, FR-005 | deps: T-012, T-022 | DoD: 전체 테스트 통과, 커버리지 ≥ 70%, pytest marker `perf` 등록, 30일 JSONL 실측 크기로 I-11 보정
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
