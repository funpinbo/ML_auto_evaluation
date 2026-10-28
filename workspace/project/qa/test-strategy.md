---
doc: test-strategy
layer: project
team: qa
status: draft
source: workspace/teams/qa/charter.md §5·§9·§10, user/02-development-standards.md §5·§10, workspace/project/stories/FR-001~005.md
---
# QA 테스트 전략 (ML_miniops)

> qa charter(§5·§9·§10)를 프로젝트 FR-001~005 에 구체적으로 적용한 문서. "하루" 1인 프로젝트 전제(user/02)로
> 커버리지 기준은 없으며, 핵심 평가 로직 + MVP 필수 시나리오만 자동화 대상으로 삼는다.

## 1. 목적과 범위

- 목적: FR-001~005 의 수용 기준(stories/FR-xxx.md)과 10§6 MVP 성공 판단 기준이 실제로 동작함을, 더미 fixture 로
  독립적으로 검증한다.
- 범위 안: FR-001(N:M 연결) ~ FR-005(결과 시각화) 핵심 파이프라인, FR-003 호환성 필터(P1 pass-through / P2 필터),
  QS-2(재시작 복구, 수동), QS-6(fail fast), QS-7(Run 전체 완료 보장).
- 범위 밖(qa 미소유): NFR-003(네트워크 바인딩, security 소유 T-019), 로깅 레벨 전수 검증(ops 소유 T-007),
  부하/동시성 테스트(NFR-004 동시 사용자 1명 전제로 과설계 금지, LTM §2).
- 실행하지 않은 검증은 "통과"로 기재하지 않는다(02§5, qa charter §10). 본 문서 작성 시점(T-004)에는 기능 코드가
  아직 구현되지 않았으므로, 아래 추적표의 모든 테스트 케이스 상태는 `planned` 이다. 실제 실행/결과는 해당 구현
  Task(T-009~T-024)의 qa 리뷰 시점에 STM §7 에 PASS/FAIL 로 기록한다.

## 2. 테스트 피라미드

| 레벨 | 비율(가이드) | 대상 | 도구 | 소유 |
|------|------|------|------|------|
| 단위(Unit) | 多 | 지표 계산 함수(accuracy/f1/rmse), 호환성 필터(METRIC_COMPATIBILITY), N:M 연결 쿼리 | pytest | 구현 팀(backend/dba), qa 는 리뷰만 |
| 통합(Integration) | 中 | FastAPI 엔드포인트 단위(`POST /models`, `/datasets`, `/links`, `/runs`) — TestClient + 임시 SQLite 파일 | pytest + `fastapi.testclient.TestClient` | 구현 팀(backend), qa 는 리뷰·추가 케이스 식별 |
| E2E | 少(필수 시나리오만) | 업로드→연결→지표선택→Run→결과조회 전체 흐름(charter §9 ①), 비호환 회귀(②③), 재시작 복구(④, 수동) | pytest(API 레벨 E2E) + 수동(④) | qa |

- 02§5 "커버리지 기준 없음"을 따른다 — 피라미드 비율은 가이드일 뿐 강제 수치가 아니다.
- 단위 테스트 작성 "책임"은 개발 팀에 있다(qa charter §2 "하지 않음"). qa 는 E2E/회귀 스위트와 fixture, 그리고
  수용 기준 ↔ 테스트 케이스 추적표를 소유한다.

## 3. 테스트 환경

- 실행 명령: `pytest`(루트 또는 `tests/`), 02§10 공통 DoD "핵심 평가 로직 단위 테스트가 있다면 통과"에 연동.
- DB: 테스트마다 격리된 임시 SQLite 파일(예: `tmp_path / "test.db"`)을 사용하고 `init_schema(conn)`(app/eval/repository.py,
  LTM D-09)으로 스키마를 초기화한다. `:memory:`는 FastAPI 요청마다 새 커넥션을 열 경우 데이터가 보이지 않을 수 있어
  기본값으로 쓰지 않는다(구현 팀이 커넥션 전략을 바꾸면 이 문서를 갱신).
- 데이터: **항상 더미 fixture**(02§5) — `tests/fixtures/` 의 합성 분류/회귀 CSV + 더미 `predict(X)->y` 모델 스크립트
  (T-005 산출물). 실제 사용자 업로드 데이터는 테스트에 쓰지 않는다.
- 디렉토리(qa charter §10, 02§3):
  ```
  tests/
    fixtures/        # T-005: classification_data.csv, regression_data.csv, dummy_classifier.py, dummy_regressor.py (+predict 미노출 스크립트 1개 — QS-6 네거티브 케이스용)
    unit/             # 지표 계산/호환성 필터 등 — 개발 팀 작성
    integration/      # 엔드포인트별 — 개발 팀 작성
    e2e/              # qa 소유 — 필수 시나리오 5종
  ```

## 4. 필수 시나리오 (qa charter §9, 10§6, 20§1 QS 표) → 테스트 케이스 매핑

| # | 시나리오 | QS/KPI | 매핑 테스트 케이스 | 자동화 |
|---|----------|--------|---------------------|--------|
| ① | 모델 2개 + 데이터셋 1개 업로드 → N:M 연결 + 지표 선택 + Run → Run 1건 + Evaluation N건 저장 | KPI-02 | TC-E2E-01 (FR-001 AC-2/3, FR-002 AC-1/2/3, FR-003 AC-1/2, FR-004 AC-1/2/5) | 자동 |
| ② | `predict` 미노출 스크립트 업로드 시 4xx 즉시 반환 | QS-6 fail fast | TC-002-04 | 자동 |
| ③ | problem_type/metric 비호환 조합은 `status=skipped_incompatible`(P2) 또는 P1 pass-through `status=error`, Run 전체는 에러 없이 완료 | QS-7 | TC-003-04(P1), TC-003-05(P2), TC-004-04 | 자동 |
| ④ | 프로세스 재시작 후 기존 데이터 조회 가능 | QS-2 | TC-004-06 | **수동** — `python run.py` 재시작이 필요해 pytest 자동화 대상 아님. T-019/T-020 전후 수동 체크리스트로 수행 |
| ⑤ | CSV 열 수 <2 등 형식 오류 시 4xx | 20§9 R6 | TC-002-05 | 자동 |

## 5. FR 별 Test Case 추적표 (수용 기준 → 테스트 케이스)

> 상세 Given/When/Then 과 구현 파일 대상은 `workspace/project/qa/test-cases/FR-xxx.md` 참고.
> 상태(status): `planned`(아직 미실행) / `pass` / `fail` — qa 리뷰 시 STM §7 근거와 함께 갱신.

| FR | AC | TC ID | 레벨 | Phase | 구현 연동 Task | 상태 |
|----|----|-------|------|-------|----------------|------|
| FR-001 | AC-1 | TC-001-01 | integration | P1 | T-013 | planned |
| FR-001 | AC-2 | TC-001-02 | integration | P1 | T-013 | planned |
| FR-001 | AC-3 | TC-001-03 | integration | P1 | T-013 | planned |
| FR-001 | AC-4 | TC-001-04 | integration | P1 | T-013 | planned |
| FR-001 | AC-5 | TC-001-05 | integration | P1 | T-013 | planned |
| FR-002 | AC-1 | TC-002-01 | integration | P1 | T-010 | planned |
| FR-002 | AC-2 | TC-002-02 | integration | P1 | T-010 | planned |
| FR-002 | AC-3 | TC-002-03 | integration | P1 | T-011 | planned |
| FR-002 | AC-4 | TC-002-04 | integration | P1 | T-010 | planned |
| FR-002 | AC-5 | TC-002-05 | integration | P1 | T-011 | planned |
| FR-002 | AC-6 | TC-002-06 | integration | P1 | T-010 | planned |
| FR-003 | AC-1 | TC-003-01 | integration | P1 | T-015 | planned |
| FR-003 | AC-2 | TC-003-02 | integration | P1 | T-015 | planned |
| FR-003 | AC-3 | TC-003-03 | integration | P1 | T-016 | planned |
| FR-003 | AC-4 | TC-003-04 | integration | P1 | T-015 | planned |
| FR-003 | AC-5 | TC-003-05 | integration | P2 | T-021 | planned |
| FR-003 | AC-6 | TC-003-06 | integration | P1 | T-015/T-016 | planned |
| FR-004 | AC-1 | TC-004-01 | e2e | P1 | T-015 | planned |
| FR-004 | AC-2 | TC-004-02 | e2e | P1 | T-015 | planned |
| FR-004 | AC-3 | TC-004-03 | integration | P1 | T-015 | planned |
| FR-004 | AC-4 | TC-004-04 | integration | P1 | T-015 | planned |
| FR-004 | AC-5 | TC-004-05 | integration | P1 | T-015 | planned |
| FR-004 | AC-6 | TC-004-06 | 수동 | P1 | T-019/T-020 | planned |
| FR-005 | AC-1 | TC-005-01 | integration | P1 | T-017/T-018 | planned |
| FR-005 | AC-2 | TC-005-02 | integration | P1 | T-017/T-018 | planned |
| FR-005 | AC-3 | TC-005-03 | integration | P1 | T-017/T-018 | planned |
| FR-005 | AC-4 | TC-005-04 | integration | P1 | T-017 | planned |
| FR-005 | AC-5 | TC-005-05 | integration | P2 | T-023/T-024 | planned |
| TC-E2E-01 | (①종합) | TC-E2E-01 | e2e | P1 | T-009~T-018 | planned |

- FR-001~005 각각 최소 1개 이상의 테스트 케이스가 매핑됨(T-004 DoD 충족).
- FR-003 AC-5(P2 호환성 필터 활성화)는 T-021 완료 전까지 `skip`(pytest `xfail`/`skip` 로 표시, 코드 완성 전 임시 상태이며
  "테스트를 삭제해 통과시키는 것"과는 다름 — 왜 skip 인지 사유를 명시)로 두고, T-025(P2 회귀)에서 활성화한다.

## 6. 회귀 전략

- P1 구현 완료마다(T-009~T-020) 해당 FR 의 integration/e2e 케이스를 qa 리뷰 모드에서 실제 실행하고 STM §7 에 결과를 남긴다.
- P2(T-021~T-024) 완료 후 T-025 에서 P1 전체 + P2 신규 케이스를 함께 재실행해 "P1 기능 회귀 없음"을 확인한다(T-025 DoD).
- 결함 발견 시 qa 는 직접 코드를 고치지 않고, STM §5 에 담당 팀(`[backend]`/`[frontend]`/`[dba]`) Task 후보로
  재현 절차(fixture, 요청/응답, 기대값 vs 실제값)와 함께 남긴다.

## 7. 알려진 제약 / 열린 사항

- T-005(테스트 픽스처)가 아직 수행되지 않아, 본 문서의 TC 들은 아직 실제 pytest 코드로 존재하지 않는다(설계 단계,
  구현은 각 Task 담당 팀 + qa 리뷰에서 진행).
- LTM I-03(FK PRAGMA 미설정)은 T-029 로 추적 중 — 해결되면 FR-001 AC-5(존재하지 않는 model_id/dataset_id 연결 시
  4xx)의 통합 테스트 범위에 FK 위반 케이스를 추가로 고려한다(현재는 애플리케이션 레벨 검증만 가정).
- QS-2(재시작 복구, TC-004-06)는 pytest 단일 프로세스 안에서 재현하기 어려워 수동 테스트로 분류함 — 자동화가
  필요해지면(예: subprocess 로 `python run.py` 기동/종료) cicd 팀과 협의한다.
