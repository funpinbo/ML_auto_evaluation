"""GET /api/v1/usage/summary · /usage/timeseries (FR-004 AC-1~AC-19, S-03·S-05~S-09, NFR-002·003).

- 시계는 `FIXED_NOW` 로 주입한다(생성기·오라클과 같은 기준).
- 3자 대조(D-17): 생성기 기대값 = 오라클(`reference_parser.aggregate`) = API 응답.
- 비노출: 모든 응답·헤더·로그에 표식·경로·`transcript_dir_name` 0회 (privacy T-01·T-02, D-13).
"""

from __future__ import annotations

import io
import json
import time
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from backend_support import (
    assert_error,
    install_engine,
    make_client,
    make_settings,
    walk_keys,
)
from fixtures import markers, reference_parser
from fixtures.claude_home import encode_project_path
from fixtures.jsonl_gen import FIXED_NOW, TOKEN_KEYS, write_project_jsonl
from fixtures.runtime_files import (
    INVALID_DIR_NAMES,
    claude_status_doc,
    write_claude_status,
    write_json,
)

from app.logging_config import setup_logging
from app.main import create_app

SUMMARY = "/api/v1/usage/summary"
SERIES = "/api/v1/usage/timeseries"
FIELDS = ("responses", *TOKEN_KEYS)


def _client(ws, home: Path | None, *, now: datetime = FIXED_NOW):
    app = create_app(make_settings(ws.root, claude_home=home), clock=lambda: now)
    return app, make_client(app)


def _get(client, url: str) -> dict[str, Any]:
    resp = client.get(url)
    assert resp.status_code == 200, (resp.status_code, resp.text)
    return resp.json()


@pytest.fixture
def normal(full_workspace, claude_home):
    write_claude_status(
        full_workspace.claude_status_file,
        "normal",
        transcript_dir_name=claude_home.dir_name,
    )
    return full_workspace, claude_home


def _hour(key: str) -> int:
    return (
        int(
            datetime.strptime(key, "%Y-%m-%dT%H:00:00Z").replace(tzinfo=UTC).timestamp()
        )
        // 3600
    )


def _oracle_cells(home) -> dict[tuple[int, str, bool], list[int]]:
    buckets, _ = reference_parser.aggregate(home.project_dir)
    assert buckets == home.manifest.expected_buckets  # 오라클 ↔ 생성기
    return {
        (_hour(k[0]), k[1], k[2]): [getattr(v, f) for f in FIELDS]
        for k, v in buckets.items()
    }


def _sum(cells) -> dict[str, Any]:
    acc = [0] * 5
    for c in cells:
        for i in range(5):
            acc[i] += c[i]
    denom = acc[1] + acc[3] + acc[4]
    return dict(zip(FIELDS, acc, strict=True)) | {
        "cache_hit_rate": round(acc[4] / denom, 6) if denom else None
    }


# ---------------------------------------------------------------- summary (AC-1·AC-16)
def test_summary_normal_matches_oracle(normal) -> None:
    ws, home = normal
    _, client = _client(ws, home.home)
    body = _get(client, SUMMARY)
    data, meta = body["data"], body["meta"]
    assert meta["status"] == "ok" and meta["warnings"] == [] and meta["error"] is None
    assert data["scope"] == "project" and data["project_dir_found"] is True
    assert data["limits_available"] is True and data["limits_notice"] is None
    assert data["five_hour"]["used_percentage"] == 23.5
    assert data["five_hour"]["resets_at"] == int(
        (FIXED_NOW + timedelta(hours=2)).timestamp()
    )
    assert data["five_hour"]["reset_passed"] is False
    assert data["seven_day"]["used_percentage"] == 41
    assert data["session_cost_usd"] == 0.12
    assert data["snapshot"]["state"] == "ok" and data["snapshot"]["stale"] is False
    cells = _oracle_cells(home)
    now_ts = FIXED_NOW.timestamp()
    today = [
        v
        for (h, _m, _s), v in cells.items()
        if (h * 3600) // 86400 == int(now_ts) // 86400
    ]
    assert data["today"]["totals"] == _sum(today)
    start = now_ts - 3 * 3600  # resets_at − 5h
    five = [
        v
        for (h, _m, _s), v in cells.items()
        if (h + 1) * 3600 > start and h * 3600 <= now_ts
    ]
    assert data["five_hour_tokens"]["estimated"] is False
    assert data["five_hour_tokens"]["totals"] == _sum(five)
    assert data["five_hour_tokens"]["totals"]["responses"] > 0
    assert data["skipped_lines"] == 3  # 깨진 2 + usage 비 dict 1
    assert data["warming"] == {"state": "done", "progress": 1.0}


def test_summary_tz_offset_changes_today(normal) -> None:
    ws, home = normal
    _, client = _client(ws, home.home)
    cells = _oracle_cells(home)
    for off in (-600, 540):
        data = _get(client, f"{SUMMARY}?tz_offset_min={off}")["data"]
        today = (FIXED_NOW.timestamp() + off * 60) // 86400
        exp = [
            v
            for (h, _m, _s), v in cells.items()
            if (h * 3600 + off * 60) // 86400 == today
        ]
        assert data["today"]["totals"] == _sum(exp)


def test_summary_no_snapshot_falls_back_to_tokens(
    full_workspace, claude_home_factory, tmp_path
) -> None:
    """AC-5: 스냅샷 없음 → 한도 안내 + 토큰 집계(규칙 인코딩으로 찾은 디렉터리)."""
    ws = full_workspace
    home = tmp_path / "home"
    proj = home / "projects" / encode_project_path(ws.root.resolve())
    manifest = write_project_jsonl(proj, days=3, responses_per_day=4)
    _, client = _client(ws, home)
    body = _get(client, SUMMARY)
    data = body["data"]
    assert body["meta"]["status"] == "ok"
    assert data["limits_available"] is False and data["five_hour"] is None
    assert "CLI 세션에서 실행하면 한도가 표시됩니다" in data["limits_notice"]
    assert data["snapshot"] == {
        "state": "missing",
        "captured_at": None,
        "age_sec": None,
        "stale": False,
        "code": "SOURCE_MISSING",
    }
    assert data["session_cost_usd"] is None
    assert data["five_hour_tokens"]["estimated"] is True
    series = _get(client, f"{SERIES}?range=30d&bucket=hour&group=none")["data"]
    assert series["totals"]["responses"] == manifest.expected_totals.responses


def test_summary_no_rate_limits(full_workspace, claude_home) -> None:
    write_claude_status(
        full_workspace.claude_status_file,
        "no_rate_limits",
        transcript_dir_name=claude_home.dir_name,
    )
    _, client = _client(full_workspace, claude_home.home)
    body = _get(client, SUMMARY)
    assert body["meta"]["status"] == "ok"
    assert body["data"]["limits_available"] is False
    assert (
        body["data"]["limits_notice"]
        == "한도 정보 없음 — Pro/Max 구독의 CLI 세션에서 첫 응답 이후 표시"
    )
    assert body["data"]["today"]["totals"]["responses"] > 0


def test_summary_one_window_missing_and_reset_passed(
    full_workspace, claude_home
) -> None:
    doc = claude_status_doc("normal", transcript_dir_name=claude_home.dir_name)
    doc["rate_limits"]["seven_day"] = None
    doc["rate_limits"]["five_hour"]["resets_at"] = int(
        (FIXED_NOW - timedelta(minutes=1)).timestamp()
    )
    write_json(full_workspace.claude_status_file, doc)
    _, client = _client(full_workspace, claude_home.home)
    data = _get(client, SUMMARY)["data"]
    assert data["limits_available"] is True and data["seven_day"] is None
    assert data["five_hour"]["reset_passed"] is True
    assert (
        data["five_hour_tokens"]["estimated"] is True
    )  # 지난 resets_at 은 구간 경계로 쓰지 않는다


@pytest.mark.parametrize(("age", "stale"), [(600, False), (601, True), (1800, True)])
def test_summary_stale_boundary(
    full_workspace, claude_home, age: int, stale: bool
) -> None:
    doc = claude_status_doc("normal", transcript_dir_name=claude_home.dir_name)
    doc["captured_at"] = (FIXED_NOW - timedelta(seconds=age)).isoformat()
    write_json(full_workspace.claude_status_file, doc)
    _, client = _client(full_workspace, claude_home.home)
    body = _get(client, SUMMARY)
    assert body["data"]["snapshot"]["stale"] is stale
    assert body["data"]["limits_available"] is True  # 값은 계속 표시
    if stale:
        assert body["meta"]["status"] == "partial"
        assert body["meta"]["error"]["code"] == "SNAPSHOT_STALE"
        assert (
            f"{age // 60}분 전 기준 — 최신 값이 아닐 수 있음"
            in body["meta"]["warnings"]
        )
    else:
        assert body["meta"]["status"] == "ok" and body["meta"]["error"] is None


def test_summary_broken_snapshot_is_partial_tokens_ok(full_workspace, tmp_path) -> None:
    """AC-8: 깨진 스냅샷 → 한도만 SOURCE_PARSE_ERROR, 토큰 정상, 500 없음."""
    ws = full_workspace
    write_claude_status(ws.claude_status_file, "broken")
    home = tmp_path / "home"
    write_project_jsonl(
        home / "projects" / encode_project_path(ws.root.resolve()),
        days=2,
        responses_per_day=3,
    )
    _, client = _client(ws, home)
    body = _get(client, SUMMARY)
    assert body["meta"]["status"] == "partial"
    assert body["meta"]["error"]["code"] == "SOURCE_PARSE_ERROR"
    assert body["data"]["limits_notice"] == "한도 정보를 읽을 수 없음"
    assert body["data"]["snapshot"]["code"] == "SOURCE_PARSE_ERROR"
    assert body["data"]["today"]["totals"]["responses"] > 0


def test_project_dir_not_found(full_workspace, claude_home_factory) -> None:
    """AC-13: 기록 폴더 없음 → summary 는 한도만, timeseries 는 PROJECT_DIR_NOT_FOUND. 모두 HTTP 200."""
    home = claude_home_factory(full_workspace.root, with_jsonl=False)
    write_claude_status(
        full_workspace.claude_status_file, "normal", transcript_dir_name=home.dir_name
    )
    _, client = _client(full_workspace, home.home)
    body = _get(client, SUMMARY)
    assert body["meta"]["status"] == "partial"
    assert body["meta"]["error"]["code"] == "PROJECT_DIR_NOT_FOUND"
    assert (
        body["data"]["limits_available"] is True
        and body["data"]["tokens_code"] == "PROJECT_DIR_NOT_FOUND"
    )
    series = _get(client, SERIES)
    assert series["meta"]["status"] == "empty"
    assert series["meta"]["error"]["code"] == "PROJECT_DIR_NOT_FOUND"
    assert series["data"]["project_dir_found"] is False


def test_nothing_at_all_is_empty(empty_workspace, tmp_path) -> None:
    _, client = _client(empty_workspace, tmp_path / "none")
    body = _get(client, SUMMARY)
    assert body["meta"]["status"] == "empty"
    assert "사용 기록이 없습니다" in body["meta"]["warnings"]


def test_no_records_in_range_is_empty(full_workspace, tmp_path) -> None:
    """AC-14: 디렉터리는 있지만 최근 기록 0건."""
    home = tmp_path / "home"
    (home / "projects" / encode_project_path(full_workspace.root.resolve())).mkdir(
        parents=True
    )
    _, client = _client(full_workspace, home)
    body = _get(client, SERIES)
    assert (
        body["meta"]["status"] == "empty"
        and "선택한 기간에 기록 없음" in body["meta"]["warnings"]
    )
    assert body["data"]["totals"]["responses"] == 0 and body["data"]["series"] == []


# ---------------------------------------------------------------- timeseries (AC-9·AC-11·AC-12)
def test_timeseries_30d_hour_model_three_way(normal) -> None:
    ws, home = normal
    _, client = _client(ws, home.home)
    data = _get(client, f"{SERIES}?range=30d&bucket=hour&group=model")["data"]
    assert len(data["buckets"]) == 720
    exp: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0] * 5)
    for (h, model, _s), cell in _oracle_cells(home).items():
        label = datetime.fromtimestamp(h * 3600, UTC).strftime("%Y-%m-%dT%H:00:00Z")
        for i in range(5):
            exp[(label, model)][i] += cell[i]
    got: dict[tuple[str, str], list[int]] = {}
    for s in data["series"]:
        for i, label in enumerate(data["buckets"]):
            vals = [s[f][i] for f in FIELDS]
            if any(vals):
                got[(label, s["key"])] = vals
    assert got == dict(exp)
    for s in data["series"]:
        assert 777777 not in s["input_tokens"] and 424242 not in s["input_tokens"]


def test_timeseries_defaults_and_groups(normal) -> None:
    ws, home = normal
    _, client = _client(ws, home.home)
    d = _get(client, SERIES)["data"]
    assert (d["range"], d["bucket"], d["group"], len(d["buckets"])) == (
        "24h",
        "hour",
        "model",
        24,
    )
    assert (
        d["buckets"][-1] == "2026-10-23T09:00:00Z"
        and d["end"] == "2026-10-23T10:00:00Z"
    )
    assert {s["key"] for s in d["series"]} <= {"claude-fake-opus", "claude-fake-sonnet"}
    assert len(_get(client, f"{SERIES}?range=5h")["data"]["buckets"]) == 5
    assert len(_get(client, f"{SERIES}?range=7d")["data"]["buckets"]) == 168
    month = _get(client, f"{SERIES}?range=30d")["data"]
    assert month["bucket"] == "day" and len(month["buckets"]) == 30
    side = _get(client, f"{SERIES}?range=30d&group=sidechain")["data"]
    assert {s["key"] for s in side["series"]} == {"main", "subagent"}
    none = _get(client, f"{SERIES}?range=30d&group=none")["data"]
    assert [s["key"] for s in none["series"]] == ["all"]
    total = home.manifest.expected_totals
    assert none["totals"]["responses"] == total.responses
    assert none["totals"]["output_tokens"] == total.output_tokens
    assert side["totals"] == none["totals"] == month["totals"]


def test_timeseries_day_buckets_use_local_midnight(normal) -> None:
    ws, home = normal
    _, client = _client(ws, home.home)
    off = 540
    d = _get(client, f"{SERIES}?range=7d&bucket=day&group=none&tz_offset_min={off}")[
        "data"
    ]
    assert len(d["buckets"]) == 7 and d["buckets"][-1] == "2026-10-23T00:00:00+09:00"
    today = (FIXED_NOW.timestamp() + off * 60) // 86400
    exp = [0] * 7
    for (h, _m, _s), cell in _oracle_cells(home).items():
        day = (h * 3600 + off * 60) // 86400
        if today - 6 <= day <= today:
            exp[int(day - (today - 6))] += cell[0]
    assert d["series"][0]["responses"] == exp


@pytest.mark.parametrize(
    "query",
    [
        "range=1h",
        "range=",
        "bucket=week",
        "group=team",
        "tz_offset_min=900",
        "tz_offset_min=-841",
        "tz_offset_min=x",
    ],
)
def test_timeseries_validation_errors(normal, query: str) -> None:
    ws, home = normal
    _, client = _client(ws, home.home)
    body = assert_error(client.get(f"{SERIES}?{query}"), 422, "VALIDATION_ERROR")
    value = query.split("=", 1)[1]
    assert (
        not value or value not in body["error"]["message"]
    )  # 입력 원문을 되돌려주지 않는다 (N-07)


def test_summary_validation_error(normal) -> None:
    ws, home = normal
    _, client = _client(ws, home.home)
    assert_error(client.get(f"{SUMMARY}?tz_offset_min=10000"), 422, "VALIDATION_ERROR")


# ---------------------------------------------------------------- 힌트 재검증 (AC-19, P-25~P-28)
@pytest.mark.parametrize("name", INVALID_DIR_NAMES)
def test_invalid_hint_is_ignored_in_api(full_workspace, claude_home, name: str) -> None:
    doc = claude_status_doc("normal", transcript_dir_name="x")
    doc["transcript_dir_name"] = name  # 스키마 위반 값을 직접 쓴다 (작성자 우회 가정)
    write_json(full_workspace.claude_status_file, doc)
    _, client = _client(full_workspace, claude_home.home)
    body = _get(client, SUMMARY)
    assert body["data"]["project_dir_found"] is False
    assert body["meta"]["error"]["code"] == "PROJECT_DIR_NOT_FOUND"


def test_hint_symlink_outside_projects_is_ignored(
    full_workspace, claude_home, symlink_escape
) -> None:
    write_claude_status(
        full_workspace.claude_status_file,
        "normal",
        transcript_dir_name=symlink_escape.dir_link_name,
    )
    _, client = _client(full_workspace, claude_home.home)
    data = _get(client, f"{SERIES}?range=30d&group=none")["data"]
    assert data["project_dir_found"] is False and data["totals"]["responses"] == 0


# ---------------------------------------------------------------- 비노출 (AC-17, S-05·S-06, T-01·T-02)
ALL_GETS = (
    "/api/v1/health", "/api/v1/pipeline", "/api/v1/plan", "/api/v1/tasks", "/api/v1/memory", "/api/v1/control",
    SUMMARY, f"{SUMMARY}?tz_offset_min=540", SERIES, f"{SERIES}?range=30d&bucket=hour&group=model",
    f"{SERIES}?range=7d&group=sidechain", f"{SERIES}?range=5h&group=none", f"{SERIES}?range=bogus",
)  # fmt: skip


def test_no_markers_paths_or_dir_name_in_responses_and_logs(
    full_workspace, claude_home, symlink_escape, tmp_path
) -> None:
    install_engine(full_workspace.root)
    write_claude_status(
        full_workspace.claude_status_file,
        "normal",
        transcript_dir_name=claude_home.dir_name,
    )
    stream = io.StringIO()
    setup_logging(stream=stream)
    _, client = _client(full_workspace, claude_home.home)
    texts: list[str] = []
    for url in ALL_GETS:
        resp = client.get(url)
        assert resp.status_code in (200, 422), (url, resp.status_code)
        texts += [resp.text, json.dumps(dict(resp.headers))]
        if resp.status_code == 200:
            assert "transcript_dir_name" not in set(walk_keys(resp.json()))
    out = stream.getvalue()
    assert (
        "사용량 기록 형식 오류 3줄을 건너뛰었습니다" in out
    )  # 빈 로그로 통과하지 않게
    assert "사용량 기록 폴더를 찾았습니다 (hint)" in out
    forbidden = (
        *claude_home.forbidden_strings(),
        str(full_workspace.root),
        str(tmp_path),
        symlink_escape.dir_link_name,
    )
    markers.assert_no_markers(*texts, extra=forbidden, where="usage responses")
    markers.assert_no_markers(out, extra=forbidden, where="usage logs")


def test_invalid_hint_log_has_code_only(full_workspace, claude_home) -> None:
    bad = f"../{markers.DIR_NAME}"
    doc = claude_status_doc("normal", transcript_dir_name="x")
    doc["transcript_dir_name"] = bad
    write_json(full_workspace.claude_status_file, doc)
    stream = io.StringIO()
    setup_logging(stream=stream)
    _, client = _client(full_workspace, claude_home.home)
    _get(client, SUMMARY)
    out = stream.getvalue()
    assert (
        "HINT_INVALID_NAME" not in out
    )  # reader 가 먼저 버려 해석기는 힌트를 받지 않는다
    assert "기록 폴더를 찾지 못했습니다" in out
    markers.assert_no_markers(out, extra=(bad, *claude_home.forbidden_strings()))


# ---------------------------------------------------------------- 데우기·health·control 연동
def test_warming_status_and_health_progress(normal, monkeypatch) -> None:
    import threading

    from app.services.usage import collector as collector_mod

    ws, home = normal
    app, client = _client(ws, home.home)
    gate, entered = threading.Event(), threading.Event()
    real = collector_mod.UsageCollector._read_file

    def slow(self, path, st, track):
        entered.set()
        gate.wait(5)
        return real(self, path, st, track)

    monkeypatch.setattr(collector_mod.UsageCollector, "_read_file", slow)
    app.state.warmup.start_warmup()
    try:
        assert entered.wait(5)
        assert (
            _get(client, "/api/v1/health")["data"]["usage_warming"]["state"]
            == "warming"
        )
        started = time.monotonic()
        body = _get(client, SUMMARY)
        assert time.monotonic() - started < 2.0  # AC-15: 기다리지 않고 부분 값
        assert body["meta"]["status"] == "warming"
        assert body["data"]["warming"]["state"] == "warming"
        assert _get(client, SERIES)["meta"]["status"] == "warming"
    finally:
        gate.set()
        app.state.warmup._thread.join(10)
    assert _get(client, "/api/v1/health")["data"]["usage_warming"] == {
        "state": "done",
        "progress": 1.0,
    }


def test_lifespan_starts_warmup(normal) -> None:
    from backend_support import BASE_URL
    from fastapi.testclient import TestClient

    ws, home = normal
    app = create_app(
        make_settings(ws.root, claude_home=home.home), clock=lambda: FIXED_NOW
    )
    with TestClient(app, base_url=BASE_URL) as client:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            state = client.get("/api/v1/health").json()["data"]["usage_warming"]
            if state["state"] == "done":
                break
            time.sleep(0.02)
        assert state == {"state": "done", "progress": 1.0}
    assert not app.state.warmup._thread.is_alive()


def test_create_app_does_no_usage_io(normal, monkeypatch) -> None:
    """앱 생성·health 는 JSONL 을 열지 않는다 (export_openapi·런처 health 폴링)."""
    import os

    ws, home = normal
    opened: list[str] = []
    real = os.open

    def spy(path, *a, **k):
        opened.append(os.fspath(path))
        return real(path, *a, **k)

    monkeypatch.setattr(os, "open", spy)
    app, client = _client(ws, home.home)
    _get(client, "/api/v1/health")
    _get(client, "/api/v1/control")
    assert not [p for p in opened if p.startswith(str(home.home))]
    assert app.state.warmup.progress()["state"] == "not_started"


def test_control_session_activity_after_warm(normal) -> None:
    ws, home = normal
    write_json(
        ws.root / "workspace" / "memory" / ".monitor" / "loop-status.json",
        _loop_running(),
    )
    _, client = _client(ws, home.home)
    before = _get(client, "/api/v1/control")["data"]
    assert before["session_activity_at"] is None
    _get(client, SUMMARY)
    after = _get(client, "/api/v1/control")["data"]
    newest = max(
        p.stat().st_mtime
        for p in home.manifest.files
        if not p.name.startswith("expired")
    )
    assert after["view"] == "V3"
    assert (
        after["session_activity_at"]
        == datetime.fromtimestamp(int(newest), UTC).isoformat()
    )
    assert after["session_activity_age_sec"] == max(
        0, int(FIXED_NOW.timestamp() - newest)
    )


def _loop_running() -> dict[str, Any]:
    from fixtures.runtime_files import loop_status_doc

    return loop_status_doc("running")


def test_usage_panel_error_is_isolated(normal, monkeypatch) -> None:
    ws, home = normal
    app, client = _client(ws, home.home)

    def boom(*a, **k):
        raise KeyError(markers.PATH)

    monkeypatch.setattr(app.state.services.usage, "summary", boom)
    body = _get(client, SUMMARY)
    assert body["data"] is None and body["meta"]["status"] == "error"
    markers.assert_no_markers(json.dumps(body))
