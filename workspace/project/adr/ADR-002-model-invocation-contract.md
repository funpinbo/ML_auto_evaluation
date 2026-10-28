---
doc: adr
id: ADR-002
title: 모델 호출 인터페이스 — predict(X) -> y 고정 계약
status: Accepted
date: 2026-10-26
layer: project
author: architecture-analyst
---
# ADR-002: 모델 호출 인터페이스 — `predict(X) -> y` 고정 계약

## Context
- 00-interpretation.md §3.1 #2 / §4: 모델 스크립트의 정확한 호출 인터페이스(함수 시그니처 등)가 미확정이며, 사용자가 명시적으로 10/20 단계 설계로 위임했다.
- 10-business-analysis.md §5 FR-002/FR-004, §7: 이 인터페이스 미확정이 FR-002/004 를 막는 1순위 리스크이며, "PyTorch/scikit-learn 두 프레임워크 분기 처리"가 필요할 것으로 예상해 FR-004 구현 노력을 "중간"으로 평가했다.
- user/03§1 원칙 1(단순함 우선, 과설계·조기 분산 금지)과 03§3(상태 관리: 서비스 로직은 stateless)이 최우선 제약이다.
- 01 FR-002: 지원 형식은 PyTorch 또는 scikit-learn 로 확정되어 있으나, 두 프레임워크는 모델 로딩 방식(state_dict vs pickle/joblib)과 아키텍처가 임의이므로 시스템이 범용적으로 추측해 로드할 수 없다.

## Decision
업로드되는 모델은 **단일 `.py` 스크립트**이며, 다음 고정 규약을 반드시 지켜야 한다.

1. 스크립트는 **모듈 전역(top-level) 함수 `predict(X) -> y`** 를 노출한다.
   - `X`: `pandas.DataFrame` (피처 컬럼만, 라벨 컬럼 제외).
   - `y`: 길이가 `len(X)` 와 같은 array-like (예측값 1개/행).
   - 모델 로딩(가중치 복원 등)은 스크립트가 **자기 책임으로 import 시점에 수행**한다(예: 자신의 파일 경로(`__file__`) 기준 상대 경로로 pickle/`state_dict` 를 불러오거나, 스크립트 안에서 즉석 학습).
2. **CSV 데이터셋 컨벤션**: 업로드된 CSV 의 **마지막 컬럼을 라벨(`y_true`)**, 나머지 컬럼을 피처(`X`)로 취급한다. 별도 컬럼 매핑 UI 는 두지 않는다.
3. 시스템(모델 로더/평가 실행기)은 `framework`(pytorch/sklearn) 값을 **메타데이터로만** 보관하며, 이를 근거로 분기 로직을 두지 않는다. 평가 실행기는 오직 `predict(X)->y` 계약만으로 두 프레임워크를 동일하게 호출한다.
4. **검증 시점 2단계**:
   - 업로드 시(FR-002): `importlib` 로 모듈을 로드하고 `hasattr(module, "predict")` 및 `callable(...)` 여부만 검사 — 실패 시 즉시 4xx(fail fast, QS-6).
   - Run 실행 시(FR-004): 실제 `predict(X)` 호출 결과의 길이/타입이 기대와 다르거나 예외가 발생하면 해당 (model, dataset, metric) Evaluation 을 `status='error'` 로 기록하고 ERROR 로그를 남긴다(Run 전체를 중단하지 않음).

## Alternatives
| 대안 | 설명 | 기각 이유 |
|------|------|-----------|
| (a) 범용 플러그인 시스템 | 사용자가 adapter 클래스를 구현하고 YAML/JSON manifest 로 진입점·여러 hook 메서드(preprocess/load/predict/postprocess 등)를 지정 | "하루" 범위에 과함, 원칙 1(단순함 우선, 과설계 금지) 정면 위반. manifest 파싱·다중 hook 오케스트레이션이 구현 범위를 FR-002/004 예상보다 키움 |
| (b) 프레임워크별 전용 로더 | 시스템이 PyTorch 는 `torch.load`(state_dict), scikit-learn 은 `joblib.load` 로 직접 모델을 복원 | PyTorch state_dict 복원에는 모델 클래스 정의가 추가로 필요해 시스템이 임의 아키텍처를 일반화해 로드할 수 없음(비현실적). 또한 평가 엔진에 프레임워크 분기 로직이 생겨 원칙 1 위반 |
| (c) 선택한 방안: `predict(X)->y` 고정 계약, 로딩은 사용자 스크립트 책임 | 본 ADR의 Decision | 채택 |

## Consequences
- **긍정**: 평가 실행기(Evaluation Engine)가 완전히 프레임워크-무관(framework-agnostic) 해져, 10-business-analysis §5 FR-004 가 예상한 "두 프레임워크 분기 처리" 구현 비용이 사라진다 — "하루" 일정 리스크(00§3.2 #9, Q9) 완화에 직접 기여.
- **긍정**: 모델 로더/평가 실행기 코드가 단순해져 유지보수성(03§2 2위) 충족.
- **부정/트레이드오프 — 사용자 부담**: 사용자가 반드시 이 계약(함수명·시그니처·자기 책임 로딩)을 지켜 스크립트를 작성해야 한다. 업로드 폼/문서에 예시 스크립트와 계약을 명시해야 하며(DoD), 계약 위반 시 즉시 명확한 에러 메시지가 필요하다.
- **보안 관련 예외 사유(명시)**: 업로드된 임의 Python 코드를 그대로 `import`(=실행)한다. 이는 일반적으로는 보안 위험이지만, 03§8("로컬 전용이 핵심 원칙, 그 외 인증/암호화 불필요") 과 01 NFR-003(로컬 PC 전용, 외부 노출 없음) 전제상 **본인이 작성/신뢰하는 스크립트만 업로드한다는 가정** 하에 허용되는 리스크로 명시적으로 수용한다(03§2 보안 7위, 거의 무관). 샌드박싱·코드 정적분석은 범위 밖(원칙 1 과설계 금지).
- CSV "마지막 컬럼=라벨" 컨벤션은 구현 단순화를 위한 고정 규칙이며, 사용자가 다른 형태의 CSV 를 올리면 혼란이 생길 수 있어 업로드 가이드 문서화가 필수다(20-architecture-analysis.md §9 R6).
