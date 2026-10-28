---
doc: interpretation
layer: project
author: doc-interpreter
status: draft
source_versions: [01@0.1, 02@0.1, 03@0.1, 04@0.1]
---
# 00. 요구 해석서 (User Layer → Project Layer)

> **작성자: doc-interpreter Agent.** User Layer 4개 문서를 읽고 Agent 가 이해한 내용을 정리합니다.
> 이후 모든 분석 Agent 는 User 문서 대신 **이 문서를 1차 입력**으로 씁니다. 사용자는 여기서 오해를 바로잡습니다.

## 1. 한 문단 요약
AI-DLC Monitor 는 VSCode + Claude Code 로 AI-DLC 를 혼자 운영하는 개발자를 위한 **로컬 전용(127.0.0.1) Grafana 스타일 대시보드**다. FastAPI + uvicorn 단일 프로세스가 `/api/v1` REST·SSE API 와 저장소에 포함된 Vue 3 빌드(dist)를 함께 서빙하고, `workspace/` 파일(frontmatter)과 `aidlc.py check/status` 출력, Claude Code 세션 기록(JSONL 의 usage 필드만)과 status line 스냅샷(JSON)을 **읽기만** 해서 파이프라인 단계·Plan/Task 진행률·메모리/cascade·팀·사용량(5시간/7일 한도, 토큰, 비용)을 한 화면에 보여준다. 대시보드가 쓰는 파일은 루프 제어 파일 하나뿐이며, 일시정지하면 `/aidlc-run N` 은 현재 Task(cascade 포함)를 마친 뒤 **같은 세션에서 대기**하다가 대시보드에서 재개하면 남은 반복을 자동으로 이어간다(01 §10 결정). 설치는 `run.bat`/`run.sh`(→ `run.py`) 한 번으로 가상환경 생성·패키지 설치·서버 실행·브라우저 열기까지 끝나야 하며, MVP(FR-001~005 + 원클릭 실행)는 2026-11-06, M2(FR-006~010)는 2026-11-13 이 목표다. 우선순위는 개발 속도 > 보안 > 유지보수성 순이며 DB 서버·Docker 필수 구성·외부 전송은 금지다.

## 2. 요구사항 추적표 (Traceability)
| ID | 원문 요약 | 해석 (구체화) | 분류 (FR/NFR/제약) | 관련 KPI | 검증 방법 | 확신도 (H/M/L) |
|----|-----------|---------------|--------------------|----------|-----------|----------------|
| FR-001 | 파이프라인 0~6 단계 현황 + user·project·docs Gate 결과 (Must, M1) | 단계 0 init ~ 6 docs (init, interpret, analyze, teams, plan, run, docs) 각각을 완료/진행/대기로 표시. 판정은 산출물 파일 존재·frontmatter(status, completed_phases 등)로 한다(기준은 #A3 가정). Gate 는 `aidlc.py check user|project|docs` 의 exit code 와 미작성 플레이스홀더 수를 파싱해 PASS/FAIL + 개수로 표시 | FR | KPI-01 | pytest: fixture workspace(빈/일부/전체) 별 단계 상태·Gate 결과가 CLI 결과와 일치 | M |
| FR-002 | Phase 별 완료/전체 수, 진행률 바, Task 목록(팀·상태 필터) (Must, M1) | tasks.md 의 `## P<n>` 섹션과 체크박스(`[ ]`/`[x]`), `[팀id]` 태그를 파싱. 상태는 체크 여부 + STM 진행 중/blocked 여부로 구분. 필터는 팀·상태 | FR | KPI-01 | pytest: fixture tasks.md 파싱 결과(개수·진행률·필터)가 원문과 일치, vitest: 필터 동작 | H |
| FR-003 | STM 현재 Task·팀·시작 시각·경과 시간, LTM rev, 미처리 cascade 단계 (Must, M1) | short-term.md frontmatter(status, task, team, opened_at)와 long-term.md `rev`, tasks.md `synced_ltm_rev`, plan.md `completed_phases` 를 읽어 cascade 1/2/3 미처리 여부를 Hook 과 같은 규칙으로 판정. 경과 시간 = 현재 시각 − opened_at | FR | KPI-01 | pytest: cascade 1/2/3 각 상황 fixture 에서 `aidlc.py status` 출력과 비교 | H |
| FR-004 | 5시간·7일 한도 사용률(%)·초기화 시각, 세션 비용, 시간대별·모델별 토큰 그래프. 한도 정보가 없으면 토큰 집계만 + 안내 (Must, M1) | 한도·비용 = DS-04 스냅샷의 `rate_limits.five_hour/seven_day.used_percentage, resets_at`, `cost.total_cost_usd`. 토큰 그래프 = DS-03 JSONL 의 `message.usage` 4종을 `timestamp`·`message.model` 로 집계(requestId 중복 제거). 스냅샷이 없거나 `rate_limits` 가 없으면(비구독, 첫 응답 전, VSCode 패널 미지원) "한도 정보 없음" 안내 + 토큰만 표시 | FR | KPI-01 | pytest: 가짜 JSONL/스냅샷 fixture(중복 requestId, usage 없는 줄, rate_limits 없음 포함)로 집계·폴백 검증 | M |
| FR-005 | 일시정지 → 현재 Task(cascade 포함) 완료 후 멈춤 + "일시정지됨" 표시, 재개 → 남은 반복 이어서 (Must, M1). 같은 세션이 대기하다 자동 재개 (01 §10 결정) | 대시보드 버튼이 제어 파일(유일한 쓰기 대상)에 pause/resume 를 기록. `/aidlc-run` 루프는 Task 경계(cascade 처리 후)에서 제어 파일을 확인하고, pause 면 같은 세션 안에서 대기 스크립트를 실행해 resume 를 기다린 뒤 남은 반복을 진행. 화면은 "일시정지 요청됨(현재 Task 진행 중)" → "일시정지됨(대기 중)" → "실행 중" 을 구분 | FR | - | pytest: 제어 파일 API·상태 전이 시나리오 테스트(02 §5 필수), 수동: 실제 `/aidlc-run 3` 중 일시정지/재개 리허설 | M |
| FR-006 | STM 작업 로그와 cascade 이벤트를 시간순, 5초 이내 갱신 (Should, M2) | STM 본문의 작업 로그 섹션 + cascade 이벤트(STM 보관, LTM rev 증가, tasks 동기화, Phase 완료)를 시간순 타임라인으로 표시. cascade 이벤트를 남기는 파일이 현재 없으므로 출처는 #A6 가정 | FR | - | pytest: 로그 파싱, SSE 로 5초 이내 전달 측정 | M |
| FR-007 | 팀별 할당/완료 Task 수, 최근 리뷰 PASS/FAIL (Should, M2) | tasks.md `[팀id]` 태그로 할당/완료 집계, STM §7 및 archive/STM-*.md 의 리뷰 기록에서 팀별 최신 PASS/FAIL 추출. 팀 목록은 `workspace/teams/*/charter.md`, 40-team-composition.md | FR | - | pytest: fixture 팀/아카이브로 집계 검증 | H |
| FR-008 | 메모리 파일·사용량 변경 시 새로고침 없이 5초 이내 반영 (Should, M2) | 서버가 파일 변경을 감지(폴링 또는 watchfiles)해 SSE 로 변경 패널만 push, 프론트는 해당 패널 재조회 | FR | KPI-01 | 자동: 파일 수정 후 SSE 이벤트 수신까지 시간 측정 ≤ 5초 | H |
| FR-009 | 설정 파일의 모델별 단가로 일/모델별 예상 비용 (Could, M2) | 사용자가 작성하는 단가 설정 파일(형식·위치 #A9 가정)이 있을 때만 토큰 × 단가로 일·모델별 비용 계산. 없으면 패널 숨김/안내. status line 의 `cost.total_cost_usd`(세션 비용)와는 별도 수치임을 표기 | FR | - | pytest: 단가 fixture 로 계산 검증, 설정 없음/깨짐 처리 | M |
| FR-010 | cascade 막힘·blocked Task·한도 80% 이상 시 상단 경고 배너 (Could, M2) | 조건 3종: (a) 미처리 cascade 존재(정의 #A10), (b) STM/tasks 에 blocked Task 존재, (c) five_hour 또는 seven_day used_percentage ≥ 80 | FR | - | pytest: 조건별 fixture 에서 배너 API 응답 검증 | M |
| SCOPE-01 | 원클릭 실행 스크립트 (In scope, M1, 5.1 흐름 1, KPI-02) — **FR 번호 없음** | `run.bat`/`run.sh` → `run.py`: Python 3.11+ 확인 → 가상환경 생성 → requirements.txt 설치 → uvicorn(127.0.0.1) 실행 → 브라우저 자동 열기. 재실행 시 설치 생략. Node 불필요(dist 포함) | 제약 (FR 누락, Q1) | KPI-02 | 수동: 깨끗한 PC(Windows/macOS/Linux) 설치 리허설 | M |
| NFR-001 | 첫 화면 2초 이내, 상태 변화 5초 이내 반영 (Task 100개, 사용 기록 30일 기준) | 첫 화면 = 서버 기동 후 브라우저 첫 렌더까지가 아니라 "대시보드 접속 → 모든 Must 패널 표시"로 해석. 30일치 JSONL(수십~수백 MB 가능)을 매 요청 전체 재파싱하지 않도록 파일별 증분 집계 필요(#C3) | NFR | KPI-01 | 성능 테스트: 생성기로 만든 Task 100개 + 30일 가짜 JSONL fixture 에서 API 응답·렌더 시간 측정 | M |
| NFR-002 | 파일 없음/형식 깨짐에도 서버 생존, 해당 패널에 안내 | 모든 파일 읽기는 패널 단위로 예외 격리 → 해당 패널에 `{"error": {...}}` 또는 "데이터 없음" 상태 반환, 다른 패널 정상. WARN 로그 | NFR | - | pytest: 파일 삭제·손상·빈 workspace 테스트에서 HTTP 500 0건 (02 §5 필수 테스트) | H |
| NFR-003 | 127.0.0.1 전용, 인증 없음, Claude 대화 내용 읽지도 저장하지도 않음 | uvicorn host 를 127.0.0.1 로 고정(설정으로 0.0.0.0 변경 불가). JSONL 은 필요한 필드만 추출하고 본문은 보관·로그·응답·저장하지 않음(#C2). `~/.claude` 인증 파일 비접근 | NFR | - | 외부 IP 접속 실패 확인, 응답·로그에 fixture 본문 문자열 미포함 자동 검사 | H |
| NFR-004 | 확장성 N/A (단일 사용자 로컬) | 대상 아님 | NFR (N/A) | - | - | H |
| NFR-005 | 규정/컴플라이언스 N/A (외부 전송 없음) | 대상 아님. 단 외부 전송 금지는 03 §4 금지 기술로 유지 | NFR (N/A) | - | 코드 리뷰: 외부 네트워크 호출 없음 | H |
| KPI-01 | 현재 상태(단계·Task·사용량) 파악 시간 약 1분 → 5초 이내 | 대시보드 첫 화면만으로 "지금 몇 단계? 어떤 Task? 5시간 한도 몇 %?" 3개 질문에 답하는 시간. FR-001·003·004 를 첫 화면 상단에 배치해야 달성 가능 | KPI | KPI-01 | 수동 사용 테스트(스톱워치). 질문 세트는 #A12 가정. 04 데이터로 자동 측정하지 않음 | M |
| KPI-02 | 다운로드 후 첫 화면 5분 이내, 실행 동작 1번 | Python 3.11+ 는 설치되어 있다는 01 §7 가정 하에, `run.bat` 더블클릭(또는 `python run.py`/`run.sh`) 1회 → 브라우저 대시보드 표시까지 5분. 네트워크 속도에 따라 pip 설치 시간이 변동 | KPI | KPI-02 | 깨끗한 PC 설치 리허설(OS 별 1회 이상), 소요 시간 기록 | M |
| CON-01 | 기술 스택: Python 3.11+ / FastAPI + uvicorn / Pydantic, TypeScript 5 strict / Vue 3 + Vite / ECharts | 02 §1·§2 그대로. 데이터 처리는 표준 라이브러리. frontmatter 는 YAML 라이브러리 없이 단순 key: value 파서(또는 aidlc 기존 파서 재사용) | 제약 | - | ruff, eslint, 타입 검사 | H |
| CON-02 | 단일 프로세스 모놀리스, 서버 무상태, 조회 REST + 실시간 SSE, `/api/v1`, 에러 포맷 고정 | FastAPI 가 dist 정적 파일 + API 서빙. SSE 는 FastAPI StreamingResponse(추가 라이브러리 없이). OpenAPI 명세를 `workspace/project/contracts/openapi.json` 으로 내보내고 `docs/api/reference.md` 재생성 | 제약 | - | API 테스트, 명세 export 확인 | H |
| CON-03 | 읽기 전용 — 대시보드가 쓰는 파일은 루프 제어 파일 하나 | 모든 서비스 계층은 읽기 전용. 쓰기 API 는 pause/resume 1종. Hook 엔진의 쓰기 함수(STM 보관 등)를 import 해 호출하지 않음 | 제약 | - | 코드 리뷰 + 테스트: 조회 API 호출 전후 workspace 파일 해시 불변 | H |
| CON-04 | `frontend/dist` 저장소 포함, 사용자 Node 빌드 불필요. frontend 변경 시 dist 재빌드를 같은 PR 에 포함 | dist 는 커밋 대상(.gitignore 제외 확인 필요) | 제약 | KPI-02 | PR 리뷰, run 스크립트로 Node 없이 실행 확인 | H |
| CON-05 | `/api/v1/health` 헬스 체크, 콘솔 텍스트 로그(시각·레벨·메시지), 대화 내용·토큰/키 로그 금지 | health 는 서버 생존 + 주요 데이터 소스 접근 가능 여부 반환 | 제약 | - | API 테스트, 로그 검사 | H |
| CON-06 | 테스트는 fixture 가짜 기록만, backend 라인 커버리지 70%+, 필수: 단위+API, 일시정지/재개 시나리오, 깨진 파일·빈 workspace | 실제 `~/.claude` 경로를 테스트에서 참조하지 않도록 데이터 경로를 설정으로 주입 | 제약 | - | pytest --cov, CI 없음 → 로컬 실행 | H |
| CON-07 | Agent 승인 없이 금지: `~/.claude` 수정·삭제, `~/.claude/settings.json` 변경, 전역 패키지 설치 | status line 등록·패키지 설치는 프로젝트 범위(`.claude/settings.json`, 가상환경)에서만(#A4) | 제약 | - | 리뷰 | H |

> 기술 금지 검사: 02 의 기술(FastAPI, uvicorn, Pydantic, Vue 3, Vite, ECharts, pytest, vitest, ruff, eslint, prettier, pip-audit) 중 03 §4 금지(DB 서버, Docker 필수 구성, 외부 SaaS 전송)에 해당하는 것은 **없음**. watchfiles 는 "폴링보다 빠를 때만" 허용이므로 ADR 로 결정한다(uvicorn[standard] 에 포함된다는 점도 고려).

## 3. 모호함 & 충돌
| # | 위치 (문서§) | 내용 | 유형 (모호/충돌/누락) | Agent 의 임시 가정 | 영향 |
|---|-------------|------|----------------------|-------------------|------|
| C1 | 01 §6 NFR-001 vs 01 §5 FR-008, §9 | NFR-001 은 "상태 변화 5초 이내 반영"을 조건 없이 요구하고 5.1 흐름 3·FR-005("일시정지됨" 표시)도 실시간 갱신을 전제하지만, 자동 갱신 FR-008 은 Should·M2 로 잡혀 있다 | 충돌 | M1 에 SSE 기반 최소 자동 갱신(FR-003 메모리 패널, FR-005 제어 상태, FR-004 한도)을 포함하고, 전 패널 확장·변경 감지 최적화는 M2(FR-008)에서 완성한다. (확신도 M) | M1 범위 소폭 증가 |
| C2 | 01 NFR-003, 04 §2.1·§6 vs 03 §1 원칙 3 | "대화 본문은 메모리에 올리지도 않는다"고 하지만 DS-03 은 한 JSON 줄에 본문과 usage 가 함께 있어, 표준 라이브러리만으로는 줄을 읽지 않고 usage 만 꺼낼 수 없다(스트리밍 JSON 파서는 외부 의존성) | 충돌 | 의도를 "본문을 **보관·가공·로그·응답·저장하지 않는다**"로 해석. 구현: 줄 단위 스트리밍 읽기 → `"usage"` 문자열 없는 줄은 파싱 전 버림 → 파싱 직후 timestamp·model·usage·requestId 만 새 객체로 복사하고 원본 dict 즉시 폐기. `message.content` 키에는 접근하지 않음. (확신도 H) | 보안(2순위) 해석. 사용자 확인 필요(Q2) |
| C3 | 01 NFR-001 vs 03 §3 상태 관리, §5 일관성 | "서버는 상태를 갖지 않는다 / 캐시는 수 초 TTL" 을 문자 그대로 따르면 30일치 JSONL(수십 MB × 여러 파일)을 수 초마다 전량 재파싱해야 해서 첫 화면 2초를 지키기 어렵다 (성능은 5순위지만 수치 NFR 이 있음) | 충돌 | "상태 없음" = 디스크에 자체 데이터를 영속하지 않음으로 해석. 프로세스 메모리 안의 **파생 캐시**(파일별 size·mtime·읽은 offset + 집계값)는 허용, 파일이 바뀌면 증분 반영, 재시작 시 재구축. 화면 값은 수 초 이내 최신성 유지. (확신도 M) | 아키텍처 ADR 대상(사용량 수집 방식) |
| A4 | 04 DS-04, 02 §11, 03 §1 원칙 2, 01 §10 | DS-04 는 status line 스크립트가 JSON 을 파일로 저장한다고 하지만, 누가 statusLine 을 등록하는지·스냅샷 파일 위치가 정의되지 않았다. 사용자 전역 설정 변경은 승인 필요 | 누락 | 저장소의 프로젝트 `.claude/settings.json` 에 `statusLine`(command + refreshInterval)을 개발 시점에 추가(커밋). 스크립트는 stdin JSON 중 `rate_limits`·`cost`·`context_window`·모델·세션 ID 만 git 무시 경로(예: `monitor/.runtime/statusline.json`)에 원자적으로 저장하고 짧은 상태 문자열을 출력. 대시보드는 읽기만. 사용자 전역 statusLine 이 있으면 프로젝트 설정이 우선 적용되어 가려진다. (확신도 M) | FR-004 데이터 수집 경로, Q4 |
| A5 | 01 §10 (VSCode 확장 statusLine 실행 여부) | 공식 문서로 확인되지 않음. 미지원이면 VSCode 채팅 패널만 쓰는 사용자는 한도 사용률을 못 본다 | 모호 | FR-004 수용 기준의 폴백(토큰 집계만 + 안내)으로 Must 는 충족. 구현 초기에 실측 확인 Task 를 둔다. 미지원이면 "CLI 세션에서 실행하면 한도가 표시됨" 안내. 스냅샷의 생성 시각을 함께 표시해 오래된 값임을 알린다. (확신도 M) | FR-004 표시 범위, Q13 |
| A6 | 01 FR-006, 04 §1 | "cascade 이벤트"를 기록하는 데이터 소스가 04 에 없다. 현재 Hook 은 메시지를 Claude 에게만 출력하고, 파일로 남는 것은 `archive/STM-*.md`(archived_at), frontmatter 값, `.cascade-state.json`(Stop 가드 상태) 뿐이다 | 누락 | M2 에서 frontmatter·archive 변화로 이벤트를 **추론**해 타임라인 구성(STM 보관=archived_at, LTM rev 증가, synced_ltm_rev 갱신, completed_phases 추가). Hook 에 이벤트 로그를 추가하는 안은 프레임워크 변경이므로 사용자 승인 후. (확신도 M) | FR-006 정확도, Q8 |
| A7 | 01 FR-005, §10 결정 | "같은 세션이 일시정지 상태로 기다린다"의 구현 수단이 정의되지 않았다. Claude Code 는 기본 대기 기능이 없어 세션 안에서 대기 스크립트(Bash 도구 호출)를 실행해야 하며, 도구 호출에는 시간 제한(최대 10분 수준)이 있어 긴 일시정지는 대기 호출을 반복해야 한다. 반복마다 소량의 토큰·컨텍스트를 쓴다. 세션이 닫히면 재개할 주체가 없다 | 모호 | 대기 스크립트(Python, OS 공통)가 제어 파일을 1~2초 간격으로 확인, 제한 시간 직전 "still paused" 로 반환 → 루프가 다시 호출. 대기 중 heartbeat(대기 시작 시각·마지막 확인 시각)를 제어 상태에 기록해 화면이 "일시정지됨(세션 대기 중)"과 "세션 없음"을 구분. 세션이 끊긴 뒤 재개하면 다음 `/aidlc-run` 시작 시 남은 반복 수를 안내. (확신도 M) | FR-005 설계, ADR 필수(루프 제어 방식), Q5 |
| A8 | 01 FR-005, 03 §10, CLAUDE.md | 루프 제어는 대시보드(monitor/)만으로 불가능하고 AI-DLC 프레임워크(`.claude/skills/aidlc-run/SKILL.md`, 필요시 hook)를 수정해야 한다. 제어 파일 위치도 미정. `workspace/memory/` 는 Hook·오케스트레이터 소유 | 누락 | 프레임워크 변경 범위는 aidlc-run 스킬에 "Task 경계에서 제어 파일 확인 + 대기 스크립트 실행" 단계 추가로 최소화. 제어 파일은 메모리 cascade 판정 대상이 아닌 별도 파일(예: `workspace/memory/loop-control.json`)로 두고 Hook 판정 로직에 영향이 없음을 테스트. 위치는 ADR 로 확정. (확신도 M) | 팀 소유권(architecture/backend), Q6 |
| A9 | 01 FR-009 | 단가 설정 파일의 위치·형식이 없다 | 모호 | 사용자가 작성하는 `monitor/pricing.json`(모델 ID → 입력/출력/캐시 생성/캐시 읽기 단가, USD per 1M tokens). 저장소에는 예시 파일만 두고, 대시보드는 읽기만 한다. (확신도 L — Could 항목) | FR-009 만 |
| A10 | 01 FR-010 | "cascade 가 막혔다"의 정의가 없다 | 모호 | 미처리 cascade 가 존재하고 일정 시간(예: 10분) 이상 해소되지 않거나, `.cascade-state.json` 상 Stop Hook 차단이 최대 횟수(3회)에 도달한 경우. (확신도 L — Could 항목) | FR-010 만 |
| A11 | 01 FR-001 | 각 단계의 완료/진행/대기 판정 기준이 없다 | 모호 | 0 init: workspace/user 존재 / 1 interpret: 00 해석서 존재(status 표시) / 2 analyze: 10·20·30 존재 / 3 teams: 40 + teams/* 존재 / 4 plan: plan.md·tasks.md 에 Phase 존재 / 5 run: tasks 일부 [x]=진행, 전부 [x]=완료 / 6 docs: docs Gate PASS. 이전 단계 완료 + 자기 산출물 일부 = 진행. (확신도 M) | FR-001 표시 |
| A12 | 01 §2 KPI-01, 04 §5 | 04 §5 는 DS-03·04 가 KPI-01 측정에 쓰인다고 하지만 KPI-01 은 사람 대상 시간 측정이며 질문 세트가 정의되지 않았다 | 모호 | 질문 3개 고정: "지금 몇 단계인가", "지금 어떤 Task 를 어느 팀이 하고 있나", "5시간 한도를 몇 % 썼고 언제 초기화되나". 측정은 수동, 데이터 소스 불필요. (확신도 M) | KPI 판정 |
| A13 | 01 FR-004, 04 §3 Q1, 01 §3 Out of scope | 5시간·7일 한도는 계정 전체 기준인데, 토큰 집계를 이 저장소의 `~/.claude/projects/<프로젝트>/` 만 하면 다른 프로젝트 사용분이 빠진다. "여러 저장소 모니터링"은 범위 밖 | 모호 | 토큰 그래프는 이 저장소 프로젝트 디렉터리만 집계하고 "이 프로젝트 기준"이라고 표기. 한도 %는 status line 값(계정 기준)을 그대로 표시. 프로젝트 디렉터리는 저장소 절대 경로를 Claude Code 규칙으로 인코딩해 찾고, 못 찾으면 안내. (확신도 M) | FR-004 수치 해석, Q7 |
| A14 | 01 FR-004 | "시간대별" 그래프의 기간·단위, "오늘"의 시간대가 없다 | 모호 | 기본 최근 24시간 1시간 단위 + 기간 선택(5시간 구간/7일/30일, 30일은 일 단위). 시간대는 PC 로컬 시간. (확신도 M) | FR-004 화면 |
| A15 | 04 §4 | 같은 응답이 여러 줄로 기록되어 중복 집계 위험 | 모호 | `requestId`(없으면 message.id) 기준으로 묶어 마지막 줄의 usage 를 채택. usage 없는 줄은 건너뜀. EDA(30)에서 실측으로 확정. (확신도 M) | 토큰 수치 정확도 |
| A16 | 01 §3 In scope "원클릭 실행 스크립트" | 범위·마일스톤(M1)·KPI-02 에 있으나 대응 FR 이 없다 | 누락 | SCOPE-01 로 추적하고 수용 기준은 KPI-02 + 5.1 흐름 1 을 그대로 사용(Must 취급). (확신도 M) | M1 범위, Q1 |
| A17 | 01 FR-003, 04 DS-02 | `aidlc.py status`/`check` 를 서브프로세스로 부를지, 같은 판정 로직을 재구현할지 미정. Windows 에는 `python3` 명령이 없을 수 있다. Hook 엔진 모듈에는 쓰기 함수(STM 보관)가 섞여 있다 | 모호 | 서브프로세스는 `sys.executable` 로 호출하고 출력은 파싱하며, 쓰기 경로가 있는 함수는 호출하지 않는다. status/check 명령이 읽기 전용인지 구현 전에 확인. (확신도 M) | FR-001·003, CON-03 |

## 4. 사용자에게 묻는 질문
<!-- 답이 오면 해당 user 문서를 사용자가 고치고, 이 문서는 /aidlc-interpret 재실행으로 갱신 -->
> **답변 처리 (2026-10-23):** 사용자가 "추천대로 해서 만들어줘" 라고 지시하여 아래 답을 적용함. 바꾸려면 해당 Q 의 답을 알려 주거나 user 문서를 고친 뒤 `/aidlc-interpret` 재실행.
> - Q2 → 예. JSONL 각 줄은 읽되 `"usage"` 문자열이 없는 줄은 파싱 전에 버리고, usage·model·timestamp·requestId 만 복사. 본문은 접근·보관·로그·응답·저장하지 않음.
> - Q4 → 예. 프로젝트 `.claude/settings.json` 에 등록. 사용자 전역 statusLine 이 있으면 그 명령을 실행해 출력을 그대로 이어 붙임(체이닝) — 기존 표시를 가리지 않음.
> - Q5 → 허용. 최대 일시정지 시간 기본 2시간(설정 가능). 초과 시 루프를 정상 종료하고 STM 은 건드리지 않음.
> - Q6 → 승인. FR-005 구현에 필요한 `.claude/skills/aidlc-run/SKILL.md`·`aidlc/scripts` 수정은 이 프로젝트 범위. 제어 파일 `workspace/memory/.control.json`.
> - Q1, Q3, Q7~Q13 → 본문 가정(A1~A16) 그대로 적용.
- [x] Q1. 원클릭 실행 스크립트를 FR(예: FR-011, Must, 수용 기준 = KPI-02)로 01 §5 에 추가할까요? (A16)
- [x] Q2. "대화 본문을 메모리에 올리지 않는다"를 "줄을 읽되 본문 필드는 접근·보관·로그·응답·저장하지 않고 즉시 버린다"로 해석해도 됩니까? (C2)
- [x] Q3. NFR-001 의 "상태 변화 5초 이내 반영"을 MVP(M1)부터 적용하나요? 그렇다면 최소 자동 갱신을 M1 에 포함합니다. (C1)
- [x] Q4. status line 을 저장소의 `.claude/settings.json`(프로젝트 범위)에 등록해도 됩니까? 이미 개인 statusLine 을 쓰고 있다면 가려지는데, 기존 출력을 이어 붙이는(체이닝) 방식이 필요한가요? (A4)
- [x] Q5. 일시정지 대기 중 세션이 약 10분마다 대기 호출을 반복하며 소량의 토큰을 씁니다. 허용합니까? 최대 일시정지 시간(초과 시 루프 종료)을 둘까요? (A7)
- [x] Q6. 루프 제어를 위해 AI-DLC 프레임워크(`.claude/skills/aidlc-run/SKILL.md`, 필요시 Hook)를 수정하는 것을 이 프로젝트 범위로 승인합니까? 제어 파일을 `workspace/memory/` 아래 두어도 됩니까? (A8)
- [x] Q7. 토큰 집계를 이 저장소의 Claude Code 기록만으로 해도 됩니까, 아니면 `~/.claude/projects/` 전체 합계도 필요합니까? (A13)
- [x] Q8. FR-006 의 cascade 이벤트를 파일 변화로 추론할까요, 아니면 Hook 이 이벤트 로그 파일을 남기도록 바꿀까요? (A6)
- [x] Q9. 토큰 그래프의 기본 기간·단위(가정: 최근 24시간, 1시간 단위)가 맞습니까? (A14)
- [x] Q10. FR-010 의 "cascade 막힘" 기준(가정: 10분 이상 미해소 또는 Stop Hook 3회 차단)이 맞습니까? (A10)
- [x] Q11. FR-001 의 단계별 완료/진행/대기 판정 기준(A11)이 의도와 맞습니까?
- [x] Q12. KPI-01 사용 테스트 질문 3개(A12)로 확정해도 됩니까?
- [x] Q13. VSCode 확장에서 status line 이 동작하지 않으면 "CLI 세션에서만 한도 표시" 안내로 충분합니까? (A5)

## 5. 표준 & 철학 요약 (분석 Agent 용 체크리스트)
- 개발 표준 핵심 규칙 (02):
  - Python 3.11+ / FastAPI + uvicorn / Pydantic 입출력, TypeScript 5 strict / Vue 3 + Vite / ECharts. pip + requirements.txt(버전 고정), npm 은 프론트 수정 시에만
  - ruff format/check, eslint + prettier. snake_case / PascalCase.vue / useXxx.ts. type hint 필수, public docstring, 주석은 "왜"만
  - 디렉터리: `monitor/backend/app/{api,services,models}`, `monitor/backend/tests`, `monitor/frontend/src/{views,components/panels,api}`, `monitor/frontend/dist`(커밋), 루트 `run.py`, `run.bat`/`run.sh`
  - REST + SSE, `/api/v1`, 에러 `{"error": {"code", "message"}}`, 인증 없음(127.0.0.1), OpenAPI → `workspace/project/contracts/openapi.json` (+ docs/api/reference.md 재생성)
  - 테스트: pytest + TestClient, vitest, backend 라인 70%+, 필수 = 단위·API·일시정지/재개 시나리오·깨진 파일/빈 workspace. 실제 `~/.claude` 기록 사용 금지(fixture 만)
  - 로그: 콘솔 텍스트, ERROR=패널 못 그림, WARN=일부 생략. 대화 내용·토큰/키 로그 금지
  - 보안: 비밀값 없음, `~/.claude` 인증 파일 비접근, 요청에서 파일 경로 받지 않음, pip-audit/npm audit(릴리스 전)
  - 의존성: 표준 라이브러리로 안 될 때만, MIT/Apache/BSD, 최근 1년 내 릴리스
  - Git: 작업 브랜치 → main PR, Conventional Commits, squash, 테스트 통과 필수, 프론트 변경 시 dist 동봉
  - DoD: 테스트·린트·타입 통과, dist 재빌드, 문서 갱신, run 스크립트로 화면 확인
  - Agent 금지(승인 없이): `~/.claude` 수정·삭제, 전역 settings 변경, 전역 패키지 설치. 불확실하면 STM 질문 + blocked
- 아키텍처 우선순위 (03): 1위 개발 속도(2주 MVP) ~ 2위 보안(로컬 전용, 대화 비접근) ~ 3위 유지보수성(예시로 읽히는 코드). 이하 가용성 4, 성능 5, 운영 비용 6, 확장성 7
  - 핵심 원칙: ① 설치·실행 단순(실행 파일 하나로 웹까지) ② 읽기 전용 우선(쓰기는 루프 제어뿐) ③ 의존성 최소
  - 스타일: 단일 프로세스 모놀리스(FastAPI 가 API + Vue dist 서빙), 조회 REST / 실시간 SSE, 서버 무상태(진실의 원천 = workspace/ 파일 + Claude Code 기록)
  - 금지: DB 서버, Docker 필수 구성, 외부 SaaS 전송. 허용: watchfiles(폴링보다 빠를 때만)
  - 안티패턴: 대시보드가 AI-DLC 파일 직접 수정(제어 파일 제외), 실행 전 Node 빌드 요구
  - ADR 필수: 사용량 수집 방식, 루프 제어 방식, 프론트 배포 방식(dist 포함), 새 외부 의존성 → `workspace/project/adr/ADR-xxx.md`
  - 관측성: 콘솔 로그 + `/api/v1/health`, 알림 대신 경고 배너
- 데이터 제약 (04):
  - 소스 5종: DS-01 workspace/memory(+archive), DS-02 aidlc.py check/status 출력, DS-03 `~/.claude/projects/<프로젝트>/*.jsonl`(개인정보), DS-04 status line 스냅샷 JSON, DS-05 팀 charter·40 문서
  - DS-03 은 `timestamp`, `message.model`, `message.usage`(input/output/cache_creation_input/cache_read_input tokens), `requestId` 만 추출. `message.content` 는 읽지 않음
  - 품질: usage 없는 줄 혼재, requestId 중복, `rate_limits` 는 Pro/Max + 세션 첫 응답 이후에만 존재
  - 규모: JSONL 세션당 수십 MB 가능 → 스트리밍·증분 집계 필요, EDA Q5 로 집계 시간 실측
  - 대시보드는 자체 데이터를 저장하지 않음(예외: 제어 파일). ML/AI 사용 없음
  - EDA 질문: 오늘/현재 5시간 토큰(입력·출력·캐시별), 모델별 비중, 팀별 Task 당 평균 토큰·시간(STM opened_at~archived_at 매핑), 캐시 적중률, 대용량 집계 시간

## 6. 분석 단계 진행 판단
- 결정: **GO** — 확신도 L 인 Must FR 이 없다(FR-001·004·005 는 M, FR-002·003 은 H. L 은 Could 인 FR-009·010 의 가정뿐). 충돌 3건(C1 마일스톤 vs NFR-001, C2 본문 비접근 vs JSONL 구조, C3 무상태 vs 성능)은 모두 사용자 의도를 바꾸지 않는 임시 가정으로 해소할 수 있고, 아키텍처 분석의 ADR(사용량 수집·루프 제어)에서 확정한다. 질문 13건은 분석과 병행해 답을 받으며, 특히 Q2·Q4·Q5·Q6 은 `/aidlc-plan` 전에 답이 필요하다.
