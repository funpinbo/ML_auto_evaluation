#!/usr/bin/env bash
# Hook 런처: OS 마다 다른 Python 명령(python3 / python / py)을 찾아 memory_cascade.py 를 실행한다.
# Windows 의 python3 는 Microsoft Store 안내용 가짜 실행 파일일 수 있으므로 실제로 실행해 보고 고른다.
# Python 을 못 찾으면 세션을 막지 않도록 조용히 exit 0.
script="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/memory_cascade.py"
for py in python3 python py; do
  if command -v "$py" >/dev/null 2>&1 && "$py" -c 'import sys; sys.exit(sys.version_info < (3, 10))' >/dev/null 2>&1; then
    exec "$py" "$script" "$@"
  fi
done
echo "[aidlc] Python 3.10+ 를 찾지 못해 Hook 을 건너뜁니다 (python3/python/py)." >&2
exit 0
