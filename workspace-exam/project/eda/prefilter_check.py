#!/usr/bin/env python3
"""사전 필터 후보별 선택도 비교 (개수만 출력, 본문 미출력)."""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from profile_usage import extract
root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / ".claude/projects/-home-user-chatbot"
cands = ['usage', '"usage":', '"usage":{"input_tokens"', '"type":"assistant"']
res = {c: {"hit": 0, "hit_with_usage": 0} for c in cands}
total_usage = 0
for f in sorted(root.rglob("*.jsonl")):
    for line in f.open(encoding="utf-8", errors="replace"):
        has = False
        if "usage" in line:
            r = extract(line)
            has = bool(r) and not r.get("_bad_json")
        total_usage += has
        for c in cands:
            if c in line:
                res[c]["hit"] += 1
                res[c]["hit_with_usage"] += has
out = {"usage_records": total_usage, "candidates": res}
Path(__file__).with_name("summary_prefilter.json").write_text(json.dumps(out, indent=2))
print(json.dumps(out))
