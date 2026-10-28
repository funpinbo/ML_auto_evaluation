---
doc: team-charter
layer: team
team: ops
group: platform
tier: core
status: draft
---
# Ops / SRE 팀 Charter

> 팀 Agent(`.claude/agents/team-ops.md`)가 작업 전 항상 읽는 문서입니다. `aidlc/teams/catalog.json` 기본값으로 생성되며,
> team-architect 가 프로젝트 분석서 근거로 구체화합니다 ("프로젝트 적용" 칸).
> 상위 문서와 충돌하면 user/02(개발 표준) > user/03(아키텍처 철학) > 이 문서 순으로 따릅니다.

## 1. 미션
서비스가 SLO 를 지키도록 관측성, 알림, 장애 대응, 용량 계획을 운영한다.

- 생성 근거: 항상 — 운영 환경의 관측성·SLO·장애 대응
- 프로젝트 적용: core. 20 §4 "관측성 (`app/logging_config.py`, `api/health.py`) → ops", 20 §6 관측성 규칙, QS-03·QS-11. 로컬 단일 사용자 도구라 SLO 는 NFR-001·002 측정값으로 대체. 40 §2 에서 infra(로컬 실행 환경 전제·런북) 책임을 인수 (40 §1)

## 2. 책임 범위
**소유 (Owns)**
- SLO/SLI 정의 (slo.md)
- 모니터링·대시보드·알림 규칙 (예: ops/monitoring)
- 런북 (runbooks/)
- 장애 대응 절차·포스트모템 템플릿
- (infra 인수) 로컬 실행 환경 전제(127.0.0.1 바인딩·포트 운영 확인, Windows bash 전제 R-09) 런북

**하지 않음 (Not owns)**
- 기능 개발
- 인프라 리소스 설계 (infra)

- 프로젝트 적용 (실제 디렉토리/컴포넌트):
  - `monitor/backend/app/logging_config.py` (`setup_logging()`, 포맷 `%(asctime)s %(levelname)s %(message)s`, uvicorn access log 끔)
  - `monitor/backend/app/api/health.py`, `monitor/backend/app/models/health.py` (`/api/v1/health`)
  - `monitor/backend/tests/ops/` (health·로깅 단위 테스트, user/02 §10 DoD)
  - `workspace/project/ops/` — `slo.md`(NFR-001·002 → SLI), `logging.md`(로그 문구 규칙), `runbooks/`(포트 사용 중, statusLine 미실행, 일시정지 해제 안 됨, 사용량 데우기 느림)
  - **경계:** `app/main.py` 의 health 라우터 등록·`setup_logging()` 호출은 backend 소유. health 가 쓰는 소스 상태·데우기 진행률은 backend 의 `services/` 읽기 함수를 호출만 한다

## 3. 산출물
- slo.md: NFR → SLI/SLO/에러 버짓
- 알림 규칙 + 대시보드 정의
- runbooks/<장애유형>.md
- 용량 계획

## 4. 입력 문서
- workspace/user/01-project-overview.md §6
- workspace/user/03-architecture-philosophy.md §7
- workspace/project/20-architecture-analysis.md

## 5. 담당 요구사항
| FR/NFR | 내용 | Phase |
|--------|------|-------|
| CON-05 | `/api/v1/health` = 생존 + 소스별 접근 가능 여부 + 데우기 진행률 + 앱 식별자 | P1 |
| 02 §7 | 로그 레벨 규칙(ERROR=패널 못 그림, WARN=파일 누락·형식 오류), 본문·경로·ID 금지 | P1 |
| NFR-002 | 깨진 입력에도 프로세스 생존, WARN 1줄(파일 종류·사유만) | P1 |
| FR-005 / QS-11 | heartbeat 만료(≤ 2분) "세션 없음" 표시 운영 확인, 2시간 상한 런북 | P1 |
| NFR-001 | 첫 화면·반영 지연 SLI 정의(측정은 qa) | P1 |

## 6. 협업 인터페이스
- infra: 리소스
- cicd: 배포·롤백
- 모든 개발 팀: 로그/메트릭 계측
- security: 보안 이벤트 알림

| 방향 | 상대 팀 | 계약 | 위치 |
|------|---------|------|------|
| 제공 | backend | `setup_logging()` + 로그 문구 규칙 | `monitor/backend/app/logging_config.py`, `workspace/project/ops/logging.md` |
| 사용 | backend | `source_status()`, `warmup.progress()` 읽기 함수 | `workspace/project/contracts/README.md` |
| 제공 | cicd | health 응답 `app` 식별자 | `workspace/project/contracts/openapi.json` |
| 협의 | security | 로그에 비밀값·본문이 없는지 | `workspace/project/security/security-checklist.md` |

## 7. 팀 Definition of Done
- [ ] user/02 §10 공통 DoD
- [ ] 모든 가용성/성능 NFR 에 SLI·알림 존재
- [ ] 알림마다 런북 링크
- [ ] 장애 시나리오 리허설 기록

## 8. 품질 지표
- SLO 달성률
- MTTD/MTTR
- 알림 노이즈(조치 불필요 알림 비율)

## 9. 리뷰 게이트 (다른 팀 Task 검증)
- 대상: 배포 방식·설정·로그/메트릭 계측·외부 의존성을 바꾸는 Task
- 확인 항목:
  - [ ] 관측 가능한가 (로그·메트릭·트레이스)
  - [ ] 롤백 가능한가
  - [ ] SLO 영향이 평가되었는가

## 10. 팀 표준 (user/02 구체화)
- 언어/프레임워크: Python 3.11+ `logging`(표준), FastAPI 라우터, Pydantic v2 응답 모델
- 디렉토리: 위 "프로젝트 적용" 목록
- 테스트 명령: `cd monitor/backend && python -m pytest tests/ops` (health·로깅 단위 테스트), 전체 `cd monitor/backend && python -m pytest`
- 규칙: 알림 대신 화면 경고 배너(FR-010)를 쓴다. 외부 모니터링 SaaS 금지(03 §4)
