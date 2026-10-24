"""사용량 집계 구조 — 프로세스 메모리만 (ADR-002 Decision 4·5·8, privacy.md P-11).

- 버킷: `(UTC epoch hour, model, is_sidechain) → [responses, input, output, cache_creation, cache_read]`
- 중복 제거: `requestId` 다이제스트 → 기여값(버킷 키, 토큰, 기여 파일 id). 전역(파일을 넘어), last-wins —
  같은 값이면 무시, 다르면 이전 기여분을 빼고 새 값을 더한다.
- `requestId` 없는 줄은 1건씩 센다(파일별 목록에 둔다 — 파일 초기화 때 빼기 위해).
- 파일은 정수 id 로만 구분한다. 이 구조에는 경로·ID 원문·본문이 없다(문자열은 모델명뿐).
- 동시성: `threading.Lock` 하나. 읽기는 복사본(`buckets_copy`)으로 한다.
"""

from __future__ import annotations

import threading
from collections import Counter
from dataclasses import dataclass, field

from app.services.usage.privacy_filter import UsageRecord

BucketKey = tuple[int, str, bool]
Tokens = tuple[int, int, int, int]
WINDOW_HOURS = 30 * 24


@dataclass(slots=True)
class _Contribution:
    key: BucketKey
    tokens: Tokens
    file_id: int


@dataclass
class _FileShare:
    """파일 하나가 기여한 응답 — 잘림·교체로 파일을 처음부터 다시 읽을 때 뺀다 (ADR-002 §2)."""

    request_keys: set[bytes] = field(default_factory=set)
    anonymous: list[tuple[BucketKey, Tokens]] = field(default_factory=list)


class UsageStore:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self._buckets: dict[BucketKey, list[int]] = {}
        self._by_request: dict[bytes, _Contribution] = {}
        self._files: dict[int, _FileShare] = {}
        self.counts: Counter[str] = Counter()

    # ------------------------------------------------------------ 갱신 (lock 은 호출자가 잡는다)
    def _apply(self, key: BucketKey, tokens: Tokens, sign: int) -> None:
        cell = self._buckets.get(key)
        if cell is None:
            if sign < 0:
                return
            cell = self._buckets[key] = [0, 0, 0, 0, 0]
        cell[0] += sign
        for i, value in enumerate(tokens, start=1):
            cell[i] += sign * value
        if cell[0] <= 0:
            del self._buckets[key]

    def add(self, file_id: int, record: UsageRecord) -> None:
        key: BucketKey = (record.hour, record.model, record.is_sidechain)
        share = self._files.setdefault(file_id, _FileShare())
        if record.request_key is None:
            self.counts["no_request_id"] += 1
            share.anonymous.append((key, record.tokens))
            self._apply(key, record.tokens, +1)
            return
        prev = self._by_request.get(record.request_key)
        if prev is not None:
            self.counts["duplicates"] += 1
            if prev.file_id != file_id:
                old = self._files.get(prev.file_id)
                if old is not None:
                    old.request_keys.discard(record.request_key)
                prev.file_id = file_id
            share.request_keys.add(record.request_key)
            if prev.key == key and prev.tokens == record.tokens:
                return  # 같은 값 → 무시 (30 EDA: 중복 그룹 95/95 동일)
            self._apply(prev.key, prev.tokens, -1)
            prev.key, prev.tokens = key, record.tokens
            self._apply(key, record.tokens, +1)
            return
        self._by_request[record.request_key] = _Contribution(
            key, record.tokens, file_id
        )
        share.request_keys.add(record.request_key)
        self._apply(key, record.tokens, +1)

    def forget_file(self, file_id: int) -> None:
        """그 파일 기여분을 requestId 단위로 뺀다 (잘림·inode 변경·삭제)."""
        share = self._files.pop(file_id, None)
        if share is None:
            return
        for rkey in share.request_keys:
            contrib = self._by_request.get(rkey)
            if contrib is not None and contrib.file_id == file_id:
                self._apply(contrib.key, contrib.tokens, -1)
                del self._by_request[rkey]
        for key, tokens in share.anonymous:
            self._apply(key, tokens, -1)

    def prune(self, now_hour: int) -> None:
        """30일 지난 버킷·requestId 를 정리한다."""
        cutoff = now_hour - WINDOW_HOURS
        for key in [k for k in self._buckets if k[0] < cutoff]:
            del self._buckets[key]
        stale = [k for k, c in self._by_request.items() if c.key[0] < cutoff]
        for rkey in stale:
            contrib = self._by_request.pop(rkey)
            share = self._files.get(contrib.file_id)
            if share is not None:
                share.request_keys.discard(rkey)
        for share in self._files.values():
            share.anonymous = [a for a in share.anonymous if a[0][0] >= cutoff]

    # ------------------------------------------------------------ 읽기
    def buckets_copy(self) -> dict[BucketKey, tuple[int, int, int, int, int]]:
        with self.lock:
            return {k: (v[0], v[1], v[2], v[3], v[4]) for k, v in self._buckets.items()}

    @property
    def unique_requests(self) -> int:
        return len(self._by_request)
