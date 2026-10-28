#!/usr/bin/env python3
"""NFR-001 검증용 합성 JSONL 벤치마크 — 표준 라이브러리만.

실제 기록에서는 줄 길이와 범주(usage 문자열 없음 / 문자열은 있으나 usage 없음 / usage 있음)
라는 메타데이터만 수집하고, 본문은 전혀 복사하지 않는다. 그 분포를 따라 가짜 내용으로
대용량 파일을 만들어 profile_usage 의 동일 파서로 콜드 파싱·증분 파싱 시간을 잰다.

사용법: python3 bench_synthetic.py <real_projects_dir> <work_dir> [target_mb ...]
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from profile_usage import extract, scan_file  # noqa: E402


def line_profile(root: Path) -> list[tuple[int, str]]:
    prof = []
    for f in sorted(root.rglob("*.jsonl")):
        with f.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                n = len(line.encode("utf-8"))
                if "usage" not in line:
                    prof.append((n, "skip"))
                else:
                    r = extract(line)
                    prof.append((n, "usage" if r and not r.get("_bad_json") else "fp"))
    return prof


def fake_line(n: int, cat: str, i: int) -> str:
    base = {"type": "assistant" if cat == "usage" else "user", "timestamp": "2026-10-%02dT%02d:%02d:00.000Z" % (1 + i % 28, i % 24, i % 60),
            "requestId": "req_%08d" % (i // 3), "sessionId": "s-%d" % (i // 5000), "isSidechain": False}
    if cat == "usage":
        base["message"] = {"model": "claude-fake", "content": [{"type": "text", "text": ""}],
                           "usage": {"input_tokens": 3, "output_tokens": 200, "cache_creation_input_tokens": 1000, "cache_read_input_tokens": 50000}}
    else:
        base["message"] = {"role": "user", "content": [{"type": "text", "text": ""}]}
        if cat == "fp":
            base["toolUseResult"] = {"note": "usage"}
    head = json.dumps(base)
    pad = max(0, n - len(head) - 1)
    base["message"]["content"][0]["text"] = "x" * pad
    return json.dumps(base) + "\n"


def build(prof, path: Path, target_bytes: int) -> int:
    written, i = 0, 0
    with path.open("w", encoding="utf-8") as fh:
        while written < target_bytes:
            n, cat = prof[i % len(prof)]
            s = fake_line(n, cat, i)
            fh.write(s)
            written += len(s)
            i += 1
    return i


def timed_scan(path: Path) -> tuple[float, int]:
    st = Counter()
    t = time.perf_counter()
    recs = scan_file(path, st)
    groups = {}
    for r in recs:  # dedup 포함
        groups[r["requestId"]] = r
    return time.perf_counter() - t, len(groups)


def incremental(path: Path, offset: int) -> float:
    """append-only 가정: 마지막 offset 이후 바이트만 읽는다."""
    t = time.perf_counter()
    with path.open("rb") as fh:
        fh.seek(offset)
        for raw in fh:
            line = raw.decode("utf-8", "replace")
            if "usage" in line:
                extract(line)
    return time.perf_counter() - t


def main() -> int:
    real, work = Path(sys.argv[1]), Path(sys.argv[2])
    targets = [float(x) for x in sys.argv[3:]] or [50, 200]
    work.mkdir(parents=True, exist_ok=True)
    prof = line_profile(real)
    cats = Counter(c for _, c in prof)
    bytes_by = Counter()
    for n, c in prof:
        bytes_by[c] += n
    total = sum(bytes_by.values())
    result = {"profile_lines": len(prof), "category_lines": dict(cats),
              "category_byte_share": {k: round(v / total, 4) for k, v in bytes_by.items()},
              "avg_line_bytes": {k: round(bytes_by[k] / cats[k]) for k in cats},
              "max_line_bytes": max(n for n, _ in prof), "runs": []}
    for mb in targets:
        p = work / f"synthetic_{int(mb)}mb.jsonl"
        lines = build(prof, p, int(mb * 1_000_000))
        size = p.stat().st_size
        runs = [timed_scan(p) for _ in range(3)]
        best = min(r[0] for r in runs)
        # 1MB 추가분 증분 파싱
        with p.open("a", encoding="utf-8") as fh:
            add, j = 0, lines
            while add < 1_000_000:
                n, c = prof[j % len(prof)]
                s = fake_line(n, c, j)
                fh.write(s)
                add += len(s)
                j += 1
        inc = incremental(p, size)
        result["runs"].append({"target_mb": mb, "bytes": size, "lines": lines, "cold_parse_best_sec": round(best, 3),
                               "cold_parse_all_sec": [round(r[0], 3) for r in runs],
                               "sec_per_mb": round(best / (size / 1e6), 4), "responses_after_dedup": runs[0][1],
                               "incremental_1mb_sec": round(inc, 4)})
        p.unlink()
    out = Path(__file__).with_name("summary_bench.json")
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
