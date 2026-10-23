"""루프 제어 CLI 테스트 도우미 (backend 소유, T-008).

- 저장소의 `aidlc/scripts/loop_control.py` 를 바이트코드 없이 import 한다.
- `SimEnv`: 벽시계·monotonic·sleep 을 하나의 가상 시계로 묶는다. `sleep(s)` 는 시간을 s 만큼 진행하고
  `on_tick` 콜백(예: tick 3 에서 POST resume)을 부른다 — 실제로 잠들지 않는다.
- CLI 를 workspace 루트에 대해 실행하는 `run_cli(root, *argv)` → (exit, stdout, stderr).
"""

from __future__ import annotations

import importlib.util
import io
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from types import ModuleType
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[4]
LOOP_CONTROL_PATH = REPO_ROOT / "aidlc" / "scripts" / "loop_control.py"
T0 = datetime.fromisoformat("2026-10-23T08:00:00+00:00")


def load_loop_control() -> ModuleType:
    name = "aidlc_loop_control_under_test"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, LOOP_CONTROL_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    saved = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = saved
    return module


lc = load_loop_control()


@dataclass
class SimClock:
    now_at: datetime = T0
    mono: float = 1000.0
    ticks: int = 0
    on_tick: Callable[[int], None] | None = None
    sleeps: list[float] = field(default_factory=list)

    def now(self) -> datetime:
        return self.now_at

    def monotonic(self) -> float:
        return self.mono

    def advance(self, seconds: float) -> None:
        self.now_at += timedelta(seconds=seconds)
        self.mono += seconds

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.advance(seconds)
        if seconds >= 1:  # 쓰기 재시도(0.05 s)는 tick 이 아니다
            self.ticks += 1
            if self.on_tick is not None:
                self.on_tick(self.ticks)


@dataclass
class CliResult:
    code: int
    out: str
    err: str

    @property
    def line(self) -> str:
        lines = self.out.splitlines()
        assert len(lines) == 1, lines  # stdout 은 한 줄뿐 (loop-cli §5)
        return lines[0]

    @property
    def result(self) -> str:
        return self.line.split()[2]

    @property
    def keys(self) -> dict[str, str]:
        return dict(tok.split("=", 1) for tok in self.line.split()[3:])


def run_cli(
    root: Path, *argv: str, clock: SimClock | None = None, **env_kwargs: Any
) -> CliResult:
    clock = clock or SimClock()
    out, err = io.StringIO(), io.StringIO()
    env = lc.Env(
        root=root,
        now=clock.now,
        monotonic=clock.monotonic,
        sleep=clock.sleep,
        out=out,
        err=err,
        **env_kwargs,
    )
    code = lc.main(list(argv), env)
    return CliResult(code, out.getvalue(), err.getvalue())
