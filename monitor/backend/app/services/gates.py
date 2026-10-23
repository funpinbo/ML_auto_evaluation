"""문서 Gate — `aidlc.py check <layer>` 서브프로세스 (ADR-009 §5, FR-001 §2.3).

- 실행: `[sys.executable, <root>/aidlc/scripts/aidlc.py, "check", layer]`, timeout 10 s, stdin DEVNULL.
- `status` 는 어떤 경로로도 실행하지 않는다 (D-07). 허용 서브커맨드는 `check` 하나다.
- 결과는 TTL 5 s 동안, 대상 디렉터리 서명(mtime·파일 수)이 같으면 재사용한다.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from app.models.envelope import SourceErrorCode

LAYERS = ("user", "project", "docs")
GATE_TIMEOUT_SEC = 10.0
GATE_TTL_SEC = 5.0
SCRIPT_RELPATH = Path("aidlc") / "scripts" / "aidlc.py"

# 20 §5 F9 출력 정규식
FILE_LINE_RE = re.compile(r"^(OK|TODO)\s+(\S+)\s+\((\d+)개 미작성\)", re.MULTILINE)
MISSING_RE = re.compile(r"^MISSING\s+(\S+)", re.MULTILINE)
GATE_LINE_RE = re.compile(
    r"^GATE (PASS|FAIL) — .*미작성 (\d+)개, 누락 문서 (\d+)개", re.MULTILINE
)
TARGET_MISSING_MARK = "가 없습니다"


@dataclass(frozen=True)
class RunOutput:
    returncode: int
    stdout: str


Runner = Callable[[list[str], Path, float], RunOutput]


def subprocess_runner(argv: list[str], cwd: Path, timeout: float) -> RunOutput:
    """기본 실행기. `subprocess.TimeoutExpired` 는 호출자가 처리한다."""
    if "check" not in argv[2:3]:  # 방어: check 외 서브커맨드 금지 (D-07)
        raise ValueError("only the 'check' subcommand is allowed")
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONDONTWRITEBYTECODE"] = (
        "1"  # 읽기 전용: 대상 저장소에 .pyc 를 남기지 않는다
    )
    proc = subprocess.run(
        argv,
        cwd=str(cwd),
        capture_output=True,
        stdin=subprocess.DEVNULL,
        timeout=timeout,
        env=env,
        check=False,
    )
    return RunOutput(proc.returncode, proc.stdout.decode("utf-8", errors="replace"))


@dataclass(frozen=True)
class GateOutcome:
    layer: str
    result: str  # PASS | FAIL | UNKNOWN
    unwritten: int | None
    missing: int | None
    target_missing: bool
    no_documents: bool
    error_code: SourceErrorCode | None
    checked_at: str | None
    file_unwritten: dict[str, int] = field(default_factory=dict)


def parse_output(layer: str, out: RunOutput, checked_at: str) -> GateOutcome:
    """aidlc.py check 출력 → GateOutcome. PASS/FAIL 은 exit code 기준 (FR-001 §2.3)."""
    files = {m.group(2): int(m.group(3)) for m in FILE_LINE_RE.finditer(out.stdout)}
    gate = GATE_LINE_RE.search(out.stdout)
    result = "PASS" if out.returncode == 0 else "FAIL"
    if gate is None:
        if out.returncode != 0 and TARGET_MISSING_MARK in out.stdout:
            return GateOutcome(layer, "FAIL", None, None, True, False, None, checked_at)
        # 출력을 해석할 수 없음 (예: 스크립트가 깨진 파일에서 예외로 종료)
        return GateOutcome(
            layer,
            "UNKNOWN",
            None,
            None,
            False,
            False,
            SourceErrorCode.SOURCE_PARSE_ERROR,
            checked_at,
        )
    return GateOutcome(
        layer=layer,
        result=result,
        unwritten=int(gate.group(2)),
        missing=int(gate.group(3)),
        target_missing=False,
        no_documents=result == "PASS" and not files,
        error_code=None,
        checked_at=checked_at,
        file_unwritten=files,
    )


def _target_dir(root: Path, layer: str) -> Path:
    return root / "docs" if layer == "docs" else root / "workspace" / layer


def target_signature(root: Path, layer: str) -> tuple[object, ...]:
    """대상 디렉터리와 그 아래 `.md` 의 (개수, 최대 mtime). 캐시 무효화용."""
    target = _target_dir(root, layer)
    try:
        dir_mtime = target.stat().st_mtime_ns
    except OSError:
        return ("missing",)
    pattern = "**/*.md" if layer == "docs" else "*.md"
    count, latest = 0, 0
    try:
        for p in target.glob(pattern):
            try:
                latest = max(latest, p.stat().st_mtime_ns)
                count += 1
            except OSError:
                continue
    except OSError:
        return ("unreadable",)
    return (dir_mtime, count, latest)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


class GateService:
    """layer 별 Gate 결과 + TTL 캐시. 스레드 안전."""

    def __init__(
        self,
        *,
        runner: Runner = subprocess_runner,
        clock: Callable[[], float] = time.monotonic,
        ttl: float = GATE_TTL_SEC,
        timeout: float = GATE_TIMEOUT_SEC,
    ) -> None:
        self._runner = runner
        self._clock = clock
        self._ttl = ttl
        self._timeout = timeout
        self._lock = threading.Lock()
        self._cache: dict[
            tuple[Path, str], tuple[float, tuple[object, ...], GateOutcome]
        ] = {}

    def check(self, root: Path, layer: str) -> GateOutcome:
        if layer not in LAYERS:
            raise ValueError("unknown gate layer")
        key = (root, layer)
        signature = target_signature(root, layer)
        now = self._clock()
        with self._lock:
            cached = self._cache.get(key)
            if cached and now - cached[0] < self._ttl and cached[1] == signature:
                return cached[2]
        outcome = self._run(root, layer)
        with self._lock:
            self._cache[key] = (now, signature, outcome)
        return outcome

    def _run(self, root: Path, layer: str) -> GateOutcome:
        checked_at = _now_iso()
        script = root / SCRIPT_RELPATH
        if not script.is_file():
            return GateOutcome(
                layer, "UNKNOWN", None, None, False, False,
                SourceErrorCode.SOURCE_MISSING, checked_at,
            )  # fmt: skip
        argv = [sys.executable, str(script), "check", layer]
        try:
            out = self._runner(argv, root, self._timeout)
        except subprocess.TimeoutExpired:
            return GateOutcome(
                layer, "UNKNOWN", None, None, False, False,
                SourceErrorCode.GATE_TIMEOUT, checked_at,
            )  # fmt: skip
        except (OSError, ValueError):
            return GateOutcome(
                layer, "UNKNOWN", None, None, False, False,
                SourceErrorCode.SOURCE_UNREADABLE, checked_at,
            )  # fmt: skip
        return parse_output(layer, out, checked_at)
