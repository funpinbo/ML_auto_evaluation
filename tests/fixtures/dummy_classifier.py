"""QA 테스트 fixture — 분류용 더미 모델 스크립트 (ADR-002 고정 계약 준수).

- 모듈 전역 함수 `predict(X) -> y` 를 노출한다 (ADR-002 Decision #1).
- 모델 로딩(=학습)은 스크립트 자기 책임으로 **import 시점에 즉석 학습**한다
  (ADR-002 Decision #1 "스크립트 안에서 즉석 학습" 허용 패턴).
- `classification_data.csv` 와 동일한 분포(`random_state=42`, 동일 피처/클래스 수)로
  합성 데이터를 재생성해 학습하므로, 이 CSV 로 평가해도 임의 수준 이상의 성능이 나온다.
- `framework` 메타데이터는 업로드 시 사용자가 별도로 지정하는 값이며(ADR-002 Decision #3),
  이 스크립트의 실제 구현 라이브러리와 무관하다 — 평가 엔진은 `predict(X)->y` 계약만 본다.

사용 예 (테스트 코드):
    import importlib.util
    spec = importlib.util.spec_from_file_location("dummy_classifier", "tests/fixtures/dummy_classifier.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert callable(module.predict)
    y = module.predict(X)  # X: pandas.DataFrame, 피처 컬럼만 (라벨 제외)
"""

from __future__ import annotations

import pandas as pd
from sklearn.datasets import make_classification
from sklearn.linear_model import LogisticRegression

# classification_data.csv 생성 시 사용한 파라미터와 반드시 동일하게 유지한다
# (tests/fixtures/classification_data.csv 생성 스크립트 참고).
_X_train, _y_train = make_classification(
    n_samples=60,
    n_features=4,
    n_informative=3,
    n_redundant=0,
    n_classes=3,
    n_clusters_per_class=1,
    random_state=42,
)

_model = LogisticRegression(max_iter=1000)
_model.fit(_X_train, _y_train)


def predict(X: pd.DataFrame):
    """X: pandas.DataFrame(피처 컬럼만) -> y: len(X) 와 같은 길이의 array-like."""
    return _model.predict(X.to_numpy())
