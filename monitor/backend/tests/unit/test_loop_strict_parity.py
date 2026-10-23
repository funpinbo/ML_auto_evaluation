"""엄격 정수 술어 교차 검증 (loop-cli §2.1, D-40, SQ-16·SQ-17).

CLI(`aidlc/scripts/loop_control.py`)와 대시보드(`app/services/control.py`)는 판독 코드를 공유하지 않는다
(CLI 는 표준 라이브러리 단독 스크립트). 이 테스트가 같은 입력 바이트에 대해 두 구현의 판정이 같고,
그 판정이 "계약 스키마(jsonschema) 통과 + 엄격 정수 술어" 와 같음을 보인다.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fixtures.contracts import is_valid
from fixtures.runtime_files import control_doc, loop_status_doc
from loop_support import lc

from app.services import control as svc

SEQ_MAX = 9007199254740991
BIG = "9" * 4301


def _ctl_text(seq_literal: str, **over: str) -> bytes:
    fields = {
        "schema": "1",
        "seq": seq_literal,
        "state": '"pause"',
        "requested_at": '"2026-10-23T08:00:00+00:00"',
        "max_pause_sec": "7200",
        **over,
    }
    return ("{" + ", ".join(f'"{k}": {v}' for k, v in fields.items()) + "}").encode()


CONTROL_CORPUS: dict[str, bytes] = {
    "ok": _ctl_text("8"),
    "ok-max": _ctl_text(str(SEQ_MAX)),
    "ok-running": _ctl_text("1", state='"running"'),
    "ok-z": _ctl_text("3", requested_at='"2026-10-23T08:00:00Z"'),
    "ok-frac": _ctl_text("3", requested_at='"2026-10-23T08:00:00.123+09:00"'),
    "seq-float": _ctl_text("7.0"),
    "seq-exp": _ctl_text("8e0"),
    "seq-EXP": _ctl_text("7E+0"),
    "seq-true": _ctl_text("true"),
    "seq-false": _ctl_text("false"),
    "seq-zero": _ctl_text("0"),
    "seq-neg": _ctl_text("-1"),
    "seq-over": _ctl_text(str(SEQ_MAX + 1)),
    "seq-17digits": _ctl_text("1" + "0" * 16),
    "seq-4301": _ctl_text(BIG),
    "seq-nan": _ctl_text("NaN"),
    "seq-inf": _ctl_text("Infinity"),
    "seq-neginf": _ctl_text("-Infinity"),
    "seq-string": _ctl_text('"8"'),
    "seq-null": _ctl_text("null"),
    "schema-2": _ctl_text("8", schema="2"),
    "schema-1.0": _ctl_text("8", schema="1.0"),
    "schema-true": _ctl_text("8", schema="true"),
    "state-bad": _ctl_text("8", state='"paused"'),
    "max-599": _ctl_text("8", max_pause_sec="599"),
    "max-86401": _ctl_text("8", max_pause_sec="86401"),
    "max-float": _ctl_text("8", max_pause_sec="7200.0"),
    "max-true": _ctl_text("8", max_pause_sec="true"),
    "ts-no-offset": _ctl_text("8", requested_at='"2026-10-23T08:00:00"'),
    "ts-month13": _ctl_text("8", requested_at='"2026-13-23T08:00:00Z"'),
    "ts-trailing-nl": _ctl_text("8", requested_at='"2026-10-23T08:00:00Z\\n"'),
    "extra-key": _ctl_text("8", extra='"x"'),
    "missing-key": b'{"schema": 1, "seq": 8, "state": "pause", "requested_at": "2026-10-23T08:00:00Z"}',
    "array": b"[]",
    "truncated": b'{"schema": 1, "seq": 8, "state": "pa',
    "empty": b"",
    "bom": b"\xef\xbb\xbf" + _ctl_text("8"),
    "latin1": _ctl_text("8", state='"pause"').replace(b"pause", b"pa\xffse"),
    "deep": b"[" * 100000 + b"]" * 100000,
    "huge": b'{"pad": "' + b"x" * (70 * 1024) + b'"}',
}
VALID_CONTROL = {"ok", "ok-max", "ok-running", "ok-z", "ok-frac"}


@pytest.mark.parametrize("name", sorted(CONTROL_CORPUS))
def test_control_cli_and_dashboard_agree(tmp_path: Path, name: str) -> None:
    path = tmp_path / ".control.json"
    path.write_bytes(CONTROL_CORPUS[name])
    cli = lc.read_control(path)
    dash = svc.read_control(path)
    assert cli.status == dash.status == ("ok" if name in VALID_CONTROL else "broken")
    assert (cli.seq, cli.state, cli.max_pause_sec) == (
        dash.seq,
        dash.state,
        dash.max_pause_sec,
    )
    if cli.status == "ok":
        assert type(cli.seq) is int and type(dash.seq) is int


@pytest.mark.parametrize("name", sorted(CONTROL_CORPUS))
def test_control_predicate_matches_schema_plus_strict_int(name: str) -> None:
    """판정 = jsonschema 통과 ∧ 엄격 정수 (스키마만으로는 7.0·true 를 못 거른다)."""
    try:
        doc = json.loads(CONTROL_CORPUS[name])
    except (ValueError, RecursionError):
        doc = None
    expected = name in VALID_CONTROL
    # 인코딩·크기·날짜 실재성은 스키마 밖 규칙(UTF-8 BOM 없음, 64 KiB, fromisoformat) — 더 엄격한 쪽
    if doc is not None and name not in ("ts-month13", "ts-trailing-nl", "huge", "bom"):
        strict = (
            all(type(doc.get(k)) is int for k in ("schema", "seq", "max_pause_sec"))
            if isinstance(doc, dict)
            else False
        )
        assert (is_valid(doc, "control") and strict) == expected, name
    assert lc.valid_control(doc) == svc.valid_control(doc)


def test_schema_alone_accepts_float_seq() -> None:
    """근거 고정: JSON Schema integer 는 7.0 을 통과시킨다 → 술어가 필요하다."""
    assert is_valid(control_doc("pause", 7) | {"seq": 7.0}, "control")
    assert not lc.valid_control(control_doc("pause", 7) | {"seq": 7.0})
    assert not svc.valid_control(control_doc("pause", 7) | {"seq": True})


BASELINE_CASES = {
    "neg": -1,
    "string": "7",
    "true": True,
    "float": 7.0,
    "over": SEQ_MAX + 1,
}


def _status_variants() -> dict[str, bytes]:
    base = loop_status_doc("running")
    out = {
        f"baseline-{k}": json.dumps(base | {"baseline_seq": v}).encode()
        for k, v in BASELINE_CASES.items()
    }
    out["baseline-4301"] = (
        json.dumps(base).replace('"baseline_seq": 6', f'"baseline_seq": {BIG}').encode()
    )
    out["missing-run_id"] = json.dumps(
        {k: v for k, v in base.items() if k != "run_id"}
    ).encode()
    out["paused-no-since"] = json.dumps(base | {"state": "paused"}).encode()
    out["running-with-since"] = json.dumps(
        base | {"paused_since": base["started_at"]}
    ).encode()
    out["ended-no-reason"] = json.dumps(base | {"state": "ended"}).encode()
    out["running-with-reason"] = json.dumps(base | {"ended_reason": "done"}).encode()
    out["timeout-no-since"] = json.dumps(
        base | {"state": "ended", "ended_reason": "pause_timeout"}
    ).encode()
    out["done-gt-total"] = json.dumps(base | {"iterations_done": 4}).encode()
    out["total-11"] = json.dumps(base | {"iterations_total": 11}).encode()
    out["run_id-upper"] = json.dumps(base | {"run_id": base["run_id"].upper()}).encode()
    out["truncated"] = b'{"schema": 1, "run_id": '
    for scenario in ("running", "paused", "resumed", "pause_timeout", "done"):
        out[f"ok-{scenario}"] = json.dumps(loop_status_doc(scenario)).encode()
    out["ok-max-baseline"] = json.dumps(base | {"baseline_seq": SEQ_MAX}).encode()
    return out


STATUS_CORPUS = _status_variants()


@pytest.mark.parametrize("name", sorted(STATUS_CORPUS))
def test_loop_status_cli_and_dashboard_agree(tmp_path: Path, name: str) -> None:
    path = tmp_path / "loop-status.json"
    path.write_bytes(STATUS_CORPUS[name])
    cli = lc.read_loop_status(path)
    dash = svc.read_loop_status(path)
    ok = name.startswith("ok-")
    assert (cli is not None) == ok == (dash.status == "ok"), name
    assert dash.baseline == (cli["baseline_seq"] if cli else 0)
    try:
        doc = json.loads(STATUS_CORPUS[name])
    except ValueError:
        return
    strict = isinstance(doc, dict) and all(
        type(doc.get(k)) is int
        for k in ("schema", "baseline_seq", "iterations_total", "iterations_done")
    )
    if name != "done-gt-total":  # 불변식은 스키마로 표현 불가 (스키마 description)
        assert (is_valid(doc, "loop-status") and strict) == ok, name


@pytest.mark.parametrize(
    ("x", "lo", "hi", "want"),
    [
        (1, 1, 1, True),
        (True, 0, 1, False),
        (1.0, 0, 2, False),
        (0, 1, 5, False),
        (SEQ_MAX, 1, SEQ_MAX, True),
        (SEQ_MAX + 1, 1, SEQ_MAX, False),
        ("1", 0, 5, False),
        (None, 0, 5, False),
    ],
)
def test_is_strict_int_identical(x: object, lo: int, hi: int, want: bool) -> None:
    assert lc.is_strict_int(x, lo, hi) is svc.is_strict_int(x, lo, hi) is want


def test_constants_identical() -> None:
    for name in (
        "SEQ_MAX",
        "MAX_PAUSE_MIN",
        "MAX_PAUSE_MAX",
        "MAX_PAUSE_DEFAULT",
        "ITER_MAX",
        "INT_DIGITS_MAX",
        "READ_LIMIT",
        "REPLACE_TRIES",
        "REPLACE_GAP_SEC",
        "CONTROL_KEYS",
        "STATUS_KEYS",
    ):
        assert getattr(lc, name) == getattr(svc, name), name
    assert lc._TS_RE.pattern == svc._TS_RE.pattern
    assert lc._RUN_ID_RE.pattern == svc._RUN_ID_RE.pattern
