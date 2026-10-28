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
- 프로젝트 적용: 02§4 "main 에 직접 커밋(trunk-based, PR 없음)", 03§6 "배포 전략 불필요(로컬 실행)" — 원격 CI/CD(.github/workflows/, 컨테이너 이미지)는 범위 밖이다. cicd 는 02§10 공통 DoD(lint·문서·단위테스트)를 집행하는 **로컬 게이트**로 축소 운영한다.

## 2. 책임 범위
**소유 (Owns)**
- CI 워크플로 (예: .github/workflows/)
- 빌드·패키징·컨테이너 이미지 정의
- 릴리스·버전 정책, 변경 로그
- 품질 게이트 (lint, type, test, coverage, 보안 스캔)

**하지 않음 (Not owns)**
- 운영 인프라 리소스 (infra)
- 운영 배포 실행 승인 (사람)

- 프로젝트 적용 (실제 디렉토리/컴포넌트): `.github/workflows/` 와 Dockerfile 은 만들지 않는다(원격 CI/CD 범위 밖). `requirements.txt`(의존성 고정), DoD 체크리스트(본 charter §7)가 실질적 "게이트" 산출물이다.

## 3. 산출물
- 로컬 게이트 체크리스트(본 charter §7, T-006 로 확정): `ruff format --check app tests`, `ruff check app tests`, `pytest tests` 수동 실행 절차 — 경로를 `app tests` 로 명시(저장소 루트에 무관한 별도 프로젝트 `monitor/`, `aidlc/` 가 공존하므로 `.` 로 실행하면 안 됨, T-006 실측)
- requirements.txt (의존성 버전 고정, 02§9 "특별한 승인 절차 없음"; ruff 포함 — T-006)
- release.md: 버전 규칙(해당 없음 — 단일 버전, 02§6) 대신 변경 로그만 자유 형식 커밋 메시지로 추적(02§4)

## 4. 입력 문서
- workspace/user/02-development-standards.md §4,§5,§10
- workspace/user/03-architecture-philosophy.md §6

## 5. 담당 요구사항
| FR/NFR | 내용 | Phase |
|--------|------|-------|
| (02§10 DoD 전체) | 모든 FR 변경에 공통으로 적용되는 lint/문서/단위테스트 게이트 | 전체 Phase |

## 6. 협업 인터페이스
- qa: pytest 실행을 게이트 체크리스트에 포함
- security: 의존성 취약점 점검(선택, 02§8) 필요 시 협의
- 모든 개발 팀: `ruff format`/`ruff check` 명령 공유 (infra 팀 부재 — 배포 대상 환경 해당 없음, 40§2)

| 방향 | 상대 팀 | 계약 | 위치 |
|------|---------|------|------|
| cicd → 모든 개발 팀 | 로컬 게이트 명령(ruff, pytest) | 체크리스트 | 본 charter §7, `workspace/user/02-development-standards.md` §10 |

## 7. 팀 Definition of Done — 로컬 게이트 체크리스트 (T-006)
> 원격 CI 없음(02§4 PR 없음, 03§6 배포 전략 불필요) — 아래를 Task 완료 전에 **사람이 저장소 루트에서 수동 실행**한다.
> venv 미존재 시: `python -m venv .venv` → (Windows) `set PYTHONUTF8=1 && .venv\Scripts\python.exe -m pip install -r requirements.txt`(requirements.txt 헤더 주석 참고).

- [ ] `<venv>/python -m ruff format --check app tests` — 포맷 위반 0건 (02§10 "lint(ruff) 통과")
- [ ] `<venv>/python -m ruff check app tests` — 린트 위반 0건
- [ ] `<venv>/python -m pytest tests` — 전부 PASS (있는 테스트에 한함; 아직 `test_*.py` 가 없으면 "no tests ran" 도 통과로 간주, 02§5 "선택")
- [ ] 관련 문서 갱신 확인 (02§10)
- [ ] 기능 수동 확인(브라우저/API 호출) 완료 (02§10, 각 구현 Task 담당 팀 책임)

**경로를 반드시 `app tests` 로 명시한다** — 저장소에 ML_miniops 와 무관한 별도 프로젝트(`monitor/`, `aidlc/`)가 공존해서,
경로 없이 `.`(저장소 루트)로 실행하면 ruff 가 그 프로젝트 파일까지 검사해 무관한 포맷/린트 위반을 보고하고,
`pytest`(경로 없음)는 `monitor/backend/tests`까지 수집하다 미설치 의존성(fastapi/pydantic/jsonschema 등)으로
22건 수집 오류가 발생해 전부 실패한다(2026-10-27 T-006 실측 재현, 격리 venv).

**T-006 실행 결과(2026-10-27, 격리 `.venv`, 이 Task 종료 시 삭제)**:
- `ruff check app tests` → 0 위반 (All checks passed)
- `ruff format --check app tests` → `app/eval/repository.py` 1개 파일만 미포맷(빈 줄 1곳) — **cicd 소유 파일 아님**(dba/backend 소유, LTM D-09) → Task 후보로 남김(본 STM §5)
- `pytest tests` → 0 items collected("no tests ran") — T-005 는 fixture 스크립트만 두고 `test_*.py` 는 아직 없음(T-009+ 이후 추가 예정), 실패 아님

## 8. 품질 지표
- DORA: 배포 빈도, 변경 리드타임, 변경 실패율, 복구 시간
- CI 소요 시간

## 9. 리뷰 게이트 (다른 팀 Task 검증)
- 대상: `requirements.txt`·`.gitignore`를 바꾸거나 코드 변경이 있는 모든 Task (02§10 공통 DoD 집행)
- 확인 항목:
  - [ ] `ruff format --check app tests` 포맷 위반 0건
  - [ ] `ruff check app tests` 린트 위반 0건
  - [ ] `pytest tests` 전부 PASS (해당 테스트가 있는 경우)
  - [ ] `requirements.txt` 변경 시 깨끗한 venv 재설치로 재현되는가 (pip freeze 로 전이 의존성까지 `==` 고정 유지)

## 10. 팀 표준 (user/02 구체화)
- 언어/프레임워크: 해당 없음(파이프라인 코드 없음) — pip+venv(02§1)로 로컬 의존성만 관리
- 디렉토리: 리포 루트(`requirements.txt`), `.gitignore`
- 테스트 명령(T-006 로 확정, §7 체크리스트 참조): `ruff format --check app tests && ruff check app tests`, `pytest tests`(있으면). 경로를 `app tests` 로 **반드시** 명시한다(저장소 루트 `.` 로 실행하면 무관한 별도 프로젝트 `monitor/`, `aidlc/` 까지 검사/수집되어 깨짐 — §7 실측). 원격 트리거 없음 — Task 완료 전 수동 실행
- Git 전략: main 직접 커밋(trunk-based, PR 없음, 02§4), 커밋 메시지 자유 형식
