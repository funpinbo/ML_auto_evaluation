"""기준 집계기 (테스트 오라클). 앱 코드가 아니다.

생성기의 기대값(`JsonlManifest`)을 파일을 다시 읽는 독립 구현으로 교차 검증하는 데 쓴다.
ADR-002 규칙을 가장 단순하게 옮겼다: `"usage":` 사전 필터 -> json.loads -> message.usage 가 dict 인지 확인
-> requestId last-wins(없으면 줄마다 1건) -> UTC 시간 버킷. 성능은 고려하지 않는다.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

from .jsonl_gen import FIXED_NOW, TOKEN_KEYS, UTC, BucketKey, UsageTotals


def aggregate(
    project_dir: Path, *, now: datetime = FIXED_NOW, max_age_days: int = 30
) -> tuple[dict[BucketKey, UsageTotals], Counter[str]]:
    """`(버킷별 합계, 줄 분류 건수)`. symlink 와 mtime 이 만료된 파일은 건너뛴다."""
    counts: Counter[str] = Counter()
    by_request: dict[str, tuple[BucketKey, dict[str, int]]] = {}
    anonymous: list[tuple[BucketKey, dict[str, int]]] = []
    cutoff = (now - timedelta(days=max_age_days)).timestamp()
    root = project_dir.resolve()
    for path in sorted(project_dir.rglob("*.jsonl")):
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            continue
        if path.stat().st_mtime < cutoff:
            continue
        data = path.read_bytes()
        lines = data.split(b"\n")
        lines.pop()  # 개행으로 끝나면 빈 꼬리, 아니면 잘린 마지막 줄 -> 어느 쪽이든 처리하지 않는다
        if not data.endswith(b"\n"):
            counts["truncated_tail_lines"] += 1
        for raw in lines:
            counts["lines_total"] += 1
            if b'"usage":' not in raw:
                counts["no_usage_lines"] += 1
                continue
            try:
                obj = json.loads(raw)
            except ValueError:  # UnicodeDecodeError 포함
                counts["broken_lines"] += 1
                continue
            message = obj.get("message") if isinstance(obj, dict) else None
            if not isinstance(message, dict) or "usage" not in message:
                counts["usage_string_only_lines"] += 1
                continue
            usage = message["usage"]
            if not isinstance(usage, dict):
                counts["invalid_usage_lines"] += 1
                continue
            counts["usage_lines"] += 1
            ts = datetime.fromisoformat(obj["timestamp"]).astimezone(UTC)
            key: BucketKey = (
                ts.strftime("%Y-%m-%dT%H:00:00Z"),
                message["model"],
                bool(obj["isSidechain"]),
            )
            record = (key, {k: usage[k] for k in TOKEN_KEYS})
            request_id = obj.get("requestId")
            if request_id is None:
                counts["no_request_id_lines"] += 1
                anonymous.append(record)
            else:
                if request_id in by_request:
                    counts["duplicate_lines"] += 1
                by_request[request_id] = record
    buckets: dict[BucketKey, UsageTotals] = {}
    for key, usage in [*by_request.values(), *anonymous]:
        buckets.setdefault(key, UsageTotals()).add(usage)
    return buckets, counts
