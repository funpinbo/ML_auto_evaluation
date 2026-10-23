"""`python -m app [--port N]` — 127.0.0.1 고정 바인딩으로 서버를 띄운다 (ADR-001, N-01).

호스트를 바꾸는 옵션은 없다. `--port` 가 `AIDLC_MONITOR_PORT` 보다 우선하며, 같은 값이
uvicorn 바인딩과 Host·Origin 가드에 쓰인다 (D-19).
"""

from __future__ import annotations

import argparse

import uvicorn

from app.config import BIND_HOST, Settings, parse_port
from app.main import create_app, setup_logging


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app")
    parser.add_argument("--port", type=parse_port, default=None)
    args = parser.parse_args(argv)
    settings = Settings.from_env(port=args.port)
    setup_logging()
    uvicorn.run(
        create_app(settings),
        host=BIND_HOST,
        port=settings.port,
        access_log=False,
        log_config=None,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
