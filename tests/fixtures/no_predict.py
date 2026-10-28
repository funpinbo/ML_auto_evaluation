"""QA 테스트 fixture — predict 미노출 네거티브 케이스 (QS-6 fail fast, TC-002-04).

ADR-002 Decision #1 이 요구하는 모듈 전역 `predict` 함수를 **의도적으로 노출하지 않는다**.
`POST /models` 업로드 시 `importlib` 로드 후 `hasattr(module, "predict")` 검사에서
실패해 즉시 4xx 를 반환해야 한다(Run 시점이 아니라 업로드 시점에서 걸려야 fail fast).
"""

from __future__ import annotations


def infer(X):
    """이름이 `predict` 가 아니므로 ADR-002 계약을 충족하지 못한다."""
    return [0 for _ in range(len(X))]
