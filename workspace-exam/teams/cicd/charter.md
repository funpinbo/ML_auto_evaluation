---
doc: team-charter
layer: team
team: cicd
group: platform
tier: core
status: draft
---
# CI/CD (Build & Release) 팀 Charter

> 팀 Agent(`.claude/agents/team-cicd.md`)가 작업 전 항상 읽는 문서입니다. `aidlc/teams/catalog.json` 기본값으로 생성되며,
> team-architect 가 프로젝트 분석서 근거로 구체화합니다 ("프로젝트 적용" 칸).
> 상위 문서와 충돌하면 user/02(개발 표준) > user/03(아키텍처 철학) > 이 문서 순으로 따릅니다.

## 1. 미션
모든 변경이 자동으로 빌드·검사·테스트되고, 승인된 절차로 안전하게 릴리스되게 한다.

- 생성 근거: 항상 — 자동 빌드·테스트·배포 파이프라인
- 프로젝트 적용: core. 20 §4 "원클릭 런처 → cicd", "의존성 고정 & 빌드 산출물 관리 → cicd", 20 §6 PR 전 로컬 점검. 원격 CI/CD 는 01 §3 Out of scope 이므로 CI 워크플로·컨테이너 대신 **로컬 게이트 스크립트**와 런처를 소유한다. 40 §2 에서 infra 의 설치 환경 책임 일부(venv·패키지 설치)를 인수 (40 §1)

## 2. 책임 범위
**소유 (Owns)**
- CI 워크플로 (예: .github/workflows/) — 이 프로젝트는 원격 CI 없음(01 §3), 로컬 게이트 `monitor/tools/check.py` 로 대체
- 빌드·패키징·컨테이너 이미지 정의
- 릴리스·버전 정책, 변경 로그
- 품질 게이트 (lint, type, test, coverage, 보안 스캔)
- (infra 인수) 사용자 PC 설치 절차: venv 생성, requirements 해시 마커, 포트 선택

**하지 않음 (Not owns)**
- 운영 인프라 리소스 (infra)
- 운영 배포 실행 승인 (사람)

- 프로젝트 적용 (실제 디렉토리/컴포넌트):
  - `run.py`, `run.bat`, `run.sh` (루트)
  - `monitor/backend/requirements.txt`, `requirements-dev.txt`, `monitor/backend/pyproject.toml`(ruff·pytest 설정)
  - `monitor/frontend/package.json`, `package-lock.json`
  - `monitor/tools/` — `check.py`(로컬 PR 게이트 일괄 실행), `check_dist_fresh.py`(소스 해시 ↔ `dist/.build-meta.json`)
  - `.gitignore` (Monitor 항목 추가만, 기존 프레임워크 줄 유지)
  - `workspace/project/release/` — `release.md`(버전 규칙, 롤백 = 커밋 되돌리기, pip-audit/npm audit 절차)
  - **하지 않음:** `.github/workflows/`, Dockerfile (01 §3, 03 §4)

## 3. 산출물
- CI 파이프라인 (PR 게이트)
- CD 파이프라인 (dev→staging 자동, prod 는 승인)
- release.md: 버전 규칙, 롤백 절차
- Dockerfile/빌드 스크립트

## 4. 입력 문서
- workspace/user/02-development-standards.md §4,§5,§10
- workspace/user/03-architecture-philosophy.md §6

## 5. 담당 요구사항
| FR/NFR | 내용 | Phase |
|--------|------|-------|
| SCOPE-01 | run.bat/run.sh → run.py: Python 3.11+ 탐지, `monitor/.venv`, 해시 같으면 설치 생략, 127.0.0.1 uvicorn, health 대기 후 브라우저(QS-10) | P1 |
| KPI-02 | 실행 동작 1회·첫 화면 ≤ 5분, 재실행 ≤ 10초 | P1 |
| 02 §4 / ADR-005 | dist 신선도 검사 | P1 |
| 02 §9 | requirements 전이 의존성까지 `==` 고정, lock 파일 | P1 |
| 02 §8 | 릴리스 전 pip-audit, npm audit 실행 | P1 말 / P2 말 |

## 6. 협업 인터페이스
- qa: 테스트 단계
- security: SAST/의존성/시크릿 스캔
- infra: 배포 대상 환경
- 모든 개발 팀: 빌드 명령

| 방향 | 상대 팀 | 계약 | 위치 |
|------|---------|------|------|
| 사용 | ops | `/api/v1/health` `app: "aidlc-monitor"` 식별자(중복 실행 판정) | `workspace/project/contracts/openapi.json` |
| 사용 | frontend | `npm run build` 산출물 + `dist/.build-meta.json` | `monitor/frontend/dist/` |
| 제공 | 모든 개발 팀 | 로컬 게이트 명령 | `monitor/tools/check.py` |
| 사용 | qa | 테스트 명령·커버리지 기준 | `workspace/project/qa/test-strategy.md` |
| 협의 | security | 의존성 취약점 점검 결과 | `workspace/project/release/release.md` |

## 7. 팀 Definition of Done
- [ ] user/02 §10 공통 DoD
- [ ] PR 마다 user/02 §10 게이트가 자동 실행
- [ ] 빌드 재현 가능 (lock 파일)
- [ ] 롤백 절차 문서화·검증

## 8. 품질 지표
- DORA: 배포 빈도, 변경 리드타임, 변경 실패율, 복구 시간
- CI 소요 시간

## 9. 리뷰 게이트 (다른 팀 Task 검증)
- 대상: 빌드 설정·의존성·CI 워크플로를 바꾸는 Task
- 확인 항목:
  - [ ] CI 가 통과하는가
  - [ ] 빌드 재현성이 유지되는가

## 10. 팀 표준 (user/02 구체화)
- 언어/프레임워크: Python 3.11+ 표준 라이브러리만(venv, subprocess, urllib, webbrowser, hashlib), bash(run.sh), cmd(run.bat)
- 디렉토리: 위 "프로젝트 적용" 목록
- 테스트 명령: `python monitor/tools/check.py` (ruff format --check, ruff check, `cd monitor/backend && python -m pytest --cov`, dist 신선도, `cd monitor/frontend && npm run lint && npx vue-tsc --noEmit && npm test`, OpenAPI export diff). 빌드 `cd monitor/frontend && npm ci && npm run build`
- 규칙: 런처는 호스트를 바꾸는 옵션을 두지 않는다(127.0.0.1 고정, QS-05). 패키지 전역 설치 금지(02 §11) — venv 안에만 설치
