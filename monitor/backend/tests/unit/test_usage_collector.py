"""사용량 수집기 — 3자 대조(D-17), 중복 제거, 사전 필터, 본문 비접근, 링크 이탈, 증분 커서, 데우기 (T-010, FR-004).

시나리오 참조: test-strategy S-07(집계 구조 표식), S-08(사전 필터·content), S-09(symlink), P-02(증분).
"""

from __future__ import annotations

import builtins
import io
import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any

import pytest
from fixtures import markers, reference_parser
from fixtures.claude_home import encode_project_path
from fixtures.jsonl_gen import FIXED_NOW, TOKEN_KEYS
from usage_support import (
    append_jsonl,
    as_fixture_buckets,
    make_collector,
    usage_line,
    walk_values,
    write_jsonl,
)

from app.services.usage import collector as collector_mod
from app.services.usage import privacy_filter


def _ready(claude_home, root: Path, **kw: Any):
    col = make_collector(claude_home.home, root, hint=claude_home.dir_name, **kw)
    col.ensure_fresh()
    return col


def _totals(col) -> list[int]:
    acc = [0] * 5
    for cell in col.store.buckets_copy().values():
        for i in range(5):
            acc[i] += cell[i]
    return acc


# ---------------------------------------------------------------- 3자 대조 (D-17, AC-9)
def test_three_way_match_generator_oracle_collector(
    claude_home, full_workspace
) -> None:
    col = _ready(claude_home, full_workspace.root)
    expected = claude_home.manifest.expected_buckets
    oracle, counts = reference_parser.aggregate(claude_home.project_dir)
    got = as_fixture_buckets(col.store.buckets_copy())
    assert oracle == expected, "오라클 ↔ 생성기"
    assert got == expected, "수집기 ↔ 생성기"
    assert col.view().project_found
    assert col.store.counts["ok"] == counts["usage_lines"]
    assert col.store.counts["broken"] == counts["broken_lines"]
    assert col.store.counts["no_usage"] == counts["no_usage_lines"]
    assert col.store.counts["usage_string_only"] == counts["usage_string_only_lines"]
    # 거짓 양성 토큰(본문 밖 toolUseResult.usage)은 섞이지 않는다 (P-03)
    assert all(
        markers.FALSE_POSITIVE_TOKENS not in cell
        for cell in col.store.buckets_copy().values()
    )


def test_subagent_files_are_included(claude_home, full_workspace) -> None:
    col = _ready(claude_home, full_workspace.root)
    side = {k: v for k, v in col.store.buckets_copy().items() if k[2]}
    expected = {k: v for k, v in claude_home.manifest.expected_buckets.items() if k[2]}
    assert side and as_fixture_buckets(side) == expected


# ---------------------------------------------------------------- 중복 제거 (AC-10, ADR-002 §4)
def test_dedup_seven_lines_last_wins(tmp_path) -> None:
    home = tmp_path / "home"
    proj = home / "projects" / "p"
    lines = [usage_line("req-a", (1, 1, 1, 1)) for _ in range(6)] + [
        usage_line("req-a", (9, 8, 7, 6))
    ]
    write_jsonl(proj / "s.jsonl", lines)
    col = make_collector(home, tmp_path, hint="p")
    col.ensure_fresh()
    assert _totals(col) == [1, 9, 8, 7, 6]
    assert col.store.unique_requests == 1
    assert col.store.counts["duplicates"] == 6


def test_dedup_is_global_across_files_and_moves_bucket(tmp_path) -> None:
    home = tmp_path / "home"
    proj = home / "projects" / "p"
    write_jsonl(
        proj / "a.jsonl", [usage_line("r1", (1, 1, 1, 1), ts="2026-10-23T05:00:00Z")]
    )
    write_jsonl(
        proj / "sub" / "subagents" / "agent-1.jsonl",
        [usage_line("r1", (2, 2, 2, 2), ts="2026-10-23T06:00:00Z")],
    )
    col = make_collector(home, tmp_path, hint="p")
    col.ensure_fresh()
    buckets = col.store.buckets_copy()
    assert sum(v[0] for v in buckets.values()) == 1
    assert len(buckets) == 1  # 이전 버킷 기여분은 빠졌다


def test_missing_request_id_counts_each_line_and_warns(tmp_path, caplog) -> None:
    home = tmp_path / "home"
    write_jsonl(
        home / "projects" / "p" / "s.jsonl", [usage_line(None), usage_line(None)]
    )
    col = make_collector(home, tmp_path, hint="p")
    with caplog.at_level(logging.WARNING, logger="aidlc_monitor"):
        col.ensure_fresh()
    assert _totals(col)[0] == 2
    assert "requestId 없는 사용량 응답 2건" in caplog.text


# ---------------------------------------------------------------- 사전 필터·본문 비접근 (S-08, T-05·T-06)
def test_prefilter_skips_json_loads_for_lines_without_usage(
    claude_home, full_workspace, monkeypatch
) -> None:
    calls: list[bytes] = []
    real = privacy_filter._loads

    def spy(raw: bytes) -> Any:
        calls.append(raw)
        return real(raw)

    monkeypatch.setattr(privacy_filter, "_loads", spy)
    _ready(claude_home, full_workspace.root)
    assert calls, "파싱이 한 번도 없으면 검사가 무의미"
    assert all(privacy_filter.USAGE_NEEDLE in raw for raw in calls)
    _, counts = reference_parser.aggregate(claude_home.project_dir)
    assert len(calls) == counts["lines_total"] - counts["no_usage_lines"]


ALLOWED_KEYS = {
    "message",
    "usage",
    "model",
    "timestamp",
    "requestId",
    "isSidechain",
    *TOKEN_KEYS,
}


class _Trap(dict):
    """허용 필드 밖 키 접근·순회 시 예외 (content trap, T-06)."""

    def _check(self, key: object) -> None:
        if key not in ALLOWED_KEYS:
            raise AssertionError(f"허용 필드 밖 키 접근: {key!r}")

    def __getitem__(self, key: object) -> Any:
        self._check(key)
        return super().__getitem__(key)

    def get(self, key: object, default: Any = None) -> Any:
        self._check(key)
        return super().get(key, default)

    def __iter__(self):
        raise AssertionError("dict 순회")

    def keys(self):
        raise AssertionError("dict 순회")

    def items(self):
        raise AssertionError("dict 순회")

    def values(self):
        raise AssertionError("dict 순회")


def test_only_allow_listed_keys_are_touched(
    claude_home, full_workspace, monkeypatch
) -> None:
    monkeypatch.setattr(
        privacy_filter, "_loads", lambda raw: json.loads(raw, object_hook=_Trap)
    )
    col = _ready(claude_home, full_workspace.root)
    assert (
        as_fixture_buckets(col.store.buckets_copy())
        == claude_home.manifest.expected_buckets
    )


def test_body_with_usage_literal_does_not_leak(tmp_path) -> None:
    """본문에 `"usage":` 가 그대로 든 줄(사전 필터 통과)도 허용 필드만 남는다 (P-03)."""
    home = tmp_path / "home"
    line = usage_line("r1")
    line["message"]["content"] = [
        {"type": "text", "text": markers.BODY, "usage": {"input_tokens": 777777}}
    ]
    raw = json.dumps(line).encode()
    assert privacy_filter.USAGE_NEEDLE in raw
    write_jsonl(home / "projects" / "p" / "s.jsonl", [raw])
    col = make_collector(home, tmp_path, hint="p")
    col.ensure_fresh()
    assert _totals(col) == [1, 1, 2, 3, 4]
    markers.assert_no_markers(*walk_values(col.store), where="store")


@pytest.mark.parametrize(
    ("usage", "kind"),
    [
        ("n/a", "invalid"),
        ({"input_tokens": "1"}, "invalid"),
        ({"input_tokens": True}, "invalid"),
        ({"input_tokens": -1}, "invalid"),
        ({"input_tokens": 1.5}, "invalid"),
        ({"input_tokens": 3}, "ok"),  # 누락 키는 0
    ],
)
def test_invalid_usage_values_are_dropped(usage, kind) -> None:
    line = usage_line("r1")
    line["message"]["usage"] = usage
    got, record = privacy_filter.parse_line(json.dumps(line).encode())
    assert got.value == kind
    if kind == "ok":
        assert record is not None and record.tokens == (3, 0, 0, 0)


@pytest.mark.parametrize(
    "ts",
    [None, "2026-10-23T08:00:00", "yesterday", 1792742400, "2026-10-23T08:00:00+09:00"],
)
def test_timestamp_rules(ts) -> None:
    line = usage_line("r1")
    line["timestamp"] = ts
    kind, record = privacy_filter.parse_line(json.dumps(line).encode())
    if ts == "2026-10-23T08:00:00+09:00":
        assert kind.value == "ok" and record is not None
        assert record.hour * 3600 == int(FIXED_NOW.replace(hour=23, day=22).timestamp())
    else:
        assert kind.value == "invalid"


def test_odd_json_shapes() -> None:
    assert privacy_filter.parse_line(b'["usage": 1]')[0].value == "broken"
    assert (
        privacy_filter.parse_line(b'["x", {"usage": 1}]')[0].value
        == "usage_string_only"
    )
    assert privacy_filter.parse_line(b'"\\"usage\\": x"')[0].value == "no_usage"
    assert (
        privacy_filter.parse_line(b'{"message": "m", "usage": 1}')[0].value
        == "usage_string_only"
    )
    assert privacy_filter.parse_line(b'{"usage": {}}')[0].value == "usage_string_only"
    assert privacy_filter.parse_line(b"[" * 100000 + b'"usage":')[0].value == "broken"
    line = usage_line("r1", model="x" * 500)
    line["isSidechain"] = "yes"
    _kind, record = privacy_filter.parse_line(json.dumps(line).encode())
    assert (
        record is not None
        and record.model == "unknown"
        and record.is_sidechain is False
    )


# ---------------------------------------------------------------- 메모리 구조 표식 (S-07, T-03·P-11)
def test_store_has_no_markers_paths_or_ids(claude_home, full_workspace) -> None:
    col = _ready(claude_home, full_workspace.root)
    values = list(walk_values(col.store))
    assert values, "순회 결과가 비면 검사가 무의미"
    markers.assert_no_markers(
        *values, extra=claude_home.forbidden_strings(), where="usage store"
    )
    strings = {v for v in values if isinstance(v, str)}
    # 문자열 값은 모델명과 건수 분류 키뿐이다
    assert strings <= {"claude-fake-opus", "claude-fake-sonnet", "unknown"} | {
        "ok", "no_usage", "broken", "usage_string_only", "invalid", "no_request_id", "duplicates",
    }  # fmt: skip


# ---------------------------------------------------------------- 링크 이탈 (S-09, P-28·P-29, I-10)
def test_symlink_escapes_are_not_opened(
    claude_home, full_workspace, symlink_escape, monkeypatch
) -> None:
    opened: list[str] = []
    real_open = os.open

    def spy(path, flags, *args, **kwargs):
        opened.append(os.fspath(path))
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(collector_mod.os, "open", spy)
    col = _ready(claude_home, full_workspace.root)
    assert opened
    proj = str(claude_home.project_dir.resolve())
    assert all(os.path.realpath(p).startswith(proj + os.sep) for p in opened)
    names = {os.path.basename(p) for p in opened}
    assert not names & {"linked.jsonl", "creds-link.jsonl", "leak.jsonl"}
    assert all(424242 not in cell for cell in col.store.buckets_copy().values())
    assert (
        as_fixture_buckets(col.store.buckets_copy())
        == claude_home.manifest.expected_buckets
    )


def test_credentials_link_never_read_anywhere(
    claude_home, full_workspace, symlink_escape, monkeypatch
) -> None:
    """`creds-link.jsonl -> ../../.credentials.json` (CLAUDE_HOME 안, 프로젝트 밖): 어떤 open 경로로도 읽지 않는다."""
    seen: list[str] = []
    real_open, real_bopen = os.open, builtins.open

    def track(path: object) -> None:
        if isinstance(path, str | os.PathLike):
            seen.append(os.path.realpath(os.fspath(path)))

    def os_spy(path, *a, **k):
        track(path)
        return real_open(path, *a, **k)

    def b_spy(file, *a, **k):
        track(file)
        return real_bopen(file, *a, **k)

    monkeypatch.setattr(os, "open", os_spy)
    monkeypatch.setattr(builtins, "open", b_spy)
    monkeypatch.setattr(io, "open", b_spy)
    _ready(claude_home, full_workspace.root)
    monkeypatch.undo()
    creds = os.path.realpath(claude_home.home / ".credentials.json")
    history = os.path.realpath(claude_home.home / "history.jsonl")
    assert creds not in seen and history not in seen
    assert str(symlink_escape.outside_file) not in seen


def test_hardlinked_files_are_skipped(tmp_path, caplog, monkeypatch) -> None:
    opened = _spy_os_open(monkeypatch)
    home = tmp_path / "home"
    proj = home / "projects" / "p"
    outside = write_jsonl(
        tmp_path / "outside.jsonl", [usage_line("leak", (424242, 0, 0, 0))]
    )
    write_jsonl(proj / "ok.jsonl", [usage_line("r1")])
    try:
        os.link(outside, proj / "hard.jsonl")
    except OSError as exc:
        pytest.skip(f"하드 링크를 만들 수 없음: {type(exc).__name__}")
    col = make_collector(home, tmp_path, hint="p")
    with caplog.at_level(logging.WARNING, logger="aidlc_monitor"):
        col.ensure_fresh()
    assert _totals(col) == [1, 1, 2, 3, 4]
    assert (
        "하드 링크·일반 파일 아님·경계 밖 기록 파일 1개를 건너뛰었습니다" in caplog.text
    )
    assert str(tmp_path) not in caplog.text
    assert not [
        p for p in opened if os.path.basename(p) in ("hard.jsonl", "outside.jsonl")
    ]


def _spy_os_open(monkeypatch) -> list[str]:
    opened: list[str] = []
    real = os.open

    def spy(path, *a, **k):
        opened.append(os.fspath(path))
        return real(path, *a, **k)

    monkeypatch.setattr(os, "open", spy)
    return opened


def test_hardlink_swapped_in_after_scan_is_not_read(tmp_path, monkeypatch) -> None:
    """탐색 뒤 열기 전에 하드 링크로 바뀌어도(TOCTOU) 열기 단계 검사가 거부한다."""
    from app.services.usage import safe_open

    home = tmp_path / "home"
    proj = home / "projects" / "p"
    target = write_jsonl(proj / "s.jsonl", [usage_line("r1")])
    outside = write_jsonl(
        tmp_path / "secret.jsonl", [usage_line("leak", (424242, 0, 0, 0))]
    )
    real_lstat = os.lstat

    def swap(path, *a, **k):
        if os.fspath(path) == str(target) and not os.path.samefile(target, outside):
            target.unlink()
            os.link(outside, target)
        return real_lstat(path, *a, **k)

    monkeypatch.setattr(safe_open.os, "lstat", swap)
    col = make_collector(home, tmp_path, hint="p")
    col.ensure_fresh()
    assert _totals(col)[0] == 0


# ---------------------------------------------------------------- 증분 커서 (ADR-002 §2, P-07)
def test_incremental_append_and_partial_tail(tmp_path, monkeypatch) -> None:
    home = tmp_path / "home"
    f = write_jsonl(home / "projects" / "p" / "s.jsonl", [usage_line("r1")])
    col = make_collector(home, tmp_path, hint="p")
    col.ensure_fresh()
    assert _totals(col)[0] == 1
    partial = json.dumps(usage_line("r3")).encode()
    append_jsonl(f, [usage_line("r2")], tail=partial[:20])
    reads: list[int] = []
    real = collector_mod.UsageCollector._consume

    def spy(self, fh, cursor, end, track):
        reads.append(end - cursor.offset)
        return real(self, fh, cursor, end, track)

    monkeypatch.setattr(collector_mod.UsageCollector, "_consume", spy)
    col.refresh()
    assert _totals(col)[0] == 2
    assert reads[-1] < f.stat().st_size, "처음부터 다시 읽지 않는다"
    with f.open("ab") as fh:
        fh.write(partial[20:] + b"\n")
    os.utime(f, (f.stat().st_mtime + 1,) * 2)
    col.refresh()
    assert _totals(col)[0] == 3
    reads.clear()
    col.refresh()  # 변화 없음 → 열지도 않는다
    assert reads == []


def test_truncation_and_rotation_reset_file_contribution(tmp_path) -> None:
    home = tmp_path / "home"
    proj = home / "projects" / "p"
    f = write_jsonl(
        proj / "s.jsonl", [usage_line("r1"), usage_line("r2"), usage_line("r3")]
    )
    col = make_collector(home, tmp_path, hint="p")
    col.ensure_fresh()
    assert _totals(col)[0] == 3
    # 잘림: 같은 inode, 더 작은 크기
    with f.open("r+b") as fh:
        fh.truncate(0)
        fh.write(json.dumps(usage_line("r9", (5, 5, 5, 5))).encode() + b"\n")
    os.utime(f, (f.stat().st_mtime + 5,) * 2)
    col.refresh()
    assert _totals(col) == [1, 5, 5, 5, 5]
    # 교체: 새 inode (os.replace)
    new = write_jsonl(
        proj / "tmp.txt",
        [usage_line("r7", (2, 2, 2, 2)), usage_line("r8", (2, 2, 2, 2))],
    )
    os.replace(new, f)
    os.utime(f, (f.stat().st_mtime + 10,) * 2)
    col.refresh()
    assert _totals(col) == [2, 4, 4, 4, 4]
    # 삭제: 기여분 제거
    f.unlink()
    col.refresh()
    assert _totals(col) == [0, 0, 0, 0, 0]


def test_project_dir_disappearing_drops_everything(tmp_path) -> None:
    home = tmp_path / "home"
    proj = home / "projects" / "p"
    write_jsonl(proj / "s.jsonl", [usage_line("r1")])
    col = make_collector(home, tmp_path, hint="p")
    col.ensure_fresh()
    (proj / "s.jsonl").unlink()
    proj.rmdir()
    col.refresh()
    assert not col.view().project_found and _totals(col)[0] == 0


def test_overlong_line_is_skipped_without_blocking(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(collector_mod, "MAX_LINE_BYTES", 1000)
    monkeypatch.setattr(collector_mod, "CHUNK_BYTES", 256)
    home = tmp_path / "home"
    big = json.dumps(usage_line("big") | {"pad": "x" * 5000}).encode()
    write_jsonl(home / "projects" / "p" / "s.jsonl", [big, usage_line("r1")])
    col = make_collector(home, tmp_path, hint="p")
    col.ensure_fresh()
    assert _totals(col)[0] == 1
    assert col.view().skipped_lines >= 1


def test_expired_and_old_records_follow_30_day_window(tmp_path) -> None:
    home = tmp_path / "home"
    proj = home / "projects" / "p"
    old = FIXED_NOW.replace(month=9, day=1)
    write_jsonl(proj / "old.jsonl", [usage_line("r-old")], mtime=old)
    write_jsonl(
        proj / "new.jsonl",
        [usage_line("r-new"), usage_line("r-ancient", ts="2026-08-01T00:00:00Z")],
    )
    col = make_collector(home, tmp_path, hint="p")
    col.ensure_fresh()
    assert _totals(col)[0] == 1  # 만료 파일 제외, 30일 지난 레코드는 정리


def test_refresh_throttle_and_busy_lock(tmp_path) -> None:
    home = tmp_path / "home"
    write_jsonl(home / "projects" / "p" / "s.jsonl", [usage_line("r1")])
    now = [100.0]
    col = make_collector(
        home, tmp_path, hint="p", min_refresh_sec=1.0, monotonic=lambda: now[0]
    )
    col.ensure_fresh()
    assert col.refresh() is False  # 1 s 이내
    now[0] += 2
    assert col.refresh() is True
    now[0] += 2
    with col._refresh_lock:
        assert col.refresh() is False  # 다른 갱신 중이면 기다리지 않음


def test_refresh_error_is_logged_by_type_only(tmp_path, monkeypatch, caplog) -> None:
    col = make_collector(tmp_path / "home", tmp_path, hint="p")

    def boom(**_: Any) -> None:
        raise OSError(f"{tmp_path}/{markers.PATH}")

    monkeypatch.setattr(col, "_refresh_locked", boom)
    with caplog.at_level(logging.ERROR, logger="aidlc_monitor"):
        assert col.refresh(force=True) is False
    assert "사용량 갱신 오류: OSError" in caplog.text
    markers.assert_no_markers(caplog.text, extra=(str(tmp_path),))


# ---------------------------------------------------------------- 데우기 (ADR-002 §6, contracts/README §4)
def test_warmup_progress_states_and_newest_first(
    claude_home, full_workspace, monkeypatch
) -> None:
    col = make_collector(
        claude_home.home, full_workspace.root, hint=claude_home.dir_name
    )
    assert col.progress() == {"state": "not_started", "progress": None}
    gate, entered = threading.Event(), threading.Event()
    order: list[int] = []
    real = collector_mod.UsageCollector._read_file

    def slow(self, path, st, track):
        order.append(st.st_mtime_ns)
        if len(order) == 3:
            entered.set()
            gate.wait(5)
        return real(self, path, st, track)

    monkeypatch.setattr(collector_mod.UsageCollector, "_read_file", slow)
    col.start_warmup()
    col.start_warmup()  # 두 번째 호출은 무시
    assert entered.wait(5)
    mid = col.progress()
    assert mid["state"] == "warming" and 0.0 < mid["progress"] < 1.0
    started = time.monotonic()
    col.ensure_fresh()  # 데우는 중에는 기다리지 않는다
    assert time.monotonic() - started < 1.0
    gate.set()
    col._thread.join(10)
    assert not col._thread.is_alive()
    assert col.progress() == {"state": "done", "progress": 1.0}
    assert order == sorted(order, reverse=True), "최근 파일 우선"
    assert (
        as_fixture_buckets(col.store.buckets_copy())
        == claude_home.manifest.expected_buckets
    )


def test_warmup_failure_reports_unknown(tmp_path, monkeypatch, caplog) -> None:
    col = make_collector(tmp_path, tmp_path)

    def boom(**_: Any) -> None:
        raise RuntimeError(markers.PATH)

    monkeypatch.setattr(col, "_refresh_locked", boom)
    with caplog.at_level(logging.ERROR, logger="aidlc_monitor"):
        col.start_warmup()
        col._thread.join(5)
    assert col.progress() == {"state": "unknown", "progress": None}
    assert "사용량 데우기 오류: RuntimeError" in caplog.text
    markers.assert_no_markers(caplog.text)


def test_stop_interrupts_warmup(claude_home, full_workspace) -> None:
    col = make_collector(
        claude_home.home, full_workspace.root, hint=claude_home.dir_name
    )
    col._stop.set()
    col.start_warmup()
    col.stop()
    assert not col._thread.is_alive()


def test_last_activity_only_after_warm(tmp_path) -> None:
    home = tmp_path / "home"
    write_jsonl(home / "projects" / "p" / "s.jsonl", [usage_line("r1")])
    col = make_collector(home, tmp_path, hint="p")
    assert col.last_activity() is None  # 데우기 전에는 파일을 읽지 않는다
    col.ensure_fresh()
    assert col.last_activity() == FIXED_NOW


# ---------------------------------------------------------------- 성능 (P-02 근사, 짧게)
def test_perf_50mb_cold_and_incremental(tmp_path) -> None:
    home = tmp_path / "home"
    proj = home / "projects" / "p"
    proj.mkdir(parents=True)
    usage = json.dumps(usage_line("r")).encode()
    filler = json.dumps({"type": "user", "message": {"content": "y" * 20000}}).encode()
    target = 50 * 1024 * 1024
    with (proj / "big.jsonl").open("wb") as fh:
        n, written = 0, 0
        while written < target:
            n += 1
            line = usage.replace(b'"requestId": "r"', f'"requestId": "r{n}"'.encode())
            block = line + b"\n" + filler + b"\n"
            fh.write(block)
            written += len(block)
    os.utime(proj / "big.jsonl", (FIXED_NOW.timestamp(),) * 2)
    col = make_collector(home, tmp_path, hint="p")
    t0 = time.perf_counter()
    col.ensure_fresh()
    cold = time.perf_counter() - t0
    assert _totals(col)[0] == n
    append_jsonl(proj / "big.jsonl", [usage_line(f"x{i}") for i in range(50)])
    t1 = time.perf_counter()
    col.refresh()
    incremental = time.perf_counter() - t1
    assert _totals(col)[0] == n + 50
    assert cold < 5.0, f"cold {cold:.2f}s"
    assert incremental < 0.5, f"incremental {incremental:.3f}s"


def test_encode_rule_matches_fixture_encoder() -> None:
    from app.services.usage.resolver import encode_project_path as app_encode

    for p in ("/home/user/chatbot", "C:\\x\\y", "/a b/c.d_e"):
        assert app_encode(p) == encode_project_path(p)


def test_incremental_reads_only_new_bytes_exact_counts(tmp_path, monkeypatch) -> None:
    """qa 변이: offset 을 무시하고 0 부터 다시 읽으면 requestId 없는 줄이 두 번 세진다 → 정확한 건수·버킷 + 읽은 바이트 단언."""
    home = tmp_path / "home"
    f = write_jsonl(
        home / "projects" / "p" / "s.jsonl",
        [usage_line("r1", (1, 0, 0, 0)), usage_line(None, (10, 0, 0, 0))],
    )
    col = make_collector(home, tmp_path, hint="p")
    col.ensure_fresh()
    assert _totals(col) == [2, 11, 0, 0, 0]
    first_size = f.stat().st_size
    append_jsonl(
        f,
        [
            usage_line(None, (100, 0, 0, 0)),
            usage_line("r2", (1000, 0, 0, 0), ts="2026-10-23T07:30:00.000Z"),
        ],
    )
    appended = f.stat().st_size - first_size

    seeks: list[int] = []
    read_bytes: list[int] = []
    real_fdopen = os.fdopen

    class Spy:
        def __init__(self, fh) -> None:
            self.fh = fh

        def seek(self, pos, *a):
            seeks.append(pos)
            return self.fh.seek(pos, *a)

        def read(self, n=-1):
            data = self.fh.read(n)
            read_bytes.append(len(data))
            return data

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            self.fh.close()

    monkeypatch.setattr(
        collector_mod.os, "fdopen", lambda fd, *a, **k: Spy(real_fdopen(fd, *a, **k))
    )
    col.refresh()
    assert seeks == [first_size]
    assert sum(read_bytes) == appended
    assert _totals(col) == [4, 1111, 0, 0, 0]
    hours = {k[0]: v[0] for k, v in col.store.buckets_copy().items()}
    h08 = int(FIXED_NOW.replace(hour=8).timestamp()) // 3600
    assert hours == {h08: 3, h08 - 1: 1}
    assert col.store.counts["no_request_id"] == 2
