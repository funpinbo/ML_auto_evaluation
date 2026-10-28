---
doc: adr
id: ADR-005
title: ML_miniops 실행 엔트리포인트 경로를 `python -m app` 로 확정 (저장소 루트 `run.py` 경로 충돌 해소)
status: Accepted
date: 2026-10-27
layer: project
author: architecture
---
# ADR-005: ML_miniops 실행 엔트리포인트 경로를 `python -m app` 로 확정

## Context
- 저장소 루트의 `run.py`/`run.sh`/`run.bat` 는 **이미 구현·커밋된 AI-DLC Monitor**(이 저장소 자체를 운영하는 메타 도구, 포트 8765, `monitor/.venv` 사용, SCOPE-01/ADR-001-single-process-monolith-and-launcher — `workspace-exam/` 쪽 프레임워크 자체 ADR)의 고정 인프라다. 이 파일들을 ML_miniops 용으로 옮기거나 재사용하는 것은 범위 밖이다.
- 그런데 `20-architecture-analysis.md` §4(컴포넌트 표: "실행 런처 (`run.py`)")·§6("`python run.py` 실행 시 `uvicorn.run(app, host='127.0.0.1', port=8000)`")과 `40-team-composition.md` §1(backend 소유 디렉토리 목록에 `run.py` 포함)이 **ML_miniops 의 실행 런처도 같은 경로 `run.py`** 로 설계해, backend 가 설계 그대로 구현하면 기존 AI-DLC Monitor 런처 파일을 덮어쓰게 된다(LTM I-08, STM-0008/T-033 발견).
- 02§3 디렉토리 규칙은 이미 ML_miniops 전체 코드를 `app/`(api/, eval/, web/) 패키지 하나로 모으도록 지정했고, 같은 저장소 안의 AI-DLC Monitor 자신도 `monitor/backend/app` 패키지를 `python -m app --port N` 형태(`run.py` L308-310 `server_command`)로 구동하는 선례가 이미 있다.

## Decision
ML_miniops 의 실행 엔트리포인트를 저장소 루트 `run.py` 가 아니라 **`app/__main__.py`** 로 두고, `python -m app [--port N]` 명령으로 구동한다.
- `app/__main__.py` 는 `uvicorn.run(app, host="127.0.0.1", port=<기본 8000>)` 를 호출한다(호스트 상수 고정, NFR-003/QS-3 그대로 유지).
- 저장소 루트 `run.py`/`run.sh`/`run.bat` 는 건드리지 않는다(AI-DLC Monitor 전용으로 그대로 유지).
- `20-architecture-analysis.md` §4/§6 은 이 ADR 채택과 동시에 "실행 런처 (`run.py`)" → "실행 엔트리포인트 (`app/__main__.py`, `python -m app`)" 로 수정한다(같은 Task 에서 반영 완료).

## Alternatives
| 대안 | 설명 | 기각 이유 |
|------|------|-----------|
| B. 루트에 다른 이름의 신규 스크립트(예: `serve.py`, `app_run.py`) 추가 | `run.py` 와 경로만 다른 별도 루트 파일 신설 | 루트에 "실행 스크립트"가 2개(Monitor 의 `run.py` + ML_miniops 의 신규 파일) 공존해 사용자가 혼동하기 쉽고, 02§3 디렉토리 규칙("app/ 안에 모든 ML_miniops 코드")에서 벗어난 루트 파일이 하나 더 생겨 유지보수성이 `python -m app` 대비 낮음. 채점: 개발속도 7×4+유지보수성 6×3+가용성 5×4+확장성 4×3+성능 3×3+운영비용 2×4+보안 1×3 = 28+18+20+12+9+8+3 = **98점** |
| C. AI-DLC Monitor 쪽 `run.py` 를 다른 경로로 옮김 | Monitor 런처를 이동시켜 루트 `run.py` 를 ML_miniops 에 내어줌 | Monitor 는 이 저장소(AI-DLC 프레임워크) 자체의 고정 인프라이자 이미 커밋되어 운영 중인 별개 프로젝트(`workspace-exam/` ADR-001-single-process-monolith-and-launcher)로, ML_miniops 작업 범위 밖이다. 변경 시 프레임워크 자체의 문서(README, docs/aidlc/)·사용자 습관("저장소 클론 후 `python run.py`")까지 깨뜨려 "최소 변경" 원칙(원칙 1)에 정반대로 어긋남 — 비교 대상에서 제외(원칙 위반) |
| **A. `app/__main__.py` + `python -m app`(선택)** | 기존 `app/` 패키지 스캐폴드(02§3, STM-0002/D-08) 안에 엔트리포인트를 추가, 루트에 새 파일을 만들지 않음. 같은 저장소의 Monitor 자신도 이미 `python -m app --port N` 패턴을 쓰고 있어 선례와 합치 | 개발속도 7×5+유지보수성 6×5+가용성 5×4+확장성 4×3+성능 3×3+운영비용 2×4+보안 1×3 = 35+30+20+12+9+8+3 = **117점 — 최고점, 선택** |

## Consequences
- **긍정**: 루트 파일 충돌이 원천적으로 사라진다(두 프로젝트가 서로 다른 모듈 경로를 씀 — Monitor 는 `monitor/backend` 를 cwd 로 `-m app`, ML_miniops 는 저장소 루트를 cwd 로 `-m app`). 02§3 디렉토리 규칙과 완전히 일치해 ML_miniops 코드가 전부 `app/` 안에 응집된다. 과설계 없이(원칙 1) 기존 선례를 재사용한다.
- **부정/트레이드오프**: 사용자가 "그냥 `python run.py`" 라고 기대할 수 있는 관례(03§6 예시 문구)와는 다르다 — 문서(README/user-guide, 03§6 은 user 레이어라 수정하지 않음)에 `python -m app` 실행법을 명시해야 한다(backend/product Task 범위).
- **후속 조치 필요 (architecture 소유 범위 밖, Task 후보로 남김)**:
  - `[backend]` 런처 구현 시 `app/__main__.py` 생성(인자: `--port`, 기본 8000, 호스트 `127.0.0.1` 고정), `workspace/teams/backend/charter.md` §2/§10 의 `run.py` 표기를 `app/__main__.py` 로 갱신
  - `[ops]` `workspace/teams/ops/charter.md` §1/§10, `workspace/project/ops/runbooks.md` §2/§4.1/§5 의 `python run.py` 테스트 명령을 `python -m app` 으로 갱신, §4.1 주의 섹션 제거(해소됨으로 표시)
  - `[security]` T-034(또는 후속) NFR-003 실측 재검증 시 대상 파일을 `app/__main__.py` 로 확인(I-10)
  - `40-team-composition.md` §1 backend 소유 디렉토리 목록의 `run.py` → `app/__main__.py` 표기 정정 필요(해당 문서는 어떤 팀 charter 에도 "소유"로 명시돼 있지 않아 이 ADR 에서는 직접 수정하지 않고 Task 후보로만 남김)
