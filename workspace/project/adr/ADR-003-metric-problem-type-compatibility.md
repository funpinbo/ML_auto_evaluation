---
doc: adr
id: ADR-003
title: 지표-문제유형 호환성 전략 및 KPI-02 산식 확정
status: Accepted
date: 2026-10-26
layer: project
author: architecture-analyst
---
# ADR-003: 지표-문제유형 호환성 전략 및 KPI-02 산식 확정

## Context
- 00-interpretation.md §3.2 #10: Accuracy/F1(분류)과 RMSE(회귀)의 문제유형-지표 불일치 처리 방식이 FR-003 수용 기준에 명시되지 않아 20 단계 설계 과제로 이관됨.
- 10-business-analysis.md §7: "지표와 모델의 문제 유형 불일치는 사용자가 알아서 피할 것"이라는 가정이 틀리면 "평가가 에러 없이 조용히 틀린 값을 낼 경우 KPI-02/결과 신뢰도 저하" 리스크가 있다고 명시.
- 30-data-analysis.md §5.2: data-analyst 가 `Model.problem_type`(사용자 직접 지정, `problem_type_source` 로 `user_declared`/`inferred` 구분) + `Evaluation.status`(`success`/`skipped_incompatible`) + `METRIC_COMPATIBILITY` 매핑(classification→{accuracy,f1}, regression→{rmse})을 제안하고, `eda/schema_validation.py` 합성 픽스처로 검증(`success_count:3`, `skipped_incompatible_count:2`, `schema_created:true`).
- 30-data-analysis.md §7: KPI-02 분자("완료 모델 수")에 `skipped_incompatible` 을 포함할지 여부를 10/20 단계에서 명시해야 한다고 권고.
- user/03§1 원칙 3("결과 비교 용이성 > 성능")과 §2(개발속도 1위·유지보수성 2위)가 채점 기준.

## Decision
1. **data-analyst 제안을 승인**한다: `Model.problem_type`(enum: classification/regression, 업로드 폼에서 사용자가 직접 지정, 기본값 없음·필수 입력), `Model.problem_type_source`(기본 `user_declared`, `inferred` 는 필드만 유지하고 이번 범위에서 구현하지 않음), `METRIC_COMPATIBILITY` 고정 매핑을 그대로 채택한다.
2. **`Evaluation.status` enum 을 `success | skipped_incompatible | error` 3종으로 확정**한다(data-analyst 제안의 2종에 `error` 를 추가 — ADR-002 의 모델 호출 실패 등 런타임 예외를 포괄하기 위함).
   - `skipped_incompatible`: Compatibility Filter 가 Run 실행 **전에** 선제 차단한 경우. `value=NULL`, WARN 로그(02§7).
   - `error`: Compatibility Filter 는 통과했으나 `predict()` 호출/지표 계산 중 예외가 발생한 경우. `value=NULL`, ERROR 로그(02§7).
3. **UI 동작**: FR-003 지표 선택 화면에서 선택된 Model(들)의 `problem_type` 기준 허용 지표(복수 모델 혼합 시 합집합)만 노출하고, Run 생성 시점에 (model, dataset, metric) 조합별로 재검사한다(data-analyst 제안 그대로).
4. **KPI-02 산식 확정**: 분모 = 해당 Run 에 연결된 모델 전체 수("입력 모델 수"). 분자 = 해당 Run 내에서 **`Evaluation.status='success'` 레코드를 하나 이상 가진 모델 수**("완료 모델 수"). `skipped_incompatible` 만 있거나 `error` 만 있는 모델은 **분자에서 제외**한다(레코드 자체는 삭제하지 않고 보존해 추적 가능하게 함).
5. **결과 화면(FR-005) 표시 요구**: "완료 N / 입력 M (호환성 스킵 K, 오류 J)" 형태로 세분 표시해, KPI-02 가 100% 미달인 이유를 사용자가 바로 알 수 있게 한다.
6. **단계 분리(P1/P2)**: Compatibility Filter 는 Evaluation Engine 과 분리된 모듈로 구현한다. "하루" 일정이 급박해질 경우(10§5 완화안), P1 에서는 이 필터를 비활성화(pass-through, 지표 1종 고정)해도 구조 변경 없이 P2 에서 다시 활성화할 수 있다.

## Alternatives
| 대안 | 설명 | 기각 이유 |
|------|------|-----------|
| (a) 모델 실행 후 출력 형태로 problem_type 추론 | 30§5.2 에서 이미 검토·보류 | PyTorch/scikit-learn 출력 shape/dtype 만으로 분류/회귀 구분이 일반적으로 성립하지 않음. 또한 "평가 실행 전" UI 필터링이 불가능해 FR-003 "지표 선택 시점" 요구와 불일치 |
| (b) 호환성 검사 없이 전부 허용, 계산 시 예외처리만 | 30§5.2 에서 이미 검토·보류 | 사용자가 실패를 매번 겪은 뒤에야 알게 됨 — 원칙 3("결과 비교 용이성 > 성능") 위반 우려 |
| (c) `skipped_incompatible` 을 KPI-02 분자(완료)에 포함 | 시스템이 에러 없이 처리했으니 "완료"로 간주 | 지표를 잘못 선택해도 100%로 보여 10-business §7 이 지적한 "조용히 틀린 결과로 신뢰도 저하" 리스크를 그대로 남김 — 원칙 3 위반. **기각** |
| (d) 선택한 방안: 승인 + `error` 상태 추가 + skipped/error 를 KPI-02 분자에서 제외 | 본 ADR의 Decision | 채택 |

## Consequences
- **긍정**: data-analyst 가 합성 데이터로 이미 검증한 로직(`schema_validation.py`)을 재사용해 설계·구현 비용이 추가로 들지 않음(개발속도 1위 충족).
- **긍정**: KPI-02 가 "나쁜 지표 선택"을 숨기지 않아 원칙 3("결과 비교 용이성")에 부합. 사용자가 결과를 신뢰할 수 있음.
- **부정/트레이드오프**: KPI-02 가 100% 미달로 나올 수 있음(사용자가 지표를 잘못 고른 경우) — 이는 의도된 설계이며, FR-005 결과 화면에 세분 표시(위 5번)를 반드시 구현해야 혼란을 막을 수 있다(요구사항으로 반영됨).
- `problem_type_source='inferred'` 는 필드만 유지하고 구현하지 않으므로, 향후 자동 추론 기능을 추가해도 스키마 변경이 필요 없다(유지보수성 2위 충족, 과설계 회피).
