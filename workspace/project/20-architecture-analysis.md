---
doc: architecture-analysis
layer: project
author: architecture-analyst
status: draft
source_versions: [00@draft(2026-10-23 답변 적용), 10@draft, 30@draft, 02@0.1, 03@0.1]
---
# 20. 아키텍처 분석

> 입력: 00-interpretation.md(§4 답변 적용), 10-business-analysis.md, 30-data-analysis.md, user/02, user/03.
> 모든 판단은 user/03 의 **품질 속성 우선순위**로 채점합니다.
> 함께 확인한 프레임워크 파일: `aidlc/hooks/memory_cascade.py`, `aidlc/hooks/run.sh`, `aidlc/scripts/aidlc.py`, `.claude/settings.json`, `.claude/skills/aidlc-run/SKILL.md`.
> 표기: "원칙 n" = user/03 §1 의 n번 원칙, "03 §n" = user/03 의 절, "02 §n" = user/02 의 절.

## 1. 품질 속성 시나리오
| ID | 품질 속성 | 자극 (Stimulus) | 환경 | 기대 반응 | 측정 기준 | 출처 (NFR) |
|----|-----------|----------------|------|-----------|-----------|-----------|
| QS-01 | 성능 (첫 화면) | 사용자가 브라우저로 대시보드에 접속 | 서버 기동 완료, Task 100개 + 30일 가짜 JSONL(329~658 MB) fixture, 사용량 캐시 데우기 진행 중일 수 있음 | 메모리·파이프라인·Plan·제어 패널은 즉시, 사용량 패널은 최근 파일부터 읽은 부분 값 + `warming` 표시로 그린다 | 접속 → 모든 Must 패널 표시(값 또는 "데우는 중") ≤ 2초. 패널 REST 응답 p95 ≤ 200 ms(버킷 조회는 파싱 없음) | NFR-001, KPI-01 |
| QS-02 | 성능 (변경 반영) | short-term.md·tasks.md·`.control.json`·상태 스냅샷·JSONL 이 바뀜 | 대시보드가 열려 있고 SSE 연결 중 | 1초 주기 stat 폴링이 변경을 감지 → SSE `changed` 이벤트(topic) → 프론트가 해당 패널만 재조회 | 파일 수정 → 화면 반영 ≤ 5초 (목표 ≤ 2초). JSONL 증분 1 MB 처리 ≤ 10 ms | NFR-001, FR-008 |
| QS-03 | 가용성/신뢰성 (깨진 입력) | 파일 없음, frontmatter 깨짐, UTF-8 아님, JSON 줄 잘림, workspace 비어 있음 | 실행 중 서버 | 해당 패널만 `meta.status = error|empty` + 안내 문구, 다른 패널과 서버는 정상. WARN 로그 1줄(내용 없이 파일 종류·사유만) | 깨진 파일·빈 workspace 테스트에서 HTTP 500 = 0건, 프로세스 생존 100% | NFR-002 |
| QS-04 | 가용성/신뢰성 (데이터 소스 부재) | status line 스냅샷 없음 / `rate_limits` 없음 / Claude 프로젝트 디렉터리 못 찾음 | 비구독, 첫 응답 전, VS Code 패널에서 statusLine 미실행 | 사용량 패널은 토큰 집계만 + "한도 정보 없음" 안내, 스냅샷이 오래되면 `captured_at` 경과 시간 표시 | fixture 3종(스냅샷 없음, rate_limits 없음, 프로젝트 디렉터리 없음)에서 안내 표시율 100% | NFR-002, FR-004 |
| QS-05 | 보안 (네트워크 노출) | 같은 LAN 의 다른 PC 가 포트에 접속 / 악성 웹페이지가 DNS rebinding·CSRF 로 `POST /control/pause` 시도 | 사용자 PC, 대시보드 실행 중 | 127.0.0.1 바인딩이라 외부 접속 불가. Host 헤더가 `127.0.0.1:<port>`/`localhost:<port>` 가 아니면 400, POST 는 `Origin` 이 자기 자신이 아니거나 `Content-Type: application/json` 이 아니면 403 | 외부 IP 접속 실패, 잘못된 Host/Origin 테스트 거부율 100%. 바인딩 주소를 바꾸는 설정·옵션 0개 | NFR-003 |
| QS-06 | 보안 (대화 본문 비접근) | JSONL 에 본문·도구 결과·비밀값처럼 보이는 문자열이 있음 | 사용량 수집 중 | `"usage":` 없는 줄은 파싱 전 폐기, 파싱한 줄은 허용 필드만 복사 후 원본 폐기. 응답·로그·메모리 캐시에 본문·파일 경로·sessionId/requestId 원문 없음 | fixture 의 본문 표식 문자열이 API 응답 전체·로그에 0건(자동 테스트). `~/.claude` 에서 여는 경로가 `projects/<enc>/**/*.jsonl` 과 `settings.json`(statusLine 키만) 뿐임을 테스트로 확인 | NFR-003, CON-07 |
| QS-07 | 보안 (읽기 전용) | 모든 조회 API·SSE 를 반복 호출 | STM `status: closed` 상태를 포함한 fixture workspace | workspace 파일 변경 없음. 쓰기는 `POST /control/*` 가 `.control.json` 1개에만 | 조회 전후 workspace 전체 해시 불변(closed STM fixture 포함). 대시보드 프로세스의 쓰기 경로 = `.control.json` 1개 | CON-03, 원칙 2 |
| QS-08 | 개발 속도 | 1인 개발자가 2주 안에 M1 을 만들어야 함 | 2026-10-23 ~ 11-06 | 사용자 지정 스택(FastAPI·Vue·ECharts)과 Hook 판정 함수 재사용으로 새로 짤 코드를 줄인다. 위험 높은 FR-004·005 는 1주차 스파이크 | M1 범위(FR-001~005, SCOPE-01, FR-008 최소) 2026-11-06 완료. 스파이크 2건(대기 루프, statusLine) 1주차 초반 결론 | 01 §7, 03 §2 순위 1 |
| QS-09 | 유지보수성 | 새 기여자가 "예시 프로젝트"로 코드를 읽음 / Hook 판정 규칙이 바뀜 | 저장소 clone 직후 | 디렉터리 = 02 §3 그대로, 계층 api → services → models 단방향. cascade 판정은 Hook 모듈 함수를 그대로 써서 규칙이 한 곳에만 있음 | backend 라인 커버리지 ≥ 70%, ruff·eslint·vue-tsc 0 오류, Hook 규칙 대조 테스트(`aidlc.py status` 출력과 같은 결론) 통과 | 02 §2·§5, 03 §2 순위 3 |
| QS-10 | 설치·실행 단순성 (운영 비용) | 깨끗한 PC 에서 `run.bat` 더블클릭 / `./run.sh` | Python 3.11+ 설치됨, Node 없음, 인터넷 연결 | venv 생성 → 고정 버전 설치 → 서버 → 헬스 확인 → 브라우저 자동 열기. 재실행 시 requirements 해시가 같으면 설치 생략, 이미 떠 있으면 브라우저만 연다 | 실행 동작 1회, 첫 화면 ≤ 5분(첫 실행), 재실행 ≤ 10초. Windows 1회 + macOS/Linux 1회 리허설 | SCOPE-01, KPI-02, 원칙 1 |
| QS-11 | 가용성/신뢰성 (루프 제어) | 루프 실행 중 일시정지 → 30분·2시간 후 재개 / 2시간 초과 / 세션 닫힘 | `/aidlc-run 3` 실행 중 | Task 경계(cascade 완료 후)에서만 멈춤. 같은 세션이 대기 호출 반복 → 재개 시 남은 반복 진행. 2시간 초과 시 루프 정상 종료(STM 무변경). 세션이 사라지면 heartbeat 만료로 "세션 없음" 표시 | 일시정지/재개 시나리오 테스트 통과, 실제 리허설에서 수동 복구 0건, heartbeat 만료 감지 ≤ 2분 | FR-005, 10 §7 최상위 가정 1 |
| QS-12 | 확장성 (N/A 확인) | 사용자 2명 이상 / 여러 저장소 요구 | 단일 사용자 로컬 | 대상 아님. 단일 프로세스·프로세스 메모리 캐시로 충분하며 확장 설계를 하지 않는다 | 설계 검토에서 확장용 컴포넌트(큐, 외부 캐시, DB) 0개 | NFR-004 (N/A) |
| QS-13 | 규정/컴플라이언스 (N/A 확인) | 코드 변경으로 외부 호출이 끼어듦 | 실행 중 | 외부 네트워크 호출 없음(프론트도 CDN·폰트·텔레메트리 없음, dist 에 모두 포함) | 코드 리뷰 + 테스트: 백엔드 소켓 연결 대상이 127.0.0.1 뿐, dist 에 외부 URL 로드 0건. 예외: run.py 의 최초 pip 설치(PyPI) | NFR-005 (N/A), 03 §4 금지 |

## 2. 후보 아키텍처 비교
<!-- 최소 2개. 점수 = Σ(속성 점수 × 가중치), 가중치는 user/03 순위로 산정 -->
가중치 = 8 − 순위 (03 §2): 개발 속도 7, 보안 6, 유지보수성 5, 가용성/신뢰성 4, 성능 3, 운영 비용 2, 확장성 1. 점수 1~5 (5 = 가장 좋음), 칸 값 = 점수 × 가중치. 만점 140.

- **후보 A — 단일 FastAPI 프로세스 + 커밋된 Vue dist + 프로세스 메모리 증분 캐시 + stat 폴링/SSE.** `run.py` 하나가 venv·설치·uvicorn(127.0.0.1)·브라우저를 처리. AI-DLC 상태는 Hook 모듈의 읽기 전용 함수를 재사용, 사용량은 JSONL 증분 파싱 + status line 스냅샷 파일. 디스크에 자기 데이터 없음(제어 파일 제외).
- **후보 B — 표준 라이브러리 전용 서버(`http.server` + 스레드) + 바닐라 JS + 저장소에 넣은 ECharts 파일.** 의존성 0, 빌드 없음.
- **후보 C — 수집 데몬 + SQLite 파생 캐시 파일 + FastAPI 조회 서버(프로세스 2개).** 수집기가 JSONL 을 SQLite 로 적재, API 는 SQL 집계.

| 품질 속성 (가중치) | 후보 A: 단일 FastAPI 모놀리스 + dist + 메모리 캐시 | 후보 B: 표준 라이브러리 서버 + 바닐라 JS | 후보 C: 수집 데몬 + SQLite 캐시 + API |
|--------------------|---------|---------|---------|
| 개발 속도 (7) | 5 → 35 (지정 스택, Pydantic 검증·OpenAPI 자동, SSE 는 StreamingResponse) | 2 → 14 (라우팅·검증·SSE·OpenAPI·UI 상태 관리를 손으로, 02 스택과도 불일치) | 2 → 14 (프로세스 2개 기동·스키마·동기화 코드 추가) |
| 보안 (6) | 5 → 30 (127.0.0.1, 허용 필드만 메모리 보관, 쓰기 1파일, Host/Origin 가드 내장 미들웨어) | 4 → 24 (같은 정책 가능하지만 입력 검증·헤더 검사를 직접 구현해 실수 여지) | 3 → 18 (파생 데이터가 디스크에 남음 = 03 §5 "자체 데이터 저장 안 함" 위반, 노출면 증가) |
| 유지보수성 (5) | 4 → 20 (02 §3 구조 그대로, api/services/models 계층, Hook 규칙 재사용) | 2 → 10 (프레임워크 관례가 없어 예시 코드로 읽기 어렵고 DOM 조작 코드 비대) | 3 → 15 (SQL 스키마·마이그레이션 관리 추가) |
| 가용성/신뢰성 (4) | 4 → 16 (패널 단위 예외 격리, 재시작 시 캐시 재구축만) | 3 → 12 (스레드 서버의 예외·연결 관리 직접) | 3 → 12 (데몬 죽음·DB 잠금·캐시 손상 경로 추가) |
| 성능 (3) | 4 → 12 (버킷 조회 ms, 콜드 스타트는 데우기로 완화) | 4 → 12 (동일 알고리즘 가능) | 5 → 15 (재시작 후에도 캐시 유지로 콜드 스타트 없음) |
| 운영 비용 (2) | 5 → 10 (프로세스 1개, 설치 1회) | 5 → 10 | 3 → 6 (프로세스 2개 감시·정리) |
| 확장성 (1) | 2 → 2 | 1 → 1 | 4 → 4 |
| 합계 | **125** | 83 | 84 |

원칙 적합성 점검: B 는 원칙 3(의존성 최소)에 가장 충실하지만 02 §1 이 FastAPI·Vue·ECharts 를 지정하고(규칙 우선순위상 02 > 03) 03 §3·§4 도 같은 스택을 "선호"로 둬서 탈락. C 는 03 §5(자체 데이터 저장 안 함)·§3(서버 무상태)·원칙 1(실행 단순)에 어긋난다.

## 3. 선택 아키텍처
- 선택: **후보 A — 127.0.0.1 에 바인딩한 단일 FastAPI(uvicorn) 프로세스가 `/api/v1` REST + SSE 와 저장소에 커밋된 Vue 3 dist 를 함께 서빙하고, AI-DLC 파일·Claude Code 기록을 읽기만 하며(쓰기는 `workspace/memory/.control.json` 하나), 사용량은 프로세스 메모리 증분 캐시로 집계한다.** 실행은 루트 `run.py`(+ `run.bat`/`run.sh`) 한 번. (ADR-001)
- 근거 (원칙 번호 인용):
  - 원칙 1(설치·실행 단순): 프로세스 1개, Node 불필요(dist 커밋, ADR-005), DB·Docker 없음, `run.py` 가 venv·설치·브라우저까지 처리(ADR-001). 03 §10 안티패턴 "실행 전 Node 빌드" 회피.
  - 원칙 2(읽기 전용 우선): 서비스 계층은 읽기 전용. `aidlc.py status` 는 STM 을 아카이브하는 부작용이 있어(30 §3) 부르지 않고, Hook 모듈의 읽기 함수만 어댑터로 재사용(ADR-009). 대시보드가 쓰는 파일은 `.control.json` 하나(ADR-004). 대기 상태는 프레임워크 CLI 가 별도 파일에 쓰므로 대시보드 쓰기 범위는 늘지 않음.
  - 원칙 3(의존성 최소): 백엔드 런타임 직접 의존성 3개(fastapi, uvicorn, pydantic — 모두 02 지정). `uvicorn[standard]`·watchfiles 미사용(1초 stat 폴링으로 5초 요구 충족, ADR-008). SSE·파일 감시·JSONL 파싱·집계·런처는 표준 라이브러리. 프론트 런타임 의존성은 vue, echarts 2개(라우터·상태관리·차트 래퍼 라이브러리 없음, ADR-007).
  - 03 §2 순위 1(개발 속도)·3(유지보수성): 지정 스택 + Hook 판정 재사용으로 신규 코드 최소화, 02 §3 디렉터리 그대로. 순위 2(보안): 127.0.0.1 고정 + Host/Origin 가드 + 허용 필드 복사(ADR-002, ADR-011).
  - 03 §3: 조회 REST, 실시간 SSE, 서버 무상태 = "디스크에 자기 데이터를 영속하지 않음"으로 해석(00 C3). 메모리 파생 캐시는 재시작 시 재구축.
- 포기한 것 (트레이드오프):
  - 재시작 직후 30일치 콜드 스타트(실측 기준 1.45~2.89 s)를 피하지 못한다 → 최근 파일 우선 데우기 + `warming` 표시로 완화(후보 C 의 영속 캐시를 포기).
  - watchfiles 의 즉시 반응 대신 최대 약 1초 지연(5초 요구 대비 여유 충분).
  - 의존성 0(후보 B)을 포기하고 지정 스택을 따른다.
  - FR-006 cascade 이벤트는 파일 변화 추론이라 서버가 꺼져 있던 동안의 LTM/Task 갱신 시각은 근사값(ADR-010).
  - 일시정지 대기 중 약 9분마다 대기 호출 1회분 토큰을 쓴다(00 Q5 허용).

## 4. 컨텍스트 & 컴포넌트
```mermaid
flowchart LR
  user[사용자 브라우저] -->|HTTP 127.0.0.1 REST/SSE| app

  subgraph proc[단일 프로세스: uvicorn + FastAPI]
    app[API 앱 셸<br/>라우터·에러 포맷·Host/Origin 가드·StaticFiles]
    aidlc[AI-DLC 상태 리더]
    usage[사용량 수집기<br/>증분 캐시]
    snap[상태 스냅샷 리더]
    ctl[루프 제어 서비스]
    watch[변경 감지 + SSE 허브]
    app --> aidlc & usage & snap & ctl & watch
  end

  app -->|정적 파일| dist[(monitor/frontend/dist<br/>커밋된 Vue 빌드)]
  aidlc -->|read| ws[(workspace/memory, project, teams)]
  aidlc -->|import 읽기 함수| mc[aidlc/hooks/memory_cascade.py]
  aidlc -->|subprocess sys.executable| chk[aidlc.py check user/project/docs]
  usage -->|read 증분| jsonl[(~/.claude/projects/enc/**/*.jsonl)]
  snap -->|read| cs[(workspace/memory/.monitor/claude-status.json)]
  ctl -->|write 유일| cf[(workspace/memory/.control.json)]
  ctl -->|read| ls[(workspace/memory/.monitor/loop-status.json)]
  watch -->|stat 1초| ws & jsonl & cs & cf & ls

  subgraph cc[Claude Code 세션 VS Code/CLI]
    sl[status line 스크립트<br/>aidlc/hooks/statusline.sh+py] -->|원자적 write| cs
    sl -->|체이닝 실행| gsl[사용자 전역 statusLine 명령]
    run[/aidlc-run 스킬/] -->|loop-start/loop-check/wait-resume/loop-end| cli[aidlc.py loop 명령]
    cli -->|read| cf
    cli -->|write| ls
    hook[memory_cascade Hook] -->|write| ws
  end

  launcher[run.bat / run.sh → run.py] -->|venv·pip·uvicorn·browser| proc
```

디렉터리 배치 (02 §3 준수, 추가분은 굵게):
```
run.py  run.bat  run.sh
monitor/
  backend/requirements.txt  backend/requirements-dev.txt
  backend/app/main.py  config.py  logging_config.py
  backend/app/api/        health, pipeline, plan, tasks, memory, teams, timeline, usage, alerts, control, events
  backend/app/services/   aidlc_reader, gates, pipeline, tasks, teams, timeline, statusline_reader, control, watcher, usage/(resolver, cursor, privacy_filter, aggregator, warmup)
  backend/app/models/     Pydantic 응답·요청 모델
  backend/scripts/export_openapi.py
  backend/tests/          (fixtures/ 가짜 workspace·JSONL·스냅샷 생성기)
  frontend/src/           views/, components/panels/, api/, composables/
  frontend/dist/          (커밋)
aidlc/hooks/statusline.sh  statusline.py         ← status line (ADR-003)
aidlc/scripts/loop_control.py  (+ aidlc.py 서브커맨드) ← 루프 제어 CLI (ADR-004)
workspace/memory/.control.json                    ← 대시보드가 쓰는 유일한 파일 (gitignore)
workspace/memory/.monitor/{claude-status.json, loop-status.json}  (gitignore)
workspace/project/contracts/openapi.json
```

| 컴포넌트 | 책임 | 기술 | 소유 팀 (예정) | 의존 |
|----------|------|------|----------------|------|
| 원클릭 런처 (`run.py`, `run.bat`, `run.sh`) | Python 3.11+ 탐지(run.sh 는 `aidlc/hooks/run.sh` 방식으로 python3/python/py 를 실제 실행해 확인, run.bat 는 `py -3` → `python` 순서, Store 별칭 배제), `monitor/.venv` 생성, requirements 해시 마커로 재설치 생략, 포트 선택(기본 8765, 사용 중이면 자기 서버인지 `/api/v1/health` 로 확인 후 브라우저만 열거나 다음 포트), uvicorn 127.0.0.1 기동, 헬스 대기 후 `webbrowser.open` | Python 표준 라이브러리(venv, subprocess, urllib, webbrowser, hashlib), bash, cmd | cicd | requirements.txt, API 앱 셸, ops(헬스) |
| 의존성 고정 & 빌드 산출물 관리 | `requirements.txt`(런타임, 전이 의존성까지 `==` 고정), `requirements-dev.txt`, `package-lock.json`, dist 재빌드 절차와 dist 신선도 검사 스크립트(소스 해시 ↔ `dist/.build-meta.json`), `.gitignore` 갱신(.venv, node_modules, .control.json, .monitor/), pip-audit/npm audit 절차 | pip, npm, Python 스크립트 | cicd | 프론트 앱, API 앱 셸 |
| API 앱 셸 (`app/main.py`, `config.py`) | 앱 팩토리, 라우터 등록, 예외 핸들러 → `{"error":{code,message}}`, 422 → `VALIDATION_ERROR` 변환, TrustedHost + Origin 가드, dist `StaticFiles(html=True)` 마운트, 경로 설정 주입(AIDLC_ROOT, CLAUDE_HOME — 테스트에서 fixture 경로로 교체), OpenAPI export 스크립트 | FastAPI, Starlette 내장 미들웨어, Pydantic | backend (리뷰: architecture, security) | 모든 서비스, ops |
| AI-DLC 상태 리더 (`services/aidlc_reader.py`, `pipeline.py`, `tasks.py`, `gates.py`, `teams.py`) | `memory_cascade.py` 를 importlib 로 읽어 `read_doc`, `Memory.phases/archived/latest_seq/pending/load_state` 만 허용 목록으로 호출(쓰기 함수 호출 금지), 단계 0~6 판정(00 A11), Task 줄 파싱·필터, Gate = `aidlc.py check <layer>` 서브프로세스(`sys.executable`, timeout 10 s, 결과 TTL 5 s), 팀 = `workspace/teams/*/charter.md` + 40 문서, 리뷰 PASS/FAIL 추출(STM §7, archive). 파일별 mtime 캐시, 패널 단위 예외 격리 | Python 표준 라이브러리(re, pathlib, subprocess, importlib) | backend | memory_cascade.py(프레임워크, 읽기), workspace 파일 |
| 사용량 수집기 (`services/usage/`) | 프로젝트 디렉터리 해석(ADR-002), `**/*.jsonl` 재귀 탐색(30일 mtime), 파일 커서(inode·size·mtime·offset) 증분 읽기, `"usage":` 사전 필터 → 허용 필드 복사 → 원본 폐기, requestId 중복 제거(전역, last-wins), UTC 시간 버킷(시간×모델×sidechain), 서버 시작 시 백그라운드 데우기(최근 파일 우선) + 진행률 | Python 표준 라이브러리(os.scandir, json, datetime, threading/asyncio) | backend (리뷰: security) | `~/.claude/projects/<enc>/` (읽기), 상태 스냅샷(transcript 디렉터리 힌트) |
| 상태 스냅샷 리더 (`services/statusline_reader.py`) | `claude-status.json` 읽기, 스키마 버전 확인, nullable 필드 처리, `captured_at` 경과 시간 계산(오래됨 판정 10분), 5시간 구간 경계 = `resets_at − 5h` | 표준 라이브러리 | backend | status line 스크립트 |
| Status line 스크립트 (`aidlc/hooks/statusline.sh`, `statusline.py`) + `.claude/settings.json` `statusLine` 등록 | stdin JSON 에서 허용 필드만 골라 원자적 저장(임시 파일 → `os.replace`), 짧은 한 줄 출력, 사용자 전역 statusLine 명령 체이닝(같은 stdin, timeout 2 s, 자기 자신 재귀 방지), 어떤 오류에도 exit 0 | bash 런처 + Python 표준 라이브러리 | backend (리뷰: security, architecture) | Claude Code statusLine 기능, `~/.claude/settings.json`(statusLine 키만 읽기) |
| 변경 감지 & SSE 허브 (`services/watcher.py`, `api/events.py`) | 감시 대상 파일·디렉터리 stat 1초 폴링 → topic(pipeline, plan, tasks, memory, teams, timeline, usage, control, alerts) 단위 변경 이벤트, 연결별 asyncio 큐, 15초 keep-alive 주석, 연결 수 상한(8) | asyncio, FastAPI StreamingResponse | backend | 모든 리더 |
| 루프 제어 서비스·API (`services/control.py`, `api/control.py`) | `.control.json` 원자적 쓰기(유일한 쓰기), `seq` 증가, `loop-status.json` 과 조합한 화면 상태 판정(running / pause_requested / paused / resume_requested / no_session / ended) | 표준 라이브러리, Pydantic | backend (리뷰: security, architecture) | 루프 제어 CLI(파일 계약) |
| 루프 제어 CLI (`aidlc/scripts/loop_control.py`, `aidlc.py loop-start/loop-check/wait-resume/loop-end`) | 루프 시작 기준 seq 기록, 사이클 경계 확인, 대기(1초 폴링, 최대 540 s/호출, 30 s heartbeat), 누적 일시정지 상한(기본 7200 s), exit code 계약, `loop-status.json` 쓰기 | Python 표준 라이브러리 | backend (리뷰: architecture, qa) | `.control.json`(읽기) |
| aidlc-run 스킬 변경 (`.claude/skills/aidlc-run/SKILL.md`) | 시작 시 `loop-start N`, 각 사이클 7단계 후 `loop-check`, 일시정지면 `wait-resume` 반복 호출 규칙(Bash timeout 600000), 종료 시 `loop-end`, Windows Python 명령 안내 | Markdown (스킬) | architecture (리뷰: qa, ops) | 루프 제어 CLI |
| 프론트 앱 셸 & 레이아웃 (`App.vue`, `views/DashboardView.vue`, 테마) | Grafana 스타일 다크 테마, 12열 패널 그리드, 상단 경고 배너 영역, 상단 행 = KPI-01 세 질문(단계·현재 Task·5시간 %) | Vue 3 + TypeScript strict, CSS 변수 | frontend | 패널, API 클라이언트 |
| 패널 컴포넌트 (`components/panels/*.vue`) | Pipeline/Gate, Plan 진행률 바, Task 표(팀·상태 필터), Memory/cascade, 사용량(5h·7d 게이지, 토큰 시계열 스택 차트, 모델별 표, 비용 stat), 루프 제어 버튼·상태, Timeline(M2), Teams(M2), Alerts(M2). 패널별 empty/error/warming 상태 | Vue 3, ECharts(echarts/core 트리 셰이킹, gauge·line·bar) | frontend | API 클라이언트 |
| API 클라이언트 & 실시간 (`src/api/client.ts`, `types.ts`, `composables/useEventStream.ts`, `usePanel.ts`) | fetch 래퍼(에러 포맷 해석), OpenAPI 와 맞춘 TS 타입, EventSource 구독 → topic 별 재조회, 연결 실패 시 5초 폴링 폴백·지수 재연결 | TypeScript, 브라우저 EventSource | frontend | API 계약 |
| 관측성 (`app/logging_config.py`, `api/health.py`) | 콘솔 텍스트 로그(시각·레벨·메시지, 본문·경로·ID 금지), `/api/v1/health` = 생존 + 소스별 접근 가능 여부 + 캐시 데우기 진행률 + 앱 식별자(런처의 중복 실행 판정용) | logging(표준), FastAPI | ops | 모든 리더 |
| 테스트 스위트 & fixture (`monitor/backend/tests`, `frontend/src/**/*.spec.ts`) | 가짜 workspace(빈/일부/전체/깨짐/closed STM), 가짜 JSONL 생성기(30 EDA `bench_synthetic.py` 이식, 본문 표식 문자열 포함), 스냅샷 fixture, 일시정지/재개 시나리오, Hook 규칙 대조, 해시 불변·본문 비노출 테스트, 성능 테스트(Task 100 + 30일), vitest | pytest, TestClient, pytest-cov, vitest | qa | 모든 컴포넌트 |
| API 계약 & ADR (`workspace/project/contracts/openapi.json`, `adr/`, `docs/api/reference.md` 재생성) | 엔드포인트·스키마·에러 코드 단일 기준, 파일 계약(.control.json, loop-status.json, claude-status.json 스키마) 문서화, 깨지는 변경 리뷰 | OpenAPI 3.1, `aidlc/scripts/openapi_docs.py` | architecture | backend, frontend |
| 보안 정책 (허용 필드 목록, Host/Origin 정책, `~/.claude` 접근 범위, 의존성 점검) | Q2 규칙을 코드 리뷰 체크리스트로 고정, 릴리스 전 pip-audit/npm audit | 리뷰 체크리스트 | security | 사용량 수집기, status line 스크립트, API 앱 셸 |
| 수용 기준 & KPI 사용 테스트 | FR 수용 기준, KPI-01 질문 3개 사용 테스트, KPI-02 설치 리허설 기록, 단계 판정 기준(A11)·cascade 막힘 기준(A10) 확인 | 문서 | product | 전체 |

제안 팀: core 6(product, architecture, qa, cicd, ops, security) + **backend, frontend**. data/analytics/ml/dba 는 30 §7 결론대로 만들지 않는다. integration 은 외부 연동이 Claude Code 하나(파일 2종)라 backend 에 포함. design 은 화면 1개·흐름이 짧아 frontend 가 겸한다. docs 는 공개 API·운영 매뉴얼이 없어 `/aidlc-docs` 를 오케스트레이터가 수행(team-architect 판단).

## 5. 주요 데이터 흐름 & 인터페이스
| 흐름 | 출발 → 도착 | 방식 (sync/async) | 계약 (API/이벤트 스키마) |
|------|-------------|-------------------|--------------------------|
| F1 상태 조회 | 프론트 → API | sync REST | `GET /api/v1/{health, pipeline, plan, tasks, memory, teams, timeline, usage/summary, usage/timeseries, usage/cost, alerts, control}`. 성공 응답 공통 봉투 `{"data": {...}, "meta": {"status": "ok|partial|empty|error|warming", "warnings": [], "error": {"code","message"} 또는 null, "generated_at": ISO, "source_mtime": ISO 또는 null}}`. 소스 문제(파일 없음·깨짐)는 HTTP 200 + `meta.status` 로 패널에만 영향(NFR-002). 요청 오류는 HTTP 4xx/5xx + `{"error":{"code","message"}}` (02 §6) |
| F2 실시간 변경 알림 | API → 프론트 | async SSE `GET /api/v1/events` | `event: changed` `data: {"topics": ["memory","tasks"], "at": ISO}` / `event: warming` `data: {"progress": 0.0~1.0}` / `event: ready` / 15초마다 `: keep-alive`. 프론트는 topic 해당 패널만 재조회. SSE 실패 시 5초 폴링 |
| F3 루프 제어 요청 | 프론트 → API → `.control.json` | sync REST | `POST /api/v1/control/pause`, `POST /api/v1/control/resume` (본문 `{}` 또는 `{"max_pause_sec": 600~86400}`, `Content-Type: application/json` 필수). 응답 = `GET /api/v1/control` 과 같은 `ControlView`. 활성 루프 없음 → 409 `NO_ACTIVE_LOOP`, 이미 같은 상태 → 200(멱등) |
| F4 제어 파일 계약 | API(쓰기) → 루프 제어 CLI(읽기) | async 파일 | `workspace/memory/.control.json` = `{"schema": 1, "seq": int, "state": "running|pause", "requested_at": ISO, "max_pause_sec": 7200}`. 쓰기 주체 = 대시보드만, 원자적 교체 |
| F5 루프 상태 계약 | 루프 제어 CLI(쓰기) → API(읽기) | async 파일 | `workspace/memory/.monitor/loop-status.json` = `{"schema": 1, "run_id", "state": "running|paused|ended", "baseline_seq", "iterations_total", "iterations_done", "started_at", "heartbeat_at", "paused_since", "ended_reason": "done|blocked|pause_timeout|no_task|null"}`. 쓰기 주체 = CLI 만 |
| F6 루프 경계 확인 | aidlc-run 스킬 → CLI | sync (Bash 도구) | `aidlc.py loop-start <N>` → 0 / `loop-check <done>` → 0 계속, 10 일시정지 요청 / `wait-resume` → 0 재개, 10 아직 일시정지(다시 호출), 20 상한 초과(루프 종료), 2 제어 파일 오류(계속 진행 + 경고) / `loop-end <reason>` → 0 |
| F7 status line 스냅샷 | Claude Code → statusline 스크립트 → 스냅샷 파일 → 스냅샷 리더 | async (Claude Code 이벤트 + `refreshInterval: 30`) | `claude-status.json` = `{"schema": 1, "captured_at": ISO, "claude_version", "model_id", "session_hash": sha256(session_id)[:12], "transcript_dir_name", "rate_limits": {"five_hour": {"used_percentage", "resets_at"}, "seven_day": {...}} 또는 null, "cost": {"total_cost_usd", "total_duration_ms"}, "context_window": {"used_percentage", "context_window_size"}}`. 단위: 퍼센트 0~100, resets_at = epoch 초(공식 문서 확인) |
| F8 사용량 수집 | JSONL → 사용량 수집기 | async 증분(1초 stat, 백그라운드) | 허용 필드: `timestamp`, `requestId`, `message.model`, `message.usage.{input_tokens, output_tokens, cache_creation_input_tokens, cache_read_input_tokens}`, `isSidechain`, (디렉터리 해석 폴백 때만) `cwd`. 그 밖의 키는 접근하지 않음 |
| F9 AI-DLC 상태 읽기 | workspace 파일 → AI-DLC 상태 리더 | sync (요청 시, mtime 캐시) | Hook 의 `read_doc`/`Memory.*` 읽기 함수, `aidlc.py check <layer>` 출력 정규식(`(OK|TODO)\s+(\S+)\s+\((\d+)개 미작성\)`, `MISSING\s+(\S+)`, `GATE (PASS|FAIL) — .*미작성 (\d+)개, 누락 문서 (\d+)개`) |
| F10 OpenAPI 내보내기 | FastAPI → 계약 파일 → 레퍼런스 | 빌드 시 | `python monitor/backend/scripts/export_openapi.py` → `workspace/project/contracts/openapi.json` → `aidlc/scripts/openapi_docs.py render ... -o docs/api` (같은 Task 안에서) |

**엔드포인트 목록 (M1 = 굵게)**
| 메서드 | 경로 | FR | 비고 |
|--------|------|----|------|
| GET | **`/api/v1/health`** | CON-05 | `{status, app: "aidlc-monitor", version, sources: {workspace, claude_projects, statusline, control}, usage_warming}` |
| GET | **`/api/v1/pipeline`** | FR-001 | 단계 0~6 상태 + Gate 3종(PASS/FAIL, 미작성 수, 누락 수, 확인 시각) |
| GET | **`/api/v1/plan`** | FR-002 | current_phase, completed_phases, Phase 별 total/checked/진행률 |
| GET | **`/api/v1/tasks`** | FR-002 | 쿼리 `team`, `status=open|done|blocked|active`, `phase` (Pydantic 검증, enum) |
| GET | **`/api/v1/memory`** | FR-003 | STM(status, task, team, opened_at, 경과 초), LTM rev, last_merged_stm, synced_ltm_rev, 미처리 cascade level, Stop 차단 횟수 |
| GET | **`/api/v1/usage/summary`** | FR-004 | 한도(5h/7d %, resets_at, 스냅샷 경과), 세션 비용, 오늘·현재 5시간 구간 토큰 4종, 캐시 적중률, `limits_available` |
| GET | **`/api/v1/usage/timeseries`** | FR-004 | 쿼리 `range=5h|24h|7d|30d`, `bucket=hour|day`, `group=model|sidechain|none`, `tz_offset_min`(로컬 날짜 경계) |
| GET | **`/api/v1/control`** | FR-005 | `ControlView{state, requested_at, paused_since, heartbeat_at, heartbeat_age_sec, iterations_done, iterations_total, max_pause_sec, remaining_pause_sec}` |
| POST | **`/api/v1/control/pause`** | FR-005 | 유일한 쓰기(+resume) |
| POST | **`/api/v1/control/resume`** | FR-005 | |
| GET | **`/api/v1/events`** | FR-008 | SSE (M1 은 memory·control·usage·tasks topic, M2 전 topic) |
| GET | `/api/v1/timeline` | FR-006 | 쿼리 `limit`(≤ 200). STM 작업 로그(§3) 줄 + 추론 이벤트(ADR-010) |
| GET | `/api/v1/teams` | FR-007 | 팀별 할당/완료, 최근 리뷰 PASS/FAIL |
| GET | `/api/v1/usage/cost` | FR-009 | `monitor/pricing.json` 있을 때만, 없으면 `meta.status=empty` |
| GET | `/api/v1/alerts` | FR-010 | 조건 3종(cascade 막힘, blocked Task, 한도 ≥ 80%) |
| GET | `/`, `/assets/*` | - | dist 정적 파일(OpenAPI 에서 제외) |

에러 코드: `VALIDATION_ERROR`(422), `NOT_FOUND`(404), `BAD_HOST`(400), `FORBIDDEN_ORIGIN`(403), `NO_ACTIVE_LOOP`(409), `CONTROL_WRITE_FAILED`(500), `INTERNAL_ERROR`(500). 패널 `meta.error.code`: `SOURCE_MISSING`, `SOURCE_PARSE_ERROR`, `SOURCE_UNREADABLE`, `GATE_TIMEOUT`, `PROJECT_DIR_NOT_FOUND`, `SNAPSHOT_STALE`.

## 6. 배포 & 인프라
- 환경: 사용자 PC 단일 로컬 환경(Windows / macOS / Linux). 서버·클라우드·컨테이너·DB 없음(03 §4·§6). 프로세스 1개(uvicorn, worker 1, `--host 127.0.0.1` 하드코딩), venv 는 `monitor/.venv`. 포트 기본 8765(`--port` 또는 환경변수로만 변경, 호스트는 변경 불가).
- 배포 파이프라인 개요: 원격 CI/CD 없음(01 §3 Out of scope). "배포" = 저장소 main 브랜치 자체.
  1. 개발자: frontend 소스 변경 시 `npm ci && npm run build` → `monitor/frontend/dist` 와 `dist/.build-meta.json`(소스 해시) 을 같은 PR 에 포함(02 §4, ADR-005).
  2. PR 전 로컬 점검(cicd 가 스크립트로 묶음): ruff format --check, ruff check, pytest --cov(≥ 70%), dist 신선도 검사, eslint, vue-tsc, vitest, OpenAPI export 후 diff 없음 확인.
  3. 릴리스 전 수동: pip-audit, npm audit(02 §8).
  4. 사용자: `run.bat`/`run.sh` → `run.py` (최초: venv + `pip install -r monitor/backend/requirements.txt`, 이후: 해시 같으면 생략) → uvicorn → `/api/v1/health` 200 대기(최대 20 s) → 브라우저.
  5. Status line·루프 제어 CLI 는 프레임워크 파일이라 저장소에 포함되어 바로 동작(`.claude/settings.json` 커밋, 첫 세션에서 workspace trust 수락 필요).
- 관측성: 콘솔 텍스트 로그(`%(asctime)s %(levelname)s %(message)s`), ERROR = 패널을 못 그림, WARN = 파일 누락·형식 오류(파일 종류와 건수만, 내용·경로·ID 미출력), 시작 시 INFO 로 데이터 소스 해석 결과(찾음/못 찾음만). `/api/v1/health`. 알림 대신 화면 상단 경고 배너(FR-010). uvicorn access log 는 기본 끔(쿼리 문자열 노출 최소화).

## 7. 기술 스택 확정안
버전은 2026-10-23 웹 확인(출처 아래). requirements.txt 는 구현 Task 에서 venv 에 설치한 뒤 전이 의존성까지 `==` 로 고정한다.

| 영역 | 기술 | 버전 | user/02·03 근거 |
|------|------|------|----------------|
| 런타임 | Python | 3.11+ (테스트 3.11·3.13) | 02 §1. Hook 은 3.10+ 이지만 Monitor 는 3.11+ |
| 웹 프레임워크 | FastAPI | 0.161.1 (MIT, py ≥ 3.10) | 02 §1, 03 §4 선호. ADR-006 |
| ASGI 서버 | uvicorn (기본 설치, `[standard]` 아님) | 0.54.0 (BSD-3, py ≥ 3.10) | 02 §1, 원칙 3. ADR-006 |
| 검증/스키마 | Pydantic v2 | 2.14.1 (MIT) | 02 §2 "API 입출력은 Pydantic". ADR-006 |
| 파일 변경 감지 | 표준 라이브러리 stat 폴링 1초 (watchfiles 미사용) | - | 03 §4 "폴링보다 빠를 때만 허용", 원칙 3. ADR-008 |
| SSE | FastAPI `StreamingResponse` (`text/event-stream`) | - | 03 §3, 00 CON-02 (추가 라이브러리 없음) |
| 데이터 처리 | Python 표준 라이브러리 (json, re, datetime, os, hashlib) | - | 02 §1 Data |
| 프론트 언어 | TypeScript (strict) | 5.x 마지막 안정판 고정 (npm latest 는 7.0.2 이나 02 §1 이 TS 5 지정 → `typescript@~5` 로 고정, 구현 Task 에서 정확한 버전 기록) | 02 §1·§2 |
| UI 프레임워크 | Vue 3 | 3.5.44 (MIT) | 02 §1, 03 §4. ADR-007 |
| 번들러 | Vite (+ @vitejs/plugin-vue) | 8.3.5 (MIT, 개발자만 Node ^20.19 또는 ≥ 22.12) | 02 §1. ADR-007. 사용자 PC 에는 Node 불필요 |
| 차트 | Apache ECharts (`echarts/core` 모듈 import) | 6.1.0 (Apache-2.0) | 02 §1, 03 §4. ADR-007 |
| 타입 검사 | vue-tsc | TS 5 호환 버전 고정 | 02 §10 |
| 백엔드 테스트 | pytest, pytest-cov, httpx(TestClient 요구) | 구현 시 최신 고정 (dev 전용) | 02 §5 |
| 프론트 테스트 | vitest, @vue/test-utils, jsdom | 구현 시 최신 고정 (dev 전용) | 02 §5 |
| 린트/포맷 | ruff / eslint + eslint-plugin-vue + typescript-eslint + prettier | 구현 시 최신 고정 (dev 전용) | 02 §2 |
| 의존성 점검 | pip-audit, npm audit | dev 전용 | 02 §8 |
| 런처 | `run.py`(표준 라이브러리) + `run.sh`(bash) + `run.bat`(cmd) | - | 02 §3, 03 §6, 원칙 1. ADR-001 |
| Status line | bash 런처 + Python 표준 라이브러리, `statusLine.refreshInterval: 30` | Claude Code statusLine 기능 | 00 Q4, ADR-003 |
| 금지 확인 | DB 서버, Docker, 외부 SaaS 전송, CDN 로드 | 사용 안 함 | 03 §4 |

출처:
- [FastAPI — PyPI](https://pypi.org/pypi/fastapi/json), [uvicorn — PyPI](https://pypi.org/pypi/uvicorn/json), [pydantic — PyPI](https://pypi.org/pypi/pydantic/json), [watchfiles — PyPI](https://pypi.org/pypi/watchfiles/json)
- [vue — npm](https://registry.npmjs.org/vue/latest), [vite — npm](https://registry.npmjs.org/vite/latest), [echarts — npm](https://registry.npmjs.org/echarts/latest), [typescript dist-tags — npm](https://registry.npmjs.org/-/package/typescript/dist-tags)
- [Claude Code status line 문서](https://code.claude.com/docs/en/statusline) (stdin 필드, `rate_limits` 단위, `refreshInterval`, 300 ms 디바운스·실행 중 취소, workspace trust, Windows 는 Git Bash 또는 PowerShell 로 실행)
- Bash 도구 timeout(기본 120 s, 최대 600 s): [claude-code issue #34138](https://github.com/anthropics/claude-code/issues/34138), [Bash tool reference 미러](https://vineetagarwal-code-claude-code.mintlify.app/reference/tools/bash), [timeout 가이드 #5615](https://github.com/anthropics/claude-code/issues/5615)

## 8. ADR 목록
| ADR | 제목 | 상태 | 파일 |
|-----|------|------|------|
| ADR-001 | 단일 FastAPI 프로세스 모놀리스 + 원클릭 런처(run.py) | 제안 | `workspace/project/adr/ADR-001-single-process-monolith-and-launcher.md` |
| ADR-002 | 사용량 데이터 수집: JSONL 증분 파싱 + 허용 필드 복사 + 프로세스 메모리 캐시 (03 §9 필수) | 제안 | `workspace/project/adr/ADR-002-usage-data-collection.md` |
| ADR-003 | 한도·비용 수집: 프로젝트 statusLine 스냅샷 + 사용자 전역 statusLine 체이닝 (03 §9 필수) | 제안 | `workspace/project/adr/ADR-003-statusline-snapshot.md` |
| ADR-004 | 루프 제어: 제어 파일 + 사이클 경계 확인 + 같은 세션 대기 CLI (03 §9 필수) | 제안 | `workspace/project/adr/ADR-004-loop-control.md` |
| ADR-005 | 프론트 배포: 빌드된 dist 를 저장소에 커밋 (03 §9 필수) | 제안 | `workspace/project/adr/ADR-005-frontend-dist-committed.md` |
| ADR-006 | 백엔드 외부 의존성: FastAPI·uvicorn(기본)·Pydantic 만 (03 §9 필수) | 제안 | `workspace/project/adr/ADR-006-backend-dependencies.md` |
| ADR-007 | 프론트 외부 의존성: Vue 3·ECharts 런타임 + Vite·TS 개발 도구 (03 §9 필수) | 제안 | `workspace/project/adr/ADR-007-frontend-dependencies.md` |
| ADR-008 | 파일 변경 감지: stat 폴링, watchfiles 미도입 (03 §9 필수) | 제안 | `workspace/project/adr/ADR-008-change-detection-polling.md` |
| ADR-009 | AI-DLC 상태 읽기: Hook 읽기 함수 재사용, `status` 서브프로세스 금지, `check` 서브프로세스 허용 | 제안 | `workspace/project/adr/ADR-009-aidlc-state-read-only-access.md` |
| ADR-010 | FR-006 cascade 이벤트 출처: 파일 변화 추론 (Hook 이벤트 로그 보류) | 제안 | `workspace/project/adr/ADR-010-cascade-event-source.md` |
| ADR-011 | API 계약 규칙과 로컬 보안 가드 (봉투·에러 포맷·Host/Origin) | 제안 | `workspace/project/adr/ADR-011-api-contract-and-local-security.md` |

## 9. 아키텍처 리스크 & 기술 부채 예상
| ID | 리스크 | 확률 | 영향 | 대응 |
|----|--------|------|------|------|
| R-01 | 같은 세션 대기(`wait-resume` 반복 호출)가 실제로 동작하지 않거나, Bash 도구에 문서와 다른 낮은 실질 상한(보고된 약 48~73 s)이 있음 | M | H | 1주차 초반 스파이크(30분·2시간 리허설, 호출당 토큰 측정). `--max-wait` 를 설정값으로 두어 상한이 낮으면 50 s 로 낮춤(토큰 증가 감수). 실패 시 후퇴안: 루프 정상 종료 + 재개 시 "다시 `/aidlc-run <남은 수>`" 안내(ADR-004 대안 B) |
| R-02 | VS Code 확장 채팅 패널에서 statusLine 이 실행되지 않음 | M | M | FR-004 폴백(토큰만 + 안내 + 스냅샷 경과 시간). 1주차 실측 Task. 미지원이면 "CLI 세션에서 한도 표시" 안내(00 Q13) |
| R-03 | Claude Code JSONL·statusLine 스키마가 비공식이라 바뀜 | M | M | 파서는 필드 누락에 관대(WARN 건수), 스냅샷 `schema` 버전, 중복 usage 가 달라지면 last-wins 보정(30 §6). 형식 변경 감지 시 health 에 표시 |
| R-04 | 프로젝트 디렉터리 인코딩 규칙(영숫자 외 문자 → `-`)이 Windows 경로(`C:\x\y` → `C--x-y`)·비 ASCII 경로에서 다름 | M | M | 해석 3단계(ADR-002): 규칙 인코딩 → 스냅샷 `transcript_dir_name` → `projects/*` 중 usage 줄의 `cwd` 가 저장소 경로와 같은 디렉터리 탐색. Linux 는 실측 확인(`/home/user/chatbot` → `-home-user-chatbot`), Windows·macOS 는 리허설에서 확인 |
| R-05 | 30일 콜드 스타트가 느린 PC(HDD, Windows Defender 실시간 검사)에서 수 초~십수 초 | M | L | 최근 파일 우선 데우기, `warming` 진행률, 첫 화면은 비사용량 패널 먼저. 성능 fixture 로 측정 |
| R-06 | Hook 모듈(`memory_cascade.py`)을 import 하면 프레임워크 변경에 결합되고, 실수로 쓰기 함수를 부를 위험 | L | H | 어댑터 허용 목록, 금지 함수 호출을 막는 테스트(쓰기 함수 monkeypatch → 호출 시 실패), closed STM fixture 해시 불변 테스트(ADR-009) |
| R-07 | dist 가 소스와 어긋난 채 커밋됨 | M | M | `dist/.build-meta.json` 소스 해시 검사 테스트(cicd), PR 체크리스트(02 §4) |
| R-08 | 로컬 웹페이지의 CSRF/DNS rebinding 으로 일시정지 남용 | L | M | Host 허용 목록, POST Origin 검사 + JSON Content-Type 강제, CORS 미설정(ADR-011) |
| R-09 | Windows 에서 bash 부재(Git Bash 없음) 시 Hook·statusLine 미실행, `/aidlc-run` 스킬의 `python3` 명령 실패 | M | M | 기존 Hook 과 같은 전제(bash 필요)를 README 에 명시. 스킬에 "python3 가 없으면 python/py" 안내 추가(architecture). statusLine 실패는 FR-004 폴백으로 흡수 |
| R-10 | 대시보드와 CLI 가 같은 파일을 동시에 써서 요청 유실 | L | H | 파일별 단일 작성자(.control.json = 대시보드, loop-status.json = CLI) + 원자적 교체 + `seq`/`baseline_seq` 로 오래된 요청 무시(ADR-004) |
| R-11 | 사용자 전역 statusLine 체이닝이 느려 Claude Code 가 스크립트를 취소 → 스냅샷 미저장 | M | L | 스냅샷을 먼저 저장한 뒤 체이닝 실행(timeout 2 s), 자기 자신 재귀 방지 |
| R-12 | FR-006 추론 타임라인은 서버가 꺼져 있던 동안의 LTM·Task 갱신 시각이 부정확 (기술 부채) | H | L | 화면에 "추정" 표기, Hook 이벤트 로그는 사용자 승인 후 후속 ADR(ADR-010) |
| R-13 | `aidlc.py check` 서브프로세스가 요청마다 돌면 느려짐 | L | L | 결과 TTL 5 s + 대상 파일 mtime 이 같으면 재사용, timeout 10 s(`GATE_TIMEOUT`) |
| R-14 | `/aidlc-run` 0단계가 이미 `aidlc.py status` 로 STM 아카이브를 유발 — 대시보드가 이를 "이벤트"로 잘못 해석 | L | L | 타임라인은 archive 파일의 `archived_at` 만 사용(주체 구분 불필요), 정상 동작으로 처리 |
