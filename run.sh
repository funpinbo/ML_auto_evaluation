#!/usr/bin/env bash
# AI-DLC Monitor 원클릭 실행 (macOS/Linux, SCOPE-01). 실제 작업은 run.py 가 한다.
#   ./run.sh [--port N] [--no-browser]
# python3 → python → py 를 실제로 실행해 3.11+ 인지 확인한다(aidlc/hooks/run.sh 와 같은 방식,
# Windows Git Bash 의 Microsoft Store 가짜 python3 도 여기서 걸러진다).
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
for py in python3 python py; do
  if command -v "$py" >/dev/null 2>&1 && "$py" -c 'import sys; sys.exit(sys.version_info < (3, 11))' >/dev/null 2>&1; then
    exec "$py" "$here/run.py" "$@"
  fi
done
echo "[monitor] Python 3.11 이상이 필요합니다 (python3 / python / py 에서 찾지 못함)." >&2
echo "[monitor] https://www.python.org/downloads/ 에서 Python 3.11 이상을 설치한 뒤 다시 실행하세요." >&2
exit 1
