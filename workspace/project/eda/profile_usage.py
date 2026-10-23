#!/usr/bin/env python3
"""DS-03 (Claude Code 세션 기록 JSONL) 프로파일러 — 표준 라이브러리만 사용.

개인정보 규칙 (00 해석서 Q2 적용):
  1. 줄을 원문 텍스트로 읽고, 부분 문자열 "usage" 가 없는 줄은 json 파싱 전에 버린다.
  2. 파싱한 줄에서 timestamp, requestId, message.model, message.usage 의 숫자 4종,
     isSidechain, sessionId 만 새 dict 로 복사하고 원본 객체는 즉시 버린다.
  3. message.content 를 포함한 다른 필드 값은 출력·저장·로그하지 않는다.
  4. 출력(summary)에는 개수·합계·분포 같은 집계값만 남긴다. requestId/sessionId 값 자체도 남기지 않는다.

사용법: python3 profile_usage.py [projects_dir] [--out summary_usage.json]
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import os
import sys
import time
from pathlib import Path

TOKEN_KEYS = ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")


def extract(line: str) -> dict | None:
    """허용 필드만 복사한다. usage dict 가 없으면 None."""
    try:
        obj = json.loads(line)
    except ValueError:
        return {"_bad_json": True}
    if not isinstance(obj, dict):
        return None
    msg = obj.get("message")
    usage = msg.get("usage") if isinstance(msg, dict) else None
    rec = None
    if isinstance(usage, dict):
        rec = {
            "timestamp": obj.get("timestamp"),
            "requestId": obj.get("requestId"),
            "model": msg.get("model"),
            "isSidechain": obj.get("isSidechain"),
            "sessionId": obj.get("sessionId"),
        }
        for k in TOKEN_KEYS:
            v = usage.get(k)
            rec[k] = v if isinstance(v, int) else None
    del obj, msg, usage  # 원본 즉시 폐기
    return rec


def scan_file(path: Path, stats: dict) -> list[dict]:
    recs: list[dict] = []
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            stats["lines"] += 1
            if "usage" not in line:
                stats["skipped_no_substring"] += 1
                continue
            stats["substring_hit"] += 1
            r = extract(line)
            if r is None:
                stats["substring_but_no_usage"] += 1
                continue
            if r.get("_bad_json"):
                stats["bad_json"] += 1
                continue
            recs.append(r)
    return recs


def parse_ts(s) -> dt.datetime | None:
    if not isinstance(s, str):
        return None
    try:
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def tok_sum(rs) -> dict:
    out = {k: 0 for k in TOKEN_KEYS}
    for r in rs:
        for k in TOKEN_KEYS:
            out[k] += r[k] or 0
    return out


def hit_rate(t: dict) -> float | None:
    denom = t["input_tokens"] + t["cache_creation_input_tokens"] + t["cache_read_input_tokens"]
    return round(t["cache_read_input_tokens"] / denom, 4) if denom else None


def main() -> int:
    args = sys.argv[1:]
    out = Path(__file__).with_name("summary_usage.json")
    if "--out" in args:
        i = args.index("--out")
        out = Path(args[i + 1])
        del args[i : i + 2]
    root = Path(args[0]) if args else Path.home() / ".claude" / "projects" / "-home-user-chatbot"

    files = sorted(root.rglob("*.jsonl"))
    total_bytes = sum(f.stat().st_size for f in files)
    stats = collections.Counter()
    per_file = []
    all_recs: list[dict] = []
    t0 = time.perf_counter()
    for f in files:
        before = stats["lines"]
        fs = time.perf_counter()
        rs = scan_file(f, stats)
        for r in rs:
            r["_file"] = len(per_file)  # 파일 경로 대신 인덱스만
            r["_sub"] = "subagents" in f.parts
        per_file.append({
            "kind": "subagent" if "subagents" in f.parts else "main",
            "bytes": f.stat().st_size,
            "lines": stats["lines"] - before,
            "usage_lines": len(rs),
            "parse_sec": round(time.perf_counter() - fs, 4),
        })
        all_recs.extend(rs)
    parse_sec = time.perf_counter() - t0

    # 결측
    missing = {k: sum(1 for r in all_recs if r.get(k) is None)
               for k in ("timestamp", "requestId", "model", "sessionId", *TOKEN_KEYS)}

    # requestId 중복 분석
    groups: dict = collections.defaultdict(list)
    for idx, r in enumerate(all_recs):
        key = r["requestId"] or f"__noreq_{idx}"
        groups[key].append(r)
    sizes = collections.Counter(len(v) for v in groups.values())
    dup_groups = [v for v in groups.values() if len(v) > 1]
    identical = sum(1 for v in dup_groups
                    if len({tuple(x[k] for k in TOKEN_KEYS) for x in v}) == 1)
    diff_fields = collections.Counter()
    last_is_max = 0
    for v in dup_groups:
        for k in TOKEN_KEYS:
            if len({x[k] for x in v}) > 1:
                diff_fields[k] += 1
        if all((v[-1][k] or 0) >= max((x[k] or 0) for x in v) for k in TOKEN_KEYS):
            last_is_max += 1
    cross_file = sum(1 for v in dup_groups if len({x["_file"] for x in v}) > 1)
    same_model = sum(1 for v in dup_groups if len({x["model"] for x in v}) == 1)
    deduped = [v[-1] for v in groups.values()]  # 규칙: requestId 별 마지막 줄

    raw_tokens = tok_sum(all_recs)
    dd_tokens = tok_sum(deduped)

    # 모델 분포 (dedup 후)
    model_dist = collections.defaultdict(lambda: {"responses": 0, **{k: 0 for k in TOKEN_KEYS}})
    for r in deduped:
        m = model_dist[str(r["model"])]
        m["responses"] += 1
        for k in TOKEN_KEYS:
            m[k] += r[k] or 0
    for m in model_dist.values():
        m["total_tokens"] = sum(m[k] for k in TOKEN_KEYS)
        m["hit_rate"] = hit_rate(m)

    # 시간 분포 (UTC, dedup 후)
    stamps = [(parse_ts(r["timestamp"]), r) for r in deduped]
    bad_ts = sum(1 for s, _ in stamps if s is None)
    stamps = [(s, r) for s, r in stamps if s]
    hourly = collections.defaultdict(lambda: {"responses": 0, **{k: 0 for k in TOKEN_KEYS}})
    for s, r in stamps:
        h = hourly[s.strftime("%Y-%m-%dT%H:00Z")]
        h["responses"] += 1
        for k in TOKEN_KEYS:
            h[k] += r[k] or 0
    first = min(s for s, _ in stamps) if stamps else None
    last = max(s for s, _ in stamps) if stamps else None
    now = dt.datetime.now(dt.timezone.utc)
    today = [r for s, r in stamps if s.date() == now.date()]
    last5h = [r for s, r in stamps if s >= now - dt.timedelta(hours=5)]
    side = collections.Counter(("sidechain" if r["isSidechain"] else "main") for r in deduped)
    side_tokens = {k: tok_sum([r for r in deduped if bool(r["isSidechain"]) == (k == "sidechain")])
                   for k in ("main", "sidechain")}
    zero_out = sum(1 for r in deduped if (r["output_tokens"] or 0) == 0)

    mb = total_bytes / 1_000_000
    summary = {
        "generated_at_utc": now.isoformat(timespec="seconds"),
        "privacy": "집계값만 포함. 본문/ID 값 미포함.",
        "files": {"count": len(files),
                  "main": sum(1 for p in per_file if p["kind"] == "main"),
                  "subagent": sum(1 for p in per_file if p["kind"] == "subagent"),
                  "total_bytes": total_bytes, "per_file": per_file},
        "lines": dict(stats),
        "usage_records_raw": len(all_recs),
        "usage_line_share": round(len(all_recs) / stats["lines"], 4) if stats["lines"] else None,
        "substring_false_positive_share": round(stats["substring_but_no_usage"] / stats["substring_hit"], 4) if stats["substring_hit"] else None,
        "missing": missing,
        "distinct_sessions": len({r["sessionId"] for r in all_recs if r["sessionId"]}),
        "dedup": {
            "distinct_request_ids": len(groups),
            "group_size_hist": {str(k): v for k, v in sorted(sizes.items())},
            "dup_groups": len(dup_groups),
            "dup_lines_extra": len(all_recs) - len(groups),
            "dup_rate_lines": round((len(all_recs) - len(groups)) / len(all_recs), 4) if all_recs else None,
            "dup_groups_usage_identical": identical,
            "dup_groups_field_differs": dict(diff_fields),
            "dup_groups_last_is_max": last_is_max,
            "dup_groups_cross_file": cross_file,
            "dup_groups_same_model": same_model,
        },
        "tokens_raw_sum": raw_tokens,
        "tokens_dedup": dd_tokens,
        "overcount_if_no_dedup": {k: round(raw_tokens[k] / dd_tokens[k], 3) if dd_tokens[k] else None for k in TOKEN_KEYS},
        "cache_hit_rate": hit_rate(dd_tokens),
        "models": dict(model_dist),
        "sidechain": {"responses": dict(side), "tokens": side_tokens},
        "zero_output_responses": zero_out,
        "time": {"first_utc": first.isoformat() if first else None,
                 "last_utc": last.isoformat() if last else None,
                 "span_hours": round((last - first).total_seconds() / 3600, 3) if first else None,
                 "bad_timestamps": bad_ts,
                 "hourly_utc": dict(sorted(hourly.items()))},
        "q1": {"today_utc": {"date": now.date().isoformat(), "responses": len(today), **tok_sum(today)},
               "last_5h_rolling": {"responses": len(last5h), **tok_sum(last5h)}},
        "perf": {"parse_sec": round(parse_sec, 4), "mb": round(mb, 3),
                 "sec_per_mb": round(parse_sec / mb, 4) if mb else None},
    }
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("files", "lines", "usage_records_raw", "usage_line_share",
                                              "substring_false_positive_share", "missing", "distinct_sessions",
                                              "dedup", "tokens_raw_sum", "tokens_dedup", "overcount_if_no_dedup",
                                              "cache_hit_rate", "models", "sidechain", "zero_output_responses", "q1", "perf")},
                     ensure_ascii=False, indent=1, default=str))
    t = summary["time"]
    print("time:", t["first_utc"], t["last_utc"], t["span_hours"], "bad", t["bad_timestamps"])
    for h, v in t["hourly_utc"].items():
        print(" ", h, v["responses"], sum(v[k] for k in TOKEN_KEYS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
