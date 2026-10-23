"""서버 설정 (D-16, D-19).

- `port` 는 uvicorn 바인딩·Host 가드·Origin 가드가 함께 쓰는 단일 출처다(D-19). 0 은 허용하지 않는다.
- 경로(`aidlc_root`, `claude_home`)는 환경 변수 `AIDLC_ROOT`·`CLAUDE_HOME` 으로만 주입한다(D-16).
  요청에서 경로를 받지 않는다(02 §8).
- 바인딩 주소는 `127.0.0.1` 상수다. 바꾸는 옵션·환경 변수가 없다(N-01).
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

BIND_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
PORT_ENV = "AIDLC_MONITOR_PORT"
ROOT_ENV = "AIDLC_ROOT"
CLAUDE_HOME_ENV = "CLAUDE_HOME"

# monitor/backend/app/config.py → parents[3] = 저장소 루트
_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


def validate_port(value: int) -> int:
    """1~65535 정수만 허용. 0(임의 할당)은 가드가 실제 포트를 알 수 없어 거부한다."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("port must be an integer")
    if not 1 <= value <= 65535:
        raise ValueError("port must be between 1 and 65535")
    return value


def parse_port(raw: str) -> int:
    text = raw.strip()
    if not text.isdigit() or (len(text) > 1 and text.startswith("0")):
        raise ValueError("port must be a decimal integer without leading zeros")
    return validate_port(int(text))


@dataclass(frozen=True)
class Settings:
    port: int
    aidlc_root: Path
    claude_home: Path
    dist_dir: Path

    def __post_init__(self) -> None:
        validate_port(self.port)

    @classmethod
    def from_env(
        cls, env: Mapping[str, str] | None = None, *, port: int | None = None
    ) -> Settings:
        """환경 변수에서 설정을 만든다. `port` 인자(런처의 `--port`)가 환경 변수보다 우선한다."""
        env = os.environ if env is None else env
        if port is None:
            raw = env.get(PORT_ENV)
            port = parse_port(raw) if raw else DEFAULT_PORT
        root_raw = env.get(ROOT_ENV)
        aidlc_root = Path(root_raw) if root_raw else _REPO_ROOT
        home_raw = env.get(CLAUDE_HOME_ENV)
        claude_home = Path(home_raw) if home_raw else Path.home() / ".claude"
        return cls(
            port=validate_port(port),
            aidlc_root=aidlc_root,
            claude_home=claude_home,
            dist_dir=_DEFAULT_DIST,
        )

    @property
    def allowed_hosts(self) -> frozenset[str]:
        return frozenset({f"127.0.0.1:{self.port}", f"localhost:{self.port}"})

    @property
    def allowed_origins(self) -> frozenset[str]:
        return frozenset(
            {f"http://127.0.0.1:{self.port}", f"http://localhost:{self.port}"}
        )
