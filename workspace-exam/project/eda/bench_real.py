#!/usr/bin/env python3
"""실제 DS-03 기록에 대한 반복 파싱 시간 측정 (집계값만 출력)."""
import sys, time, json
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from profile_usage import scan_file

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / ".claude/projects/-home-user-chatbot"
files = sorted(root.rglob("*.jsonl"))
size = sum(f.stat().st_size for f in files)
times = []
for _ in range(7):
    st = Counter(); t = time.perf_counter()
    for f in files:
        scan_file(f, st)
    times.append(time.perf_counter() - t)
# 단계 분해: 원문 읽기 + 부분 문자열 검사만
t = time.perf_counter()
for f in files:
    with f.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            "usage" in line
read_only = time.perf_counter() - t
res = {"mb": round(size/1e6, 3), "runs_sec": [round(x, 4) for x in times], "best_sec": round(min(times), 4),
       "median_sec": round(sorted(times)[3], 4), "sec_per_mb_median": round(sorted(times)[3]/(size/1e6), 4),
       "read_and_filter_only_sec": round(read_only, 4)}
Path(__file__).with_name("summary_bench_real.json").write_text(json.dumps(res, indent=2))
print(json.dumps(res))
