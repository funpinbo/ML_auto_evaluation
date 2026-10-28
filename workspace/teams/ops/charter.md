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
- 프로젝트 적용: 03§7 "관측성: 콘솔 로그만, 메트릭/트레이스/알림 불필요" — 정식 SLO/SLI 목표는 없다(NFR-001 성능 목표 없음). ops 의 실질 책임은 QS-2(가용성: 프로세스 비정상 종료 후 `python run.py` 재시작 시 SQLite 데이터 보존 확인)와 02§7 로그 레벨 규칙 준수 검증이다. infra 팀이 없으므로(40§2) 로컬 실행 환경 전제(포트, 바인딩)도 흡수한다.

## 2. 책임 범위
**소유 (Owns)**
- SLO/SLI 정의 (slo.md)
- 모니터링·대시보드·알림 규칙 (예: ops/monitoring)
- 런북 (runbooks/)
- 장애 대응 절차·포스트모템 템플릿

**하지 않음 (Not owns)**
- 기능 개발
- 인프라 리소스 설계 (infra)

- 프로젝트 적용 (실제 디렉토리/컴포넌트): `workspace/project/ops/runbooks.md`(재시작 복구, 포트 충돌 대응). SLO 수치·알림 규칙은 작성하지 않는다(03§7 "알림 불필요") — 대신 QS-2 수동 확인 절차를 런북으로 남긴다.

## 3. 산출물
- runbooks.md: 프로세스 비정상 종료 후 재시작 복구 확인 절차(QS-2), 포트 사용 중 대응
- 로그 레벨 검증 체크리스트: ERROR=평가 실패, WARN=선택적 지표 누락(`skipped_incompatible`), INFO=평가 시작/완료(02§7) 구현 여부 확인
- slo.md/알림 규칙/대시보드/용량 계획: 작성하지 않음 — 03§7 전제와 불일치하므로 "N/A(목표 없음)"로 명시

## 4. 입력 문서
- workspace/user/01-project-overview.md §6
- workspace/user/03-architecture-philosophy.md §7
- workspace/project/20-architecture-analysis.md

## 5. 담당 요구사항
| FR/NFR | 내용 | Phase |
|--------|------|-------|
| NFR-002 | 가용성(재시작 시 데이터 보존, QS-2) | P1 |
| (02§7) | 로그 레벨 규칙(ERROR/WARN/INFO) 구현 검증 | P1 |

## 6. 협업 인터페이스
- backend: 로그 구현 검토, 재시작 복구 리허설 (infra 팀 부재 — 리소스 협의 해당 없음)
- security: NFR-003 바인딩 주소와 겹치는 리스크 공유

| 방향 | 상대 팀 | 계약 | 위치 |
|------|---------|------|------|
| ops → backend | 로그 레벨 규칙(ERROR/WARN/INFO) 리뷰 피드백 | 리뷰 코멘트(STM §7) | `workspace/memory/short-term.md` |

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
- 언어/프레임워크: 표준 `logging` 모듈, 콘솔 출력만(02§7, 03§7)
- 디렉토리: `workspace/project/ops/runbooks.md`
- 테스트 명령: 수동 — `python run.py` 로 띄운 뒤 프로세스를 강제 종료하고 재시작, 기존 Model/Dataset/Run/Evaluation 이 `GET` 조회로 그대로 나오는지 확인(QS-2)
