---
doc: story
id: SCOPE-01
title: 원클릭 실행 스크립트 (run.bat / run.sh → run.py)
priority: Must (FR 번호 없음, 00 A16·Q1)
phase: P1 (M1)
owner: product
status: draft
sources: [user/01 §2 KPI-02·§3 In scope·§5.1 흐름 1·§7, user/02 §3·§9·§10·§11, 00 §2 SCOPE-01·KPI-02·CON-04·CON-07, 10 §6 기준 2, 20 §4 원클릭 런처·§6 배포, ADR-001, ADR-005, LTM D-01·D-05·D-19·I-03]
---
# SCOPE-01 원클릭 실행

## 1. 사용자 스토리
AI-DLC 운영자(신규 도입자 포함)로서 저장소를 내려받은 뒤 실행 동작 한 번으로 대시보드를 보고 싶다, 설치 절차를 따로 익히지 않고 바로 쓰기 위해. (01 §3 In scope "원클릭 실행 스크립트", §5.1 흐름 1, KPI-02 를 스토리로 옮김 — FR 번호는 사용자가 정하지 않았으므로 SCOPE-01 유지)

- KPI: **KPI-02 다운로드 후 첫 화면 5분 이내, 실행 동작 1번** (`run.bat` 더블클릭 또는 `python run.py`/`run.sh`).
- 전제(01 §7): Python 3.11+ 가 이미 설치되어 있다. Node 는 필요 없다(dist 커밋, D-05).

## 2. 규칙 (20 §4 원클릭 런처)
1. Python 3.11+ 탐지 — `run.sh`: python3 / python / py 를 실제 실행해 버전 확인. `run.bat`: `py -3` → `python` 순서, Microsoft Store 별칭 배제.
2. `monitor/.venv` 가상환경 생성(없을 때만). 전역 설치 없음(02 §11).
3. `monitor/backend/requirements.txt` 설치. requirements 해시 마커가 같으면 설치 생략.
4. 포트 선택: 기본 8765. 사용 중이면 `/api/v1/health` 로 자기 서버인지 확인 → 자기 서버면 브라우저만 열고 종료, 아니면 다음 포트. 실제 선택 포트가 서버 `settings.port` 로 전달(D-19, 포트 0 금지).
5. uvicorn 을 `127.0.0.1` 에 기동 → `/api/v1/health` 200 대기(최대 20 s) → 기본 브라우저로 `http://127.0.0.1:<port>/` 열기.
6. 종료: 콘솔에서 Ctrl+C → 서버 정상 종료.

## 3. 수용 기준 (Given/When/Then)
- **AC-1 (Windows 첫 실행)** Given Python 3.11+ 만 설치된 깨끗한 Windows PC 에 저장소 zip 을 풀었을 때 When `run.bat` 을 더블클릭하면 Then 추가 입력 없이 가상환경 생성·패키지 설치·서버 기동 후 기본 브라우저에 대시보드 첫 화면이 열리고, 더블클릭부터 첫 화면까지 5분 이내다(UAT K2-W).
- **AC-2 (macOS/Linux 첫 실행)** Given 같은 조건의 macOS 또는 Linux 에서 When 저장소 루트에서 `./run.sh`(또는 `python3 run.py`) 를 한 번 실행하면 Then AC-1 과 같은 결과, 5분 이내(UAT K2-U).
- **AC-3 (실행 동작 1번)** Given AC-1·AC-2 일 때 Then 사용자가 하는 동작은 실행 1회뿐이다 — 프롬프트 응답, 별도 `pip install`, `npm`, 설정 파일 편집, 브라우저 주소 입력이 없다.
- **AC-4 (Node 불필요)** Given Node·npm 이 설치되지 않은 PC 일 때 Then AC-1·AC-2 가 통과한다(커밋된 `monitor/frontend/dist` 서빙). `git check-ignore --no-index monitor/frontend/dist/index.html` 이 exit 1(I-03).
- **AC-5 (재실행 설치 생략)** Given 한 번 실행한 PC 에서 서버를 끈 뒤 When 다시 실행하면 Then 패키지 설치를 건너뛰고(`설치 생략` 출력, pip 실행 없음) 첫 화면이 열린다. 네트워크가 끊겨 있어도 동작한다. 소요 시간은 UAT 에 기록만 한다(목표 수치 없음 — 01 에 기준 없음).
- **AC-6 (requirements 변경)** Given `requirements.txt` 내용이 바뀐 뒤 실행하면 Then 해시 불일치로 재설치 후 기동한다.
- **AC-7 (Python 없음/낮음)** Given Python 이 없거나 3.10 이하만 있을 때 Then 트레이스백 없이 "Python 3.11 이상이 필요합니다" 와 설치 안내 한 줄을 출력하고 0 이 아닌 코드로 끝난다. 가상환경·파일을 만들지 않는다.
- **AC-8 (설치 실패)** Given 첫 실행 중 네트워크가 없어 pip 설치가 실패할 때 Then 실패 원인 요약을 출력하고 0 이 아닌 코드로 끝나며, 해시 마커를 쓰지 않아 다음 실행에서 다시 설치를 시도한다.
- **AC-9 (포트 사용 중 — 자기 서버)** Given 이미 Monitor 가 8765 에서 실행 중일 때 When 다시 실행하면 Then 두 번째 서버를 띄우지 않고 브라우저만 기존 서버로 연다.
- **AC-10 (포트 사용 중 — 다른 프로그램)** Given 8765 를 다른 프로그램이 쓰고 있을 때 Then 다음 빈 포트로 기동하고 콘솔에 실제 URL 을 출력하며, 그 포트로 Host 가드가 동작한다(`127.0.0.1:<실제 포트>` 만 허용, D-18·D-19).
- **AC-11 (바인딩)** Given 실행 중일 때 Then 서버는 `127.0.0.1` 에만 바인딩되고 같은 네트워크의 다른 PC 에서 접속할 수 없다(NFR-003). 설정으로 `0.0.0.0` 으로 바꿀 수 없다.
- **AC-12 (헬스 대기 실패)** Given 서버가 20 s 안에 health 200 을 주지 않을 때 Then 브라우저를 열지 않고 "서버가 시작되지 않았습니다" + 원인(콘솔 로그) 출력 후 0 이 아닌 코드로 끝난다.
- **AC-13 (빈 workspace 에서도 첫 화면)** Given `workspace/` 가 비어 있거나 Claude Code 기록·스냅샷이 없을 때 Then 서버는 정상 기동하고 각 패널이 empty/안내 상태로 첫 화면이 열린다(FR-001~005 의 empty 상태).
- **AC-14 (전역 변경 없음)** Given 실행 전후일 때 Then `~/.claude/` 아래 파일, 사용자 전역 설정, 전역 Python 패키지가 바뀌지 않는다(02 §11). 쓰기는 `monitor/.venv`·해시 마커·런타임 로그 경로뿐이다.
- **AC-15 (무브라우저 옵션)** Given `run.sh --no-browser`(T-007 DoD) 일 때 Then 브라우저를 열지 않고 서버만 기동, health 200.
- **AC-16 (종료)** Given 실행 중 콘솔에서 Ctrl+C 를 누르면 Then 서버 프로세스가 종료되고 포트가 해제된다.

## 4. 예외·경계 흐름
| 상황 | AC |
|------|----|
| Python 없음 / 버전 낮음 / Store 별칭만 있음 | AC-7 |
| 첫 설치 중 네트워크 없음 | AC-8 |
| 포트 충돌(자기 서버 / 다른 프로그램) | AC-9 / AC-10 |
| 서버 기동 실패 | AC-12 |
| 빈 workspace·데이터 없음 | AC-13 |
| 경로에 공백·한글이 있는 폴더에 압축 해제 | AC-1·AC-2 와 같아야 한다 (UAT 에서 1회 확인 권장) |

## 5. 화면 상태
- 런처는 콘솔 출력만 가진다: 단계별 한 줄(`Python 확인`, `가상환경 준비`, `패키지 설치` 또는 `설치 생략`, `서버 시작 http://127.0.0.1:<port>/`, `브라우저 열기`). 실패 시 원인 한 줄 + 다음 행동 한 줄.
- 첫 화면에 FR-001·003·004 상단 행이 보이면 KPI-02 타이머를 멈춘다(UAT 정의).

## 6. 추적
| 항목 | 연결 |
|------|------|
| KPI | KPI-02 (AC-1~AC-3), 10 §6 기준 2 |
| 테스트 시나리오 | 자동 시나리오 없음(test-strategy §2 "수동" 층). AC-11 은 S-13 회귀와 관련, AC-13 은 S-02 와 같은 입력 |
| 자동 검증 | T-007 DoD: 깨끗한 상태에서 `bash run.sh --no-browser` → health 200 (cicd) |
| UAT | `uat/uat-checklist.md` §3 KPI-02 (K2-W, K2-U) |

## 7. 범위 밖
- Python 자동 설치, 설치 프로그램(.msi/.pkg)·실행 파일 묶음(PyInstaller 등).
- 원격 서버 배포·CI/CD 파이프라인·Docker 필수 구성(01 §3, 03 §4).
- OS 서비스/데몬 등록, 부팅 시 자동 시작.
- 자동 업데이트.
- statusLine 의 사용자 전역 설정 등록(프로젝트 `.claude/settings.json` 은 저장소에 커밋, Q4).
