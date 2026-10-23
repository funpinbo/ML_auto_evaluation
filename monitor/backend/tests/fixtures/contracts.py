"""계약 스키마 로더 (workspace/project/contracts/*.schema.json).

스키마의 `format`(date-time)은 비강제이므로 `pattern` 으로만 검증한다 (LTM 패턴).
음성 케이스도 이 검증기로 실제 실행해서 스키마가 잡는지 확인한다.
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path

from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[4]
CONTRACTS_DIR = REPO_ROOT / "workspace" / "project" / "contracts"

SCHEMA_NAMES = ("control", "loop-status", "claude-status")


@cache
def _validator(name: str) -> Draft202012Validator:
    schema = json.loads((CONTRACTS_DIR / f"{name}.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def schema_errors(instance: object, name: str) -> list[str]:
    """위반 목록(경로: 메시지). 비어 있으면 통과. 메시지에 입력 값이 섞일 수 있으므로 로그에 쓰지 않는다."""
    return [f"{'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message}" for e in _validator(name).iter_errors(instance)]


def is_valid(instance: object, name: str) -> bool:
    return not schema_errors(instance, name)
