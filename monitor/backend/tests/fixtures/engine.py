"""workspace 에 AI-DLC 엔진(Hook·CLI)을 복사하고 `app` 을 import 할 수 있게 하는 도우미 (qa, T-013).

앱은 ADR-009 대로 `<AIDLC_ROOT>/aidlc/...` 만 본다. 루프 CLI(`loop_control.py`)는 자기 위치로
저장소 루트를 계산하므로, E2E 는 복사본을 workspace 안에서 실행해야 실제 저장소를 건드리지 않는다.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_DIR.parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

ENGINE_FILES = (
    Path("aidlc") / "hooks" / "memory_cascade.py",
    Path("aidlc") / "scripts" / "aidlc.py",
    Path("aidlc") / "scripts" / "loop_control.py",
)
TEMPLATE_DIRS = ("user", "project", "memory")


def install_engine(root: Path) -> Path:
    """Hook·CLI·템플릿을 `root` 에 복사한다. 이미 있는 파일은 덮어쓰지 않는다. CLI 경로를 돌려준다."""
    for rel in ENGINE_FILES:
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists():
            shutil.copy2(REPO_ROOT / rel, dest)
    for name in TEMPLATE_DIRS:
        dest_dir = root / "aidlc" / "templates" / name
        dest_dir.mkdir(parents=True, exist_ok=True)
        for src in (REPO_ROOT / "aidlc" / "templates" / name).glob("*.md"):
            if not (dest_dir / src.name).exists():
                shutil.copy2(src, dest_dir / src.name)
    return root / "aidlc" / "scripts" / "aidlc.py"
