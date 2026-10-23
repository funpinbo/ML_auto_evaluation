---
status: active
task: T-007
team: cicd
outcome: none
opened_at: 2026-10-23T18:23:57+00:00
---
# Short-term Memory

> **계층 4 (작업 단위).** Task 1개를 수행하는 동안의 작업 메모리. 한 번에 하나만 열린다.
> 수명: `status: active` 로 열고 → 작업 → `outcome` 기록 → `status: closed` 로 닫는다.
> 닫히는 순간 Hook 이 이 파일을 `archive/STM-xxxx_<task>.md` 로 옮기고 Long-term memory 갱신(cascade 1/3)을 요구한다.
> frontmatter 값: status(idle|active|closed) / outcome(done|partial|blocked)

## 1. 목표
- Task: T-007 [cicd] run.py / run.sh / run.bat 원클릭 런처(Python 탐지, venv, 해시 마커 재설치 생략, 포트 선택, 헬스 대기, 브라우저 열기) + requirements 고정 + .gitignore + 로컬 게이트·dist 신선도 검사 — SCOPE-01, KPI-02 | deps: T-006
- 완료 조건(DoD): 깨끗한 상태에서 `bash run.sh --no-browser` 로 서버 기동·health 200 확인, 런처가 실제 선택한 포트를 서버 `settings.port` 로 전달·포트 0 금지(D-19), dist 가 무시되지 않음 확인(I-03), `monitor/backend/requirements.txt`(T-005 가 임시 작성, cicd 소유로 인수) 검토, TestClient httpx vs httpx2 결정(I-22), 런처 중복 실행 판정은 HTTP 200 + `data.app == "aidlc-monitor"`(400 BAD_HOST = 포트 불일치, D-34), `monitor/backend/requirements-dev.txt` 에 mypy(I-29)와 pytest==9.1.1, jsonschema==4.26.0(+referencing, jsonschema-specifications, rpds-py, attrs), ruff==0.17.2, pytest-cov, httpx 를 `pip freeze` 로 `==` 고정 (출처: STM-0004 §5) + user/02 §10 공통 DoD

## 2. 로드한 컨텍스트
- 관련: SCOPE-01(stories/SCOPE-01.md AC-1~16), KPI-02, user/02 §3·§4·§9·§10, 03 원칙 1·§6, ADR-001(런처), ADR-005(dist 커밋·신선도), ADR-006(의존성)
- LTM: D-19·D-32(포트: 기본 8765, AIDLC_MONITOR_PORT / `python -m app --port N`, 0·선행 0 금지, 127.0.0.1 고정), D-34(health `data.app` 판정), I-03(dist 무시 금지), I-12·I-22(의존성 최신 확인, httpx/httpx2), I-29(mypy), CLAUDE.md 실행 환경(Windows python/py, aidlc/hooks/run.sh 탐지 방식)
- 기존: monitor/backend/requirements.txt(T-005 임시 작성 → cicd 인수), monitor/.venv 는 개발용(.gitignore)

## 3. 작업 로그
<!-- 시간순으로 짧게. 무엇을 했고 무엇을 봤는지 -->

## 4. 발견 사항 (LTM 후보)
- 결정:
- 패턴:
- 이슈/리스크:
- 교훈:

## 5. 새로 발견된 Task (Task 후보)
- 

## 6. 결과 & 인수인계
- 산출물(파일/PR):
- 검증 결과:
- 남은 일:

## 7. 리뷰 기록 (리뷰 게이트)
<!-- /aidlc-run 이 리뷰 게이트 대상 팀을 리뷰 모드로 호출하면 각 팀이 한 줄씩 추가 -->
| 팀 | 결과 | 근거 | 필요한 조치 |
|----|------|------|-------------|
