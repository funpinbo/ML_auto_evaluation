---
doc: team-charter
layer: team
team: dba
group: engineering
tier: conditional
status: draft
---
# Database (DBA) 팀 Charter

> 팀 Agent(`.claude/agents/team-dba.md`)가 작업 전 항상 읽는 문서입니다. `aidlc/teams/catalog.json` 기본값으로 생성되며,
> team-architect 가 프로젝트 분석서 근거로 구체화합니다 ("프로젝트 적용" 칸).
> 상위 문서와 충돌하면 user/02(개발 표준) > user/03(아키텍처 철학) > 이 문서 순으로 따릅니다.

## 1. 미션
DB 스키마, 마이그레이션, 인덱스, 백업·복구를 안전하게 관리한다.

- 생성 근거: 운영 DB 가 있고 스키마 마이그레이션·성능 관리가 필요할 때
- 프로젝트 적용: 20§4 컴포넌트 표가 "데이터 접근 계층(Repository)/SQLite 스키마 관리"를 dba 소유로 명시(40§1). 30§5.1 ERD(Model/Dataset/MODEL_DATASET_LINK/Run/Evaluation, `Model.problem_type`·`Evaluation.status` 신규 필드 포함)를 그대로 DDL 로 확정하는 책임을 진다. 쿼리 구현(Python `sqlite3` 호출부)은 backend 소유이며, dba 는 스키마·인덱스·마이그레이션만 관장한다(04/30 "고정 데이터셋 없음"으로 data 팀은 불필요, 40§2).

## 2. 책임 범위
**소유 (Owns)**
- 스키마 정의·마이그레이션 검토
- 인덱스·쿼리 성능 기준
- 백업/복구 절차서

**하지 않음 (Not owns)**
- 애플리케이션 쿼리 구현 (backend)
- 운영 DB 변경 실행 (사람 승인)

- 프로젝트 적용 (실제 디렉토리/컴포넌트): `app/eval/repository.py` 상단 `CREATE TABLE` DDL 블록(스키마 정의 소유, 쿼리 함수 본문은 backend 소유), `workspace/teams/dba/charter.md` §3 에 schema.md 를 인라인으로 유지(1일 프로젝트라 별도 디렉토리 생성하지 않음).

## 3. 산출물
- schema.md (ERD + 컬럼 사전) — 30§5.1 ERD 기준: MODEL(id, name, path, framework, problem_type, problem_type_source), DATASET(id, name, path), MODEL_DATASET_LINK(model_id FK, dataset_id FK), RUN(id, created_at), EVALUATION(id, run_id FK, model_id FK, dataset_id FK, metric, value, status)
- 마이그레이션 검토 기록 (락·다운타임·롤백) — 1인 로컬 SQLite 라 락/다운타임 리스크는 사실상 없음(R4, 20§9); 그래도 각 변경에 ALTER/재생성 스크립트와 되돌리기 방법을 남긴다
- backup-restore.md — SQLite 파일 복사가 전부(03§6 단일 환경, 별도 백업 자동화 불필요)

## 4. 입력 문서
- workspace/project/30-data-analysis.md §5
- workspace/project/20-architecture-analysis.md

## 5. 담당 요구사항
| FR/NFR | 내용 | Phase |
|--------|------|-------|
| FR-001 | MODEL_DATASET_LINK 테이블(PK/FK) | P1 |
| FR-002 | MODEL/DATASET 테이블 + `problem_type`/`problem_type_source` 필드(30§5.2) | P1 |
| FR-003 | EVALUATION.metric enum(accuracy/f1/rmse) | P1 |
| FR-004 | RUN/EVALUATION 테이블 + `EVALUATION.status` enum(success/skipped_incompatible/error, ADR-003) | P1 |
| KPI-02 | Run─Evaluation 관계로 완료/입력 모델 수 집계 가능하도록 인덱스 설계 | P1 |

## 6. 협업 인터페이스
- backend: 쿼리·인덱스 검토 (ORM 없음, raw SQL — 02§1)
- architecture: ERD 변경 승인
- ops: SQLite 파일 백업/복구 안내 공유 (data 팀 부재 — 해당 없음)

| 방향 | 상대 팀 | 계약 | 위치 |
|------|---------|------|------|
| dba → backend | SQLite DDL/스키마, 인덱스 | `CREATE TABLE`/`CREATE INDEX` 문 | `app/eval/repository.py` 상단, 본 charter §3 |
| dba ↔ architecture | ERD 변경 제안·승인 | 30§5.1 ERD 갱신 | `workspace/project/30-data-analysis.md` §5 |

## 7. 팀 Definition of Done
- [ ] user/02 §10 공통 DoD
- [ ] 모든 마이그레이션에 롤백 스크립트
- [ ] 대용량 테이블 변경은 무중단 전략 명시

## 8. 품질 지표
- 슬로우 쿼리 수
- 백업 성공률
- 복구 리허설 RTO

## 9. 리뷰 게이트 (다른 팀 Task 검증)
- 대상: DB 스키마·마이그레이션·대량 쿼리를 바꾸는 Task
- 확인 항목:
  - [ ] 롤백 가능한가
  - [ ] 락/다운타임 위험이 평가되었는가
  - [ ] 인덱스가 적절한가

## 10. 팀 표준 (user/02 구체화)
- 언어/프레임워크: SQLite(표준 `sqlite3`, ORM 없음, 03§4 "선호"), DDL 은 Python 파일 상단에 문자열로 보관(별도 마이그레이션 프레임워크 불필요 — 1일 프로젝트)
- 디렉토리: `app/eval/repository.py`(DDL 블록만 dba 소유, 쿼리 함수 본문은 backend)
- 테스트 명령: `pytest`(선택) — 스키마 생성/제약조건 테스트는 `workspace/project/eda/schema_validation.py` 패턴을 참고해 fixture 로 검증
- 동시성: WAL 모드 등 락 최적화는 필요 시에만 고려(과설계 금지, R4 20§9 — NFR-004 동시 사용자 1명 전제라 매우 낮은 리스크)
