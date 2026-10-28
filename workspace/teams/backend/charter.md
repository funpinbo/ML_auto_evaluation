---
doc: team-charter
layer: team
team: backend
group: engineering
tier: conditional
status: draft
---
# Backend 팀 Charter

> 팀 Agent(`.claude/agents/team-backend.md`)가 작업 전 항상 읽는 문서입니다. `aidlc/teams/catalog.json` 기본값으로 생성되며,
> team-architect 가 프로젝트 분석서 근거로 구체화합니다 ("프로젝트 적용" 칸).
> 상위 문서와 충돌하면 user/02(개발 표준) > user/03(아키텍처 철학) > 이 문서 순으로 따릅니다.

## 1. 미션
도메인 로직과 API 를 개발 표준과 계약에 맞게 구현하고 테스트한다.

- 생성 근거: 서버 측 API 또는 도메인 로직 컴포넌트가 있을 때 (대부분의 프로젝트)
- 프로젝트 적용: 20§4 컴포넌트 표에서 API 라우터, 모델 로더/어댑터, 호환성 필터, 평가 실행기, 지표 계산기, 데이터 접근 계층(쿼리 구현부), 로컬 파일 저장소, 실행 런처 9개 중 6개를 backend 가 소유(40§1). data/analytics/integration/ml 전담 팀이 없으므로(40§2) 업로드 수집·정제·저장과 모델 호출·호환성 검사도 backend 가 흡수한다.

## 2. 책임 범위
**소유 (Owns)**
- 서버 애플리케이션 코드 (예: src/api, src/domain)
- API 구현 및 단위·통합 테스트
- DB 접근 계층 코드

**하지 않음 (Not owns)**
- DB 스키마 운영 변경 실행 (dba)
- 인프라 리소스 (infra)
- 계약 정의 자체 (architecture)

- 프로젝트 적용 (실제 디렉토리/컴포넌트): `app/api/`(FastAPI 라우터), `app/eval/model_loader.py`(ADR-002 `predict` 계약 검증), `app/eval/compatibility.py`(ADR-003 `METRIC_COMPATIBILITY`), `app/eval/engine.py`(평가 실행기), `app/eval/metrics.py`(accuracy/f1/rmse), `app/eval/repository.py`(쿼리 구현부 — DDL/스키마 설계는 dba 소유), `run.py`(uvicorn 런처), `workspace/data/`(업로드 원본). `app/eval/visualize.py` 와 `app/web/` 은 frontend 소유(겹치지 않음).

## 3. 산출물
- API 구현 + OpenAPI 동기화
- 단위/통합 테스트
- 마이그레이션 스크립트 (실행은 승인 후)

## 4. 입력 문서
- workspace/project/contracts/
- workspace/project/stories/
- workspace/user/02-development-standards.md

## 5. 담당 요구사항
| FR/NFR | 내용 | Phase |
|--------|------|-------|
| FR-001 | N:M 연결 API (`POST/GET /links`) | P1 |
| FR-002 | 업로드 API + 모델 로더(`predict` 존재 검증, fail fast QS-6) | P1 |
| FR-003 | 호환성 필터 구현(`compatibility.py`) | P1(필터 로직) — UI 비활성화는 frontend P2 |
| FR-004 | Run 실행기(`POST /runs`, 조합 순회·호환성검사·지표계산·저장) | P1 |
| NFR-001/002/003/004 | 성능 목표 없음 / SQLite 영속화로 재시작 복구 / `127.0.0.1` 바인딩 / 동시성 제어 생략 | P1 |

## 6. 협업 인터페이스
- frontend: REST API 계약(20§5), 응답 포맷(FastAPI `HTTPException`, 02§6)
- dba: 스키마(DDL)·쿼리·인덱스 검토
- qa: 더미 fixture 데이터로 테스트
- architecture: ADR-002/003 계약 구현 확인, 신규 계약 필요 시 Task 후보

| 방향 | 상대 팀 | 계약 | 위치 |
|------|---------|------|------|
| backend → frontend | `POST /models`, `POST /datasets`, `POST /links`, `GET /links`, `POST /runs`, `GET /runs/{run_id}/results` | REST, JSON/multipart | `workspace/project/20-architecture-analysis.md` §5, 런타임 `/docs` |
| dba → backend | SQLite DDL/스키마 | `CREATE TABLE` 문 | `workspace/teams/dba/charter.md` §3 |
| backend → qa | 업로드/실행 에러 로그, 더미 fixture 호출 결과 | `tests/fixtures/` 참조 | `workspace/memory/short-term.md` |

## 7. 팀 Definition of Done
- [ ] user/02 §10 공통 DoD
- [ ] 계약(OpenAPI)과 구현 일치
- [ ] user/02 커버리지 기준 충족
- [ ] 에러 응답 포맷 준수
- [ ] 로그에 개인정보 없음

## 8. 품질 지표
- API p95 지연
- 테스트 커버리지
- 5xx 비율

## 9. 리뷰 게이트 (다른 팀 Task 검증)
- 없음 (리뷰 게이트를 운영하지 않는 팀)

## 10. 팀 표준 (user/02 구체화)
- 언어/프레임워크: Python 3.12 + FastAPI + Uvicorn (02§1, 20§7). 외부 프레임워크 분기 로직 없음 — `predict(X)->y` 계약 하나로 PyTorch/scikit-learn 을 동일하게 호출(ADR-002, 20§0#1)
- 디렉토리: `app/api/`, `app/eval/`(model_loader.py, compatibility.py, engine.py, metrics.py, repository.py), `run.py` (02§3)
- 테스트 명령: `pytest`(선택, 02§5) — 핵심 평가 로직(연결/지표 계산/호환성 필터)만 더미 데이터로 최소 단위 테스트. lint: `ruff format`, `ruff check`
- 로깅: 표준 `logging`, 콘솔만. ERROR=평가 실패(`status=error`), WARN=`status=skipped_incompatible`, INFO=Run 시작/완료 (02§7, 20§6)
- CSV 컨벤션: 마지막 컬럼 = 라벨(ADR-002 §3, R6) — 업로드 시 열 수 ≥2 검증
