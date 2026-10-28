"""QA 테스트 fixture — 회귀용 더미 모델 스크립트 (ADR-002 고정 계약 준수).

- 모듈 전역 함수 `predict(X) -> y` 를 노출한다 (ADR-002 Decision #1).
- 모델 로딩(=학습)은 스크립트 자기 책임으로 **import 시점에 즉석 학습**한다.
- `regression_data.csv` 와 동일한 분포(`random_state=42`, 동일 피처 수)로 합성 데이터를
  재생성해 학습하므로, 이 CSV 로 평가해도 임의 수준 이상의 성능이 나온다.
- `framework` 메타데이터(예: 테스트에서 "pytorch" 로 지정)는 사용자가 업로드 시 별도로
  지정하는 값이며(ADR-002 Decision #3), 이 스크립트의 실제 구현 라이브러리와 무관하다 —
  평가 엔진은 어떤 프레임워크 메타데이터가 붙어 있어도 `predict(X)->y` 계약만으로 동일하게
  호출한다. TC-002-02 처럼 framework=pytorch 로 업로드 테스트를 해도 이 스크립트를 그대로
  재사용할 수 있다(실제 torch 의존성 설치 불필요).
"""

from __future__ import annotations

import pandas as pd
from sklearn.datasets import make_regression
from sklearn.linear_model import LinearRegression

# regression_data.csv 생성 시 사용한 파라미터와 반드시 동일하게 유지한다.
_X_train, _y_train = make_regression(
    n_samples=60,
    n_features=3,
    n_informative=3,
    noise=0.1,
    random_state=42,
)

_model = LinearRegression()
_model.fit(_X_train, _y_train)


def predict(X: pd.DataFrame):
    """X: pandas.DataFrame(피처 컬럼만) -> y: len(X) 와 같은 길이의 array-like."""
    return _model.predict(X.to_numpy())
