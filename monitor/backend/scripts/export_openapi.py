"""FastAPI 명세를 `workspace/project/contracts/openapi.json` 으로 내보낸다 (ADR-011 §7, 20 §5 F10).

  python monitor/backend/scripts/export_openapi.py [--check]

손편집 금지. 명세가 바뀌면 같은 Task 안에서
`python3 aidlc/scripts/openapi_docs.py render workspace/project/contracts/openapi.json -o docs/api`
로 레퍼런스를 다시 만든다. `--check` 는 파일이 최신이 아니면 exit 1 (쓰지 않음).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parents[1]
OUT = REPO / "workspace" / "project" / "contracts" / "openapi.json"

if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.config import DEFAULT_PORT, Settings
from app.main import create_app


def render() -> str:
    settings = Settings(
        port=DEFAULT_PORT,
        aidlc_root=REPO,
        claude_home=REPO / ".unused-claude-home",
        dist_dir=REPO / "monitor" / "frontend" / "dist",
    )
    spec = create_app(settings).openapi()
    spec["servers"] = [
        {"url": f"http://127.0.0.1:{DEFAULT_PORT}", "description": "로컬 기본 포트"}
    ]
    return json.dumps(spec, ensure_ascii=False, indent=2, sort_keys=False) + "\n"


def main(argv: list[str]) -> int:
    text = render()
    if "--check" in argv:
        current = OUT.read_text(encoding="utf-8") if OUT.is_file() else ""
        if current != text:
            print("openapi.json 이 코드와 다릅니다. export_openapi.py 를 실행하세요.")
            return 1
        print("openapi.json 최신")
        return 0
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
