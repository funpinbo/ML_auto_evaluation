"""backend 단위 테스트 설정 — `app` 패키지와 공용 도우미를 import 경로에 넣는다."""

from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
for _p in (_HERE, _HERE.parents[1]):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
