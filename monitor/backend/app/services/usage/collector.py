"""사용량 수집기 — 증분 커서 + 데우기 (ADR-002 Decision 2·6·8, 20 §4, contracts/README §4).

- 파일별 커서 `(dev, inode, size, mtime_ns, offset)`. size/mtime 이 바뀐 파일만 offset 부터 바이너리로 읽고
  마지막 완전한 줄 끝까지만 처리한다(잘린 꼬리는 다음 주기, P-07). size < offset 또는 inode 변경 → 그 파일
  기여분을 빼고 처음부터 다시 읽는다.
- 탐색은 `<project>/**/*.jsonl`(subagents/ 포함), mtime 30일 이내, symlink 는 따라가지 않고 열 때도
  `O_NOFOLLOW`. 실제 경로가 프로젝트 디렉터리 밖이면 열지 않는다(P-29, `creds-link.jsonl` 케이스).
  하드 링크(`st_nlink > 1`)는 `resolve()` 로 이탈을 판정할 수 없으므로 건너뛴다(I-10, 보수적 기본값).
  여는 것은 모두 `safe_open.open_regular`(lstat → O_NOFOLLOW|O_NONBLOCK → fstat 대조) — 해석기 폴백도 같다.
- 데우기: 백그라운드 스레드 1개가 mtime 내림차순으로 읽는다. `progress()` 는 I/O 없이 즉시 반환한다.
- 로그는 고정 문구 + 건수·코드만 (NFR-002, 20 §6). 경로·이름·줄 내용은 쓰지 않는다.
"""

from __future__ import annotations

import logging
import os
import stat
import threading
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.services.usage.aggregator import UsageStore
from app.services.usage.privacy_filter import LineKind, UsageRecord, parse_line
from app.services.usage.resolver import (
    MAX_AGE_SEC,
    Resolution,
    ResolveSource,
    inside,
    iter_jsonl,
    resolve_project_dir,
)
from app.services.usage.safe_open import open_regular

log = logging.getLogger("aidlc_monitor.usage")

CHUNK_BYTES = 1 << 20
MAX_LINE_BYTES = 32 << 20  # 이보다 긴 줄은 처리하지 않고 형식 오류 1건으로 센다
CWD_RESCAN_SEC = 60.0
MIN_REFRESH_SEC = 1.0
SKIP_KINDS = (LineKind.broken, LineKind.invalid)

MSG_FOUND = "사용량 기록 폴더를 찾았습니다 (%s)"
MSG_NOT_FOUND = "이 프로젝트의 Claude Code 기록 폴더를 찾지 못했습니다"
MSG_HINT = "상태 스냅샷의 기록 폴더 힌트를 무시했습니다: %s"
MSG_SKIPPED = "사용량 기록 형식 오류 %d줄을 건너뛰었습니다"
MSG_ANON = "requestId 없는 사용량 응답 %d건을 중복 제거 없이 집계했습니다"
MSG_LINKS = "하드 링크·일반 파일 아님·경계 밖 기록 파일 %d개를 건너뛰었습니다"
MSG_WARMUP_FAILED = "사용량 데우기 오류: %s"
MSG_REFRESH_FAILED = "사용량 갱신 오류: %s"


@dataclass(slots=True)
class FileCursor:
    file_id: int
    dev: int
    ino: int
    size: int
    mtime_ns: int
    offset: int
    skipping: bool = False  # MAX_LINE_BYTES 초과 줄의 나머지를 건너뛰는 중


@dataclass(frozen=True)
class UsageView:
    """API 용 읽기 결과 (복사본)."""

    buckets: dict[tuple[int, str, bool], tuple[int, int, int, int, int]]
    project_found: bool
    state: str
    progress: float | None
    skipped_lines: int


class UsageCollector:
    def __init__(
        self,
        claude_home: Path,
        repo_root: Path,
        *,
        hint: Callable[[], str | None] = lambda: None,
        clock: Callable[[], datetime],
        monotonic: Callable[[], float] = time.monotonic,
        min_refresh_sec: float = MIN_REFRESH_SEC,
    ) -> None:
        self.claude_home = claude_home
        self.repo_root = repo_root
        self.hint = hint
        self.clock = clock
        self.monotonic = monotonic
        self.min_refresh_sec = min_refresh_sec
        self.store = UsageStore()
        self._cursors: dict[str, FileCursor] = {}
        self._next_id = 0
        self._resolution = Resolution(None, None)
        self._root: Path | None = None
        self._last_cwd_scan: float | None = None
        self._last_refresh: float | None = None
        self._logged: dict[str, object] = {}
        self._refresh_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._state = "not_started"
        self._done_bytes = 0
        self._total_bytes = 0
        self._last_activity_ns: int | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    # ================================================================ 데우기 인터페이스 (contracts/README §4)
    def progress(self) -> dict[str, Any]:
        """`{state, progress}` — I/O·대기 없이 즉시 반환 (health 가 반복 호출)."""
        with self._state_lock:
            state = self._state
            if state == "warming":
                total = self._total_bytes
                value: float | None = (
                    min(1.0, self._done_bytes / total) if total > 0 else 0.0
                )
            elif state == "done":
                value = 1.0
            else:
                value = None
        return {"state": state, "progress": value}

    def start_warmup(self) -> None:
        """서버 시작 시 1회. 이미 시작했으면 아무것도 하지 않는다."""
        with self._state_lock:
            if self._state != "not_started" or self._thread is not None:
                return
            self._state = "warming"
            self._thread = threading.Thread(
                target=self._warmup, name="usage-warmup", daemon=True
            )
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout)

    def _warmup(self) -> None:
        try:
            with self._refresh_lock:
                self._refresh_locked(track_progress=True)
            self._set_state("done")
        except Exception as exc:  # noqa: BLE001 — 스레드 밖으로 내보내지 않는다
            log.error(MSG_WARMUP_FAILED, type(exc).__name__)
            self._set_state("unknown")

    def _set_state(self, state: str) -> None:
        with self._state_lock:
            self._state = state

    # ================================================================ 갱신
    def ensure_fresh(self) -> None:
        """요청 경로용. 데우기 전이면 동기 1회 읽기, 데우기 중이면 기다리지 않음, 끝났으면 증분(1 s 제한)."""
        state = self.progress()["state"]
        if state == "warming":
            return
        if state == "not_started":
            with self._refresh_lock:
                if self.progress()["state"] == "not_started":
                    self._refresh_locked(track_progress=False)
                    self._set_state("done")
            return
        self.refresh()

    def refresh(self, *, force: bool = False) -> bool:
        """증분 1회. 다른 갱신이 진행 중이면 기다리지 않고 False."""
        now = self.monotonic()
        if (
            not force
            and self._last_refresh is not None
            and now - self._last_refresh < self.min_refresh_sec
        ):
            return False
        if not self._refresh_lock.acquire(blocking=False):
            return False
        try:
            self._refresh_locked(track_progress=False)
        except Exception as exc:  # noqa: BLE001 — 패널은 마지막 값으로 계속 그린다
            log.error(MSG_REFRESH_FAILED, type(exc).__name__)
            return False
        finally:
            self._refresh_lock.release()
        return True

    def _resolve(self, now_ts: float) -> Path | None:
        if self._root is not None:
            try:
                if stat.S_ISDIR(os.stat(self._root).st_mode):
                    return self._root
            except OSError:
                pass
            self._drop_all()
            self._root = None
        mono = self.monotonic()
        allow_scan = (
            self._last_cwd_scan is None or mono - self._last_cwd_scan >= CWD_RESCAN_SEC
        )
        try:
            hint = self.hint()
        except Exception:  # noqa: BLE001 — 힌트는 선택 사항
            hint = None
        res = resolve_project_dir(
            self.claude_home,
            self.repo_root,
            hint,
            now=now_ts,
            allow_cwd_scan=allow_scan,
        )
        if allow_scan:
            self._last_cwd_scan = mono
        self._resolution = res
        if res.skipped_files:
            self._log_once(
                "links-fallback",
                res.skipped_files,
                log.warning,
                MSG_LINKS,
                res.skipped_files,
            )
        if res.hint_problem is not None:
            self._log_once(
                "hint", res.hint_problem, log.warning, MSG_HINT, res.hint_problem.value
            )
        if res.path is None:
            self._log_once("found", None, log.info, MSG_NOT_FOUND)
            return None
        source = res.source.value if res.source is not None else "-"
        self._log_once("found", source, log.info, MSG_FOUND, source)
        self._root = res.path
        return res.path

    def _log_once(
        self, key: str, value: object, fn: Callable[..., None], msg: str, *args: object
    ) -> None:
        if self._logged.get(key, object()) != value:
            self._logged[key] = value
            fn(msg, *args)

    def _drop_all(self) -> None:
        with self.store.lock:
            for cursor in self._cursors.values():
                self.store.forget_file(cursor.file_id)
        self._cursors.clear()
        self._last_activity_ns = None

    def _refresh_locked(self, *, track_progress: bool) -> None:
        self._last_refresh = self.monotonic()
        now_ts = self.clock().timestamp()
        root = self._resolve(now_ts)
        if root is None:
            return
        cutoff = now_ts - MAX_AGE_SEC
        entries: list[tuple[str, os.stat_result]] = []
        links = 0
        for entry in iter_jsonl(root, cutoff=cutoff):
            try:
                st = entry.stat(follow_symlinks=False)
            except OSError:
                continue
            if st.st_nlink != 1 or not inside(root, entry.path):
                links += 1
                continue
            entries.append((entry.path, st))
        entries.sort(key=lambda e: e[1].st_mtime_ns, reverse=True)  # 최근 파일 우선
        seen = {path for path, _ in entries}
        for path in [p for p in self._cursors if p not in seen]:
            cursor = self._cursors.pop(path)
            with self.store.lock:
                self.store.forget_file(cursor.file_id)
        if track_progress:
            total = 0
            for path, st in entries:
                cur = self._cursors.get(path)
                total += st.st_size - (
                    cur.offset if cur and cur.ino == st.st_ino else 0
                )
            with self._state_lock:
                self._total_bytes, self._done_bytes = max(total, 0), 0
        before = Counter(self.store.counts)
        latest: int | None = None
        for path, st in entries:
            if self._stop.is_set():
                break
            latest = st.st_mtime_ns if latest is None else max(latest, st.st_mtime_ns)
            if not self._read_file(path, st, track_progress):
                links += 1
        if links:
            self._log_once("links", links, log.warning, MSG_LINKS, links)
        with self.store.lock:
            self.store.prune(int(now_ts) // 3600)
        self._last_activity_ns = latest
        skipped = sum(self.store.counts[k.value] for k in SKIP_KINDS) - sum(
            before[k.value] for k in SKIP_KINDS
        )
        if skipped > 0:
            log.warning(MSG_SKIPPED, skipped)
        anon = self.store.counts["no_request_id"] - before["no_request_id"]
        if anon > 0:
            log.warning(MSG_ANON, anon)

    # ================================================================ 파일 1개 증분 읽기
    def _read_file(self, path: str, st: os.stat_result, track: bool) -> bool:
        """False = 안전 열기 검사에서 거부 (건수만 WARN)."""
        cursor = self._cursors.get(path)
        if cursor is not None and (cursor.ino, cursor.dev) == (st.st_ino, st.st_dev):
            if st.st_size == cursor.size and st.st_mtime_ns == cursor.mtime_ns:
                return True  # 변화 없음 — 열지 않는다
            if st.st_size < cursor.offset:
                self._reset(cursor)  # 잘림 → 처음부터
        elif cursor is not None:
            self._reset(cursor)  # 교체(inode 변경) → 처음부터
            cursor.dev, cursor.ino = st.st_dev, st.st_ino
        else:
            cursor = FileCursor(self._next_id, st.st_dev, st.st_ino, 0, 0, 0)
            self._next_id += 1
            self._cursors[path] = cursor
        opened = open_regular(path, expect=st)
        if opened is None:
            return False  # 탐색과 열기 사이에 링크·비정규 파일로 바뀜 → 건너뜀 (다음 주기 재검사)
        fd, fst = opened
        with os.fdopen(fd, "rb") as fh:
            self._consume(fh, cursor, fst.st_size, track)
            cursor.size, cursor.mtime_ns = fst.st_size, fst.st_mtime_ns
        return True

    def _reset(self, cursor: FileCursor) -> None:
        with self.store.lock:
            self.store.forget_file(cursor.file_id)
        cursor.offset, cursor.size, cursor.mtime_ns, cursor.skipping = 0, 0, 0, False

    def _consume(self, fh: Any, cursor: FileCursor, end: int, track: bool) -> None:
        fh.seek(cursor.offset)
        pos = cursor.offset
        carry = b""
        while pos < end and not self._stop.is_set():
            chunk = fh.read(min(CHUNK_BYTES, end - pos))
            if not chunk:
                break
            pos += len(chunk)
            if track:
                with self._state_lock:
                    self._done_bytes += len(chunk)
            data = carry + chunk
            cut = data.rfind(b"\n")
            if cut < 0:
                carry = data
                if len(carry) > MAX_LINE_BYTES:
                    cursor.skipping = True
                    cursor.offset = pos
                    carry = b""
                    self.store.counts[LineKind.broken.value] += 1
                continue
            complete, carry = data[: cut + 1], data[cut + 1 :]
            lines = complete.split(b"\n")
            lines.pop()  # 마지막 개행 뒤 빈 조각
            if cursor.skipping:
                lines.pop(0)  # 너무 긴 줄의 나머지
                cursor.skipping = False
            self._ingest(cursor.file_id, lines)
            cursor.offset = pos - len(carry)

    def _ingest(self, file_id: int, lines: list[bytes]) -> None:
        records: list[UsageRecord] = []
        kinds: Counter[str] = Counter()
        for raw in lines:
            kind, record = parse_line(raw.rstrip(b"\r"))
            kinds[kind.value] += 1
            if record is not None:
                records.append(record)
        with self.store.lock:
            self.store.counts.update(kinds)
            for record in records:
                self.store.add(file_id, record)

    # ================================================================ 읽기
    def view(self) -> UsageView:
        p = self.progress()
        counts = self.store.counts
        return UsageView(
            buckets=self.store.buckets_copy(),
            project_found=self._root is not None,
            state=p["state"],
            progress=p["progress"],
            skipped_lines=sum(counts[k.value] for k in SKIP_KINDS),
        )

    @property
    def resolution_source(self) -> ResolveSource | None:
        return self._resolution.source if self._root is not None else None

    def last_activity(self) -> datetime | None:
        """V3 "세션 활동" = 추적 중인 JSONL 의 최근 수정 시각. 데우기 전이면 None (파일을 새로 읽지 않음)."""
        if self.progress()["state"] == "done":
            self.refresh()
        ns = self._last_activity_ns
        if ns is None:
            return None
        return datetime.fromtimestamp(ns / 1e9, UTC)
