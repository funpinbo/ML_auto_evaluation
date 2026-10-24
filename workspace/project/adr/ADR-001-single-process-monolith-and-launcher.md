---
adr: 001
title: 단일 FastAPI 프로세스 모놀리스 + 원클릭 런처(run.py)
status: proposed
date: 2026-10-23
author: architecture-analyst
related: [SCOPE-01, KPI-02, NFR-001, NFR-003, CON-02, 원칙 1, 원칙 3, 03 §3, 03 §6]
---
# ADR-001. 단일 FastAPI 프로세스 모놀리스 + 원클릭 런처

## Context
- 03 §1 원칙 1: "내려받고 실행 파일 하나로 웹까지 뜬다". 03 §3: FastAPI 가 API 와 빌드된 Vue 정적 파일을 함께 서빙하는 단일 프로세스 모놀리스. 03 §6: `run.bat`/`run.sh` 실행, 최초 실행 시 venv·패키지 설치 자동.
- 02 §3: 루트에 `run.py`(설치 + 서버 + 브라우저), `run.bat`/`run.sh` 는 래퍼.
- KPI-02: 다운로드 후 첫 화면 5분 이내, 실행 동작 1회. 사용자는 Python 3.11+ 만 있다고 가정(01 §7).
- Windows 에는 `python3` 이 없거나 Microsoft Store 안내용 가짜 실행 파일일 수 있다(`aidlc/hooks/run.sh` 가 이미 실제 실행으로 탐지).
- 20 §2 채점: 후보 A(단일 프로세스) 125점, B 83점, C 84점.

## Decision
1. **프로세스 1개**: uvicorn 이 `monitor.backend.app.main:app` 을 worker 1개로 실행. 호스트는 코드에 `127.0.0.1` 로 고정(옵션 없음). 포트 기본 8765, `--port`/`AIDLC_MONITOR_PORT` 로만 변경.
2. **`run.py`(표준 라이브러리만)** 순서:
   1. `sys.version_info >= (3, 11)` 확인, 아니면 안내 후 exit 1.
   2. `monitor/.venv` 없으면 `venv.create(with_pip=True)`.
   3. `monitor/backend/requirements.txt` 의 sha256 을 `monitor/.venv/.requirements.sha256` 과 비교, 다르면 `<venv python> -m pip install --no-cache-dir -r ...`(사용자 전역 pip 캐시에 쓰지 않음, 02 §11) 후 마커 갱신. 설치 실패 시 마커를 쓰지 않는다.
   4. 포트 확인: 시작 포트(기본 8765, `--port` > `AIDLC_MONITOR_PORT`, 1~65535·0 금지 D-19/D-32)부터 최대 10개. 사용 중인 포트는 `GET http://127.0.0.1:<port>/api/v1/health` 가 HTTP 200 이고 봉투의 `data.app == "aidlc-monitor"`(값 고정 Literal, D-34) 이면 이미 실행 중 → 새 서버 없이 브라우저만 열고 종료. 그 밖(연결 실패, 200 아님 — 예: 400 `BAD_HOST` = Host 포트 불일치(가드 포트와 실제 포트가 다른 서버), JSON 아님, `data.app` 불일치)은 "다른 프로그램" 으로 보고 다음 포트. 프록시는 우회한다(`ProxyHandler({})`).
   5. `<venv python> -m app --port N` 을 `cwd=monitor/backend` 자식 프로세스로 실행. **호스트 인자는 넘기지 않는다** — 바인딩 주소는 `app/config.py` 의 `127.0.0.1` 상수(03 §8, 옵션 없음). 자식 환경에서 `AIDLC_MONITOR_PORT` 를 제거해 런처가 실제 선택한 `--port` 가 `settings.port` 의 단일 출처가 되게 한다(D-19). uvicorn 직접 호출·access log 설정은 `app/__main__.py`(backend/ops) 몫.
   6. 헬스 200 까지 최대 20 s 대기 → `webbrowser.open("http://127.0.0.1:N/")` (`--no-browser` 로 생략 가능).
   7. Ctrl+C → 자식 종료. 종료 코드 전달.
3. **`run.sh`**: `aidlc/hooks/run.sh` 와 같은 방식으로 `python3 → python → py` 를 실제 실행해 3.11+ 인지 확인 후 `exec "$py" run.py "$@"`.
   **`run.bat`**: `py -3 -c "import sys; sys.exit(sys.version_info < (3, 11))"` → 성공 시 `py -3 run.py %*`, 아니면 `python` 으로 같은 검사, 둘 다 실패면 설치 안내 + `pause`(더블클릭 시 창이 바로 닫히지 않게).
4. venv 경로 차이(Windows `Scripts\python.exe`, 그 밖 `bin/python`)는 `run.py` 가 처리.
5. 소유: cicd(런처·의존성 고정), ops(헬스·로그).

## Alternatives
- **B. 표준 라이브러리 서버 + 바닐라 JS (의존성 0)**: 원칙 3 에는 가장 맞지만 02 §1 지정 스택(FastAPI·Vue·ECharts)과 충돌(규칙 우선순위 02 > 03), 개발 속도·유지보수성 열세(20 §2, 83점).
- **C. 수집 데몬 + SQLite 캐시 + API (2 프로세스)**: 콜드 스타트는 없지만 03 §5 "자체 데이터 저장 안 함" 위반, 프로세스 관리 추가(84점).
- **PyInstaller 등 단일 실행 파일 배포**: 원칙 1 에 더 가깝지만 OS 별 빌드 파이프라인이 필요하고 01 §3 에서 원격 배포·CI/CD 범위 밖. 기각.
- **uv/pipx 로 설치**: 빠르지만 사용자 PC 에 추가 도구 설치 필요(02 §11 전역 설치 금지). 기각.
- **루트 `.venv`**: 루트를 어지럽히고 다른 Python 도구와 충돌 가능. `monitor/.venv` 선택.

## Consequences
- (+) 실행 동작 1회, Node·DB·Docker 불필요. 재실행은 설치를 건너뛰어 수 초.
- (+) 중복 실행 시 새 서버를 띄우지 않고 기존 화면을 연다.
- (−) 최초 실행에는 PyPI 접속이 필요(유일한 외부 네트워크 사용, NFR-005 예외로 명시). 오프라인 PC 는 미지원.
- (−) 프로세스 재시작 시 사용량 캐시 재구축(ADR-002 데우기로 완화).
- `.gitignore` 에 `monitor/.venv/` 추가(cicd).
- 검증: KPI-02 리허설(Windows 1회 + macOS/Linux 1회), 런처 단위 테스트(해시 마커·포트 선택 로직은 함수로 분리해 pytest).

## 변경 이력
- 2026-10-23 T-007 architecture 리뷰 조치: Decision 2.3·2.4·2.5 를 구현과 일치시킴 — 자식 명령 `<venv python> -m app --port N`(호스트 인자 없음, 127.0.0.1 은 `app/config.py` 상수), 자식 env 에서 `AIDLC_MONITOR_PORT` 제거(D-19), 포트 최대 10개, 마커 `monitor/.venv/.requirements.sha256`, `pip install --no-cache-dir`, 중복 실행 판정 = health 200 + `data.app`(D-34). 구조 결정 변경 없음(문구 정정).
- 2026-10-24 T-009 (I-27, 문구만): Decision 2.4 중복 실행 판정을 구현(`run.py` `probe_health`/`is_our_server`)과 health 계약(D-34)에 맞춰 상세화 — HTTP 200 + 봉투 `data.app == "aidlc-monitor"` 만 "실행 중", 400 `BAD_HOST`·비 JSON·불일치는 다음 포트, 프록시 우회. 근거: 원칙 1(실행 동작 1회 — 중복 실행 시 기존 화면), ADR-011 §4(Host 가 포트까지 검사하므로 다른 포트 서버는 400). 구조 결정 변경 없음.
