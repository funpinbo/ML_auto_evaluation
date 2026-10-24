"""사용량 수집기 테스트 공용 도우미 (backend 소유, T-010).

- 시계는 qa fixture 의 `FIXED_NOW` 로 고정한다(생성기 기대값과 같은 기준, 30일 창 판정 포함).
- 작은 JSONL 은 `usage_line` 으로 직접 만든다. 모든 줄에 본문 표식을 넣어 비노출 검사가 가능하다.
- `walk_values` 는 객체 그래프(dict·list·set·tuple·dataclass·`__slots__`·`__dict__`)를 순회해 문자열·바이트를 모은다.
"""

from __future__ import annotations

import dataclasses
import json
import os
import threading
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fixtures import markers
from fixtures.jsonl_gen import FIXED_NOW, TOKEN_KEYS, BucketKey, UsageTotals

from app.services.usage.collector import UsageCollector


def clock() -> datetime:
    return FIXED_NOW


def make_collector(
    home: Path, root: Path, hint: str | None = None, **kw: Any
) -> UsageCollector:
    kw.setdefault("min_refresh_sec", 0.0)
    return UsageCollector(home, root, hint=lambda: hint, clock=clock, **kw)


def as_fixture_buckets(
    buckets: dict[tuple[int, str, bool], tuple[int, int, int, int, int]],
) -> dict[BucketKey, UsageTotals]:
    """수집기 키 (epoch hour, model, sidechain) → 생성기 키 ('YYYY-MM-DDTHH:00:00Z', model, sidechain)."""
    out: dict[BucketKey, UsageTotals] = {}
    for (hour, model, side), cell in buckets.items():
        key = (
            datetime.fromtimestamp(hour * 3600, UTC).strftime("%Y-%m-%dT%H:00:00Z"),
            model,
            side,
        )
        out[key] = UsageTotals(cell[0], *cell[1:])
    return out


def usage_line(
    request_id: str | None,
    tokens: tuple[int, int, int, int] = (1, 2, 3, 4),
    *,
    ts: str = "2026-10-23T08:15:00.000Z",
    model: str = "claude-fake-opus",
    sidechain: bool = False,
    cwd: str | None = None,
) -> dict[str, Any]:
    line: dict[str, Any] = {
        "type": "assistant",
        "timestamp": ts,
        "sessionId": markers.SESSION,
        "uuid": markers.UUID,
        "isSidechain": sidechain,
        "extraNote": markers.EXTRA,
        "message": {
            "model": model,
            "content": [{"type": "text", "text": markers.BODY}],
            "usage": dict(zip(TOKEN_KEYS, tokens, strict=True)),
        },
    }
    if request_id is not None:
        line["requestId"] = request_id
    if cwd is not None:
        line["cwd"] = cwd
    return line


def write_jsonl(
    path: Path,
    lines: list[dict[str, Any] | bytes],
    *,
    mtime: datetime | None = None,
    tail: bytes = b"",
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = b"".join(
        (ln if isinstance(ln, bytes) else json.dumps(ln).encode()) + b"\n"
        for ln in lines
    )
    path.write_bytes(data + tail)
    stamp = (mtime or FIXED_NOW).timestamp()
    os.utime(path, (stamp, stamp))
    return path


def append_jsonl(path: Path, lines: list[dict[str, Any]], *, tail: bytes = b"") -> None:
    st = path.stat()
    with path.open("ab") as fh:
        for ln in lines:
            fh.write(json.dumps(ln).encode() + b"\n")
        fh.write(tail)
    stamp = st.st_mtime + 1
    os.utime(path, (stamp, stamp))


def walk_values(obj: Any, _seen: set[int] | None = None) -> Iterator[str | bytes]:
    seen = set() if _seen is None else _seen
    if id(obj) in seen:
        return
    seen.add(id(obj))
    if isinstance(obj, str | bytes):
        yield obj
        return
    if isinstance(obj, int | float | bool) or obj is None:
        return
    if isinstance(obj, type(threading.Lock())):
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from walk_values(k, seen)
            yield from walk_values(v, seen)
        return
    if isinstance(obj, list | tuple | set | frozenset):
        for v in obj:
            yield from walk_values(v, seen)
        return
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        for f in dataclasses.fields(obj):
            yield from walk_values(getattr(obj, f.name), seen)
        return
    for name in getattr(type(obj), "__slots__", ()):
        if hasattr(obj, name):
            yield from walk_values(getattr(obj, name), seen)
    if hasattr(obj, "__dict__"):
        for v in vars(obj).values():  # 속성 이름은 코드라 제외, 값만
            yield from walk_values(v, seen)
