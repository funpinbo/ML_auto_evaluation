"""JSONL 한 줄 → 허용 필드만 담은 `UsageRecord` (ADR-002 Decision 3, privacy.md §1·§2, security 리뷰 대상).

두 단계는 목적이 다르다.

1. **사전 필터(성능 목적, P-06·P-08)**: 원문 바이트에 `b'"usage":'` 가 없으면 `json.loads` 를 부르지 않고
   버린다. 30 EDA 실측 거짓 양성 11.7% — 사전 필터는 보안 경계가 아니다.
2. **허용 필드 복사(보안 경계, P-01·P-03)**: 파싱한 dict 에서 `timestamp`, `requestId`, `message.model`,
   `message.usage` 숫자 4종, `isSidechain` 만 고정 필드 dataclass 로 복사하고 원본 dict 는 함수가 끝나면서
   버린다. 그 밖의 키(`message.content` 등 본문)는 읽지 않는다.

`requestId` 는 원문을 보관하지 않고 BLAKE2b 16바이트 다이제스트로 바꾼다 — 중복 제거 키로만 쓰이므로 원문이
필요 없고, 메모리 집계 구조에 ID 원문이 남지 않는다(P-11).
`cwd` 는 디렉터리 해석 폴백(`extract_cwd`)에서만 읽는다(P-05).
로그·예외 메시지에는 줄 내용을 담지 않는다 — 이 모듈은 로그를 쓰지 않고 분류 결과만 돌려준다(T-08).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any

USAGE_NEEDLE = b'"usage":'
TOKEN_KEYS = (
    "input_tokens",
    "output_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
)
MAX_MODEL_LEN = 128
MAX_TOKEN_VALUE = 1 << 53
UNKNOWN_MODEL = "unknown"


class LineKind(str, Enum):
    """줄 분류. `ok` 만 집계된다. 나머지는 건수만 센다."""

    ok = "ok"
    no_usage = "no_usage"  # 사전 필터에서 버림 (json.loads 호출 없음)
    broken = "broken"  # JSON/UTF-8 아님
    usage_string_only = "usage_string_only"  # `"usage":` 는 있지만 message.usage 없음
    invalid = "invalid"  # message.usage 가 dict 아님, 토큰이 정수 아님, timestamp 없음/형식 오류


@dataclass(frozen=True, slots=True)
class UsageRecord:
    """허용 필드만 담는 고정 구조 (privacy.md §1 표). 문자열은 모델명뿐이다."""

    hour: int  # UTC epoch 시(hour) = floor(timestamp / 3600)
    request_key: bytes | None  # blake2b(requestId)[:16], requestId 없으면 None
    model: str
    is_sidechain: bool
    tokens: tuple[int, int, int, int]  # TOKEN_KEYS 순서


def request_key(request_id: str) -> bytes:
    return hashlib.blake2b(request_id.encode("utf-8"), digest_size=16).digest()


def parse_timestamp(value: Any) -> datetime | None:
    """시간대가 있는 ISO 8601 만 허용(`Z` 포함). 시간대 없는 값은 로컬로 오해하지 않게 버린다."""
    if not isinstance(value, str) or len(value) > 64:
        return None
    text = value.strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(UTC)


def _token(value: Any) -> int | None:
    # bool 은 int 의 하위 타입이라 명시적으로 거부한다 (P-04).
    if type(value) is not int or not 0 <= value < MAX_TOKEN_VALUE:
        return None
    return value


def _loads(raw: bytes) -> Any:
    return json.loads(raw)


def parse_line(raw: bytes) -> tuple[LineKind, UsageRecord | None]:
    """한 줄(개행 제외 바이트)을 분류하고, 집계 대상이면 허용 필드만 복사한 레코드를 돌려준다."""
    if USAGE_NEEDLE not in raw:  # 성능 목적 사전 필터 — 파싱 전에 버린다 (P-06)
        return LineKind.no_usage, None
    try:
        obj = _loads(raw)
    except ValueError:  # JSONDecodeError, UnicodeDecodeError 모두 ValueError
        return LineKind.broken, None
    except RecursionError:
        return LineKind.broken, None
    if not isinstance(obj, dict):
        return LineKind.usage_string_only, None
    message = obj.get("message")
    if not isinstance(message, dict) or "usage" not in message:
        return LineKind.usage_string_only, None
    usage = message.get("usage")
    if not isinstance(usage, dict):
        return LineKind.invalid, None
    tokens: list[int] = []
    for key in TOKEN_KEYS:
        value = _token(
            usage.get(key, 0)
        )  # 키가 없으면 0 (Claude Code 가 캐시 필드를 생략할 수 있음)
        if value is None:
            return LineKind.invalid, None
        tokens.append(value)
    ts = parse_timestamp(obj.get("timestamp"))
    if ts is None:
        return LineKind.invalid, None
    model = message.get("model")
    if not isinstance(model, str) or not model or len(model) > MAX_MODEL_LEN:
        model = UNKNOWN_MODEL
    raw_id = obj.get("requestId")
    rkey = request_key(raw_id) if isinstance(raw_id, str) and raw_id else None
    sidechain = obj.get("isSidechain") is True
    record = UsageRecord(
        hour=int(ts.timestamp()) // 3600,
        request_key=rkey,
        model=model,
        is_sidechain=sidechain,
        tokens=(tokens[0], tokens[1], tokens[2], tokens[3]),
    )
    return LineKind.ok, record


def extract_cwd(raw: bytes) -> str | None:
    """디렉터리 해석 폴백 전용 (ADR-002 §1.3, P-05): 사전 필터를 통과한 usage 줄의 `cwd` 만 꺼낸다.

    호출하는 쪽은 비교 직후 값을 버린다(저장·응답·로그 금지).
    """
    if USAGE_NEEDLE not in raw:
        return None
    try:
        obj = _loads(raw)
    except (ValueError, RecursionError):
        return None
    if not isinstance(obj, dict):
        return None
    message = obj.get("message")
    if not isinstance(message, dict) or not isinstance(message.get("usage"), dict):
        return None
    cwd = obj.get("cwd")
    return cwd if isinstance(cwd, str) and 0 < len(cwd) <= 4096 else None
