#!/usr/bin/env bash
# status line 런처 (ADR-003 Decision 2): run.sh 와 같은 방식으로 python3 / python / py 를 실제 실행해 보고
# statusline.py 를 실행한다. stdin(Claude Code statusLine JSON)은 그대로 넘긴다.
# Python 을 못 찾으면 세션 표시를 깨지 않도록 빈 줄을 출력하고 exit 0.
script="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/statusline.py"
for py in python3 python py; do
  if command -v "$py" >/dev/null 2>&1 && "$py" -c 'import sys; sys.exit(sys.version_info < (3, 10))' </dev/null >/dev/null 2>&1; then
    exec "$py" "$script"
  fi
done
echo ""
exit 0
