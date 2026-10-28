"""app/eval/model_loader.py — 모델 로더/어댑터 (FR-002/FR-004, ADR-002, backend 소유).

업로드된 `.py` 스크립트를 `importlib` 로 동적 import 하고, 모듈 전역 함수 `predict` 의
존재/호출 가능 여부만 검증한다(ADR-002 Decision #1/#4 "검증 시점 2단계" 중 **1단계**,
업로드 시점, FR-002, QS-6 fail fast).

- `X`(피처), `y`(예측값) 의 실제 타입/길이 검증과 `predict(X)` 실제 호출은 **Run 실행
  시점**(FR-004)의 몫이며 이 모듈 범위 밖이다(별도 Task, T-015).
- `framework`(pytorch/sklearn) 값은 메타데이터로만 쓰이며, 이 모듈은 프레임워크별
  분기 로직을 두지 않는다(ADR-002 Decision #3) — 두 경우 모두 동일하게 `hasattr`/
  `callable` 검사만 수행한다.
- FastAPI 등 웹 프레임워크에 의존하지 않는다(팀 특화 지침 "도메인 로직은 프레임워크에
  의존하지 않게 분리"). 호출자(`app/api/models.py`)가 `ModelContractError` 를
  `HTTPException`(4xx)으로 변환하고 ERROR 로그를 남긴다.
"""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

PREDICT_CONTRACT_HINT = "predict(X) -> y"


class ModelContractError(Exception):
    """업로드된 모델 스크립트가 `predict(X) -> y` 계약(ADR-002)을 만족하지 못할 때 발생한다.

    모듈을 아예 import 할 수 없는 경우(문법 오류, import 시점 예외 등)도 계약을
    검증할 방법이 없으므로 이 예외로 통일해서 올린다 — 호출자가 어떤 경우든 동일하게
    4xx + ERROR 로그로 처리할 수 있게 한다(QS-6 fail fast).
    """


def validate_predict_contract(script_path: str | Path) -> None:
    """`script_path` 의 `.py` 모듈을 로드해 전역 `predict` 함수가 존재하고 호출 가능한지
    검사한다.

    성공하면 아무 것도 반환하지 않는다(부수효과 없음). 실패하면 `ModelContractError` 를
    올리며, 메시지에 `predict(X) -> y` 계약을 명시한다(FR-002 AC-4 "오류 메시지에 계약
    명시").
    """
    path = Path(script_path)
    # 동일 프로세스 안에서 여러 모델을 반복 업로드/검증할 수 있으므로, sys.modules 캐시
    # 충돌을 피하기 위해 매번 고유한 모듈 이름을 사용한다.
    module_name = f"uploaded_model_{uuid.uuid4().hex}"

    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ModelContractError(
            f"모델 스크립트를 로드할 수 없습니다 ({path}). "
            f"모듈 전역 함수 {PREDICT_CONTRACT_HINT} 를 노출해야 합니다(ADR-002)."
        )

    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        # 사용자 스크립트가 올릴 수 있는 모든 예외를 동일하게 "계약 위반"으로 취급한다
        # (의도적으로 광범위하게 catch).
        raise ModelContractError(
            f"모델 스크립트 로드 중 오류가 발생했습니다: {exc}. "
            f"모듈 전역 함수 {PREDICT_CONTRACT_HINT} 를 노출해야 합니다(ADR-002)."
        ) from exc

    predict_fn = getattr(module, "predict", None)
    if predict_fn is None or not callable(predict_fn):
        raise ModelContractError(
            f"모델 스크립트가 모듈 전역 함수 {PREDICT_CONTRACT_HINT} 를 노출하지 않습니다"
            " (ADR-002)."
        )
