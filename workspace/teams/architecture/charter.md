---
doc: team-charter
layer: team
team: architecture
group: product
tier: core
status: draft
---
# Architecture 팀 Charter

> 팀 Agent(`.claude/agents/team-architecture.md`)가 작업 전 항상 읽는 문서입니다. `aidlc/teams/catalog.json` 기본값으로 생성되며,
> team-architect 가 프로젝트 분석서 근거로 구체화합니다 ("프로젝트 적용" 칸).
> 상위 문서와 충돌하면 user/02(개발 표준) > user/03(아키텍처 철학) > 이 문서 순으로 따릅니다.

## 1. 미션
아키텍처 철학에 맞게 기술 결정을 내리고 기록하며, 팀 간 인터페이스 계약과 구조적 일관성을 지킨다.

- 생성 근거: 항상 — ADR 과 팀 간 계약의 단일 책임자가 필요하다
- 프로젝트 적용: 선택 아키텍처는 단일 프로세스 모놀리스(20§3, 가중합계 115점). ADR-001(스타일)·ADR-002(`predict(X)->y` 계약)·ADR-003(지표-문제유형 호환성 + KPI-02 산식)이 이미 Accepted 상태(20§8)이며, 신규 설계 쟁점이 생기면 이 문서 기준에 추가한다.

## 2. 책임 범위
**소유 (Owns)**
- workspace/project/20-architecture-analysis.md 유지보수
- workspace/project/adr/
- workspace/project/contracts/ (API·이벤트 스키마 계약)

**하지 않음 (Not owns)**
- 개별 기능 구현
- 운영 배포

- 프로젝트 적용 (실제 디렉토리/컴포넌트): `workspace/project/adr/ADR-001-single-process-monolith.md`, `ADR-002-model-invocation-contract.md`, `ADR-003-metric-problem-type-compatibility.md`. `workspace/project/contracts/` 는 생성하지 않는다 — 02§6 "OpenAPI 는 FastAPI 자동생성 문서 사용"이므로 계약 원천은 `20-architecture-analysis.md` §5 데이터 흐름 표와 런타임 `/docs` 다.

## 3. 산출물
- ADR-xxx.md (Context/Decision/Alternatives/Consequences)
- contracts/<interface>.yaml|json (OpenAPI 3.x/AsyncAPI/JSON Schema — docs/api 레퍼런스의 원천)
- 기술 부채 목록

## 4. 입력 문서
- workspace/user/03-architecture-philosophy.md
- workspace/user/02-development-standards.md
- workspace/project/20-architecture-analysis.md

## 5. 담당 요구사항
| FR/NFR | 내용 | Phase |
|--------|------|-------|
| FR-002 | 모델 호출 인터페이스 설계 (`predict(X)->y`, ADR-002) | P1 (완료) |
| FR-003 | 지표-문제유형 호환성 전략 설계 (`METRIC_COMPATIBILITY`, ADR-003) | P1 (완료) |
| NFR-002/003/004 | 가용성(SQLite 영속화)·보안(127.0.0.1 바인딩)·확장성(동시성 미제어) 결정 근거 | P1 (완료, 20§1 QS-2/3/4) |

## 6. 협업 인터페이스
- backend: ADR-002/003 계약 구현 확인, 신규 계약 필요 시 ADR 선행
- dba: 30§5 ERD/스키마 제안 승인(problem_type, Evaluation.status 필드)
- security: R2(임의 코드 실행) 위협 모델 공유 (infra 팀 부재 — 해당 없음)

| 방향 | 상대 팀 | 계약 | 위치 |
|------|---------|------|------|
| architecture → backend | `predict(X)->y` 계약 | ADR-002 | `workspace/project/adr/ADR-002-model-invocation-contract.md` |
| architecture → backend | `METRIC_COMPATIBILITY` + `Evaluation.status` + KPI-02 산식 | ADR-003 | `workspace/project/adr/ADR-003-metric-problem-type-compatibility.md` |
| architecture → dba | ERD 승인(Model.problem_type/problem_type_source, Evaluation.status) | 20§4 컴포넌트 표, 30§5.1 | `workspace/project/20-architecture-analysis.md` §4 |
| architecture → security | R2(임의 Python 코드 실행) 리스크 근거 | 20§9 리스크 표 | `workspace/project/20-architecture-analysis.md` §9 |

## 7. 팀 Definition of Done
- [ ] user/02 §10 공통 DoD
- [ ] user/03 §9 ADR 필수 대상에 ADR 존재
- [ ] 계약 변경은 하위 호환성 판단 포함
- [ ] 원칙 위반 시 예외 사유 ADR 명시

## 8. 품질 지표
- ADR 누락 결정 수 0
- 계약 위반 빌드 실패 수

## 9. 리뷰 게이트 (다른 팀 Task 검증)
- 대상: 새 컴포넌트·외부 의존성·데이터 모델·팀 간 계약을 바꾸는 Task
- 확인 항목:
  - [ ] ADR 이 있는가
  - [ ] user/03 원칙과 금지 기술을 지켰는가
  - [ ] 계약 하위 호환성이 지켜졌는가

## 10. 팀 표준 (user/02 구체화)
- 언어/프레임워크: 결정은 user/03 품질속성 가중치(개발속도7>유지보수성6>가용성5>확장성4>성능3>운영비용2>보안1, 20§2)로 채점해 ADR 에 기록
- 디렉토리: `workspace/project/adr/`, `workspace/project/20-architecture-analysis.md`
- 테스트 명령: 해당 없음(설계 문서). 신규 ADR 작성 시 20§2 후보 비교표 형식(최소 2개 후보, 가중합계)을 따른다.
