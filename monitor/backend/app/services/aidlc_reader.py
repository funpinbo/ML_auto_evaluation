"""AI-DLC 상태 리더 — Hook 읽기 함수 어댑터 (ADR-009).

`<AIDLC_ROOT>/aidlc/hooks/memory_cascade.py` 를 importlib 로 로드하고 **허용 목록**만 쓴다:
`read_doc`, `as_int`, `FM_RE`, `PHASE_RE`, `CHECKBOX_RE`, `ARCHIVE_RE`,
`Memory(root).exists/phases/archived/latest_seq/pending/load_state`.
Hook 의 쓰기 함수는 이 모듈에서 참조하지 않는다. `aidlc.py status` 는 어떤 경로로도 실행하지 않는다
(closed STM 을 아카이브하는 부작용, D-07).
"""

from __future__ import annotations

import hashlib
import importlib.machinery
import importlib.util
import logging
import re
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

from app.models.envelope import SourceErrorCode

log = logging.getLogger("aidlc_monitor.reader")

HOOK_RELPATH = Path("aidlc") / "hooks" / "memory_cascade.py"
ALLOWED_ATTRS = (
    "read_doc",
    "as_int",
    "FM_RE",
    "PHASE_RE",
    "CHECKBOX_RE",
    "ARCHIVE_RE",
    "Memory",
)
ALLOWED_MEMORY_METHODS = (
    "exists",
    "phases",
    "archived",
    "latest_seq",
    "pending",
    "load_state",
)


class SourceProblem(Exception):
    """패널 단위 소스 문제. HTTP 오류가 아니라 `meta.status`/`meta.error` 로 바뀐다 (NFR-002)."""

    def __init__(self, code: SourceErrorCode) -> None:
        super().__init__(code.value)
        self.code = code


class EngineUnavailable(Exception):
    """Hook 모듈을 찾지 못했거나 로드하지 못함 ("AI-DLC 엔진을 찾을 수 없음")."""


def _classify(exc: BaseException) -> SourceErrorCode:
    if isinstance(exc, (UnicodeDecodeError, ValueError)):
        return SourceErrorCode.SOURCE_PARSE_ERROR
    return SourceErrorCode.SOURCE_UNREADABLE


@dataclass(frozen=True)
class Doc:
    meta: dict[str, Any]
    body: str


class MemoryView:
    """`Memory(root)` 의 허용 메서드만 노출한다. 예외는 SourceProblem 으로 바꾼다."""

    def __init__(self, memory: Any) -> None:
        self._memory = memory

    def _call(self, name: str) -> Any:
        try:
            return getattr(self._memory, name)()
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            raise SourceProblem(_classify(exc)) from None

    def exists(self) -> bool:
        return bool(self._call("exists"))

    def phases(self) -> dict[str, tuple[int, int]]:
        return dict(self._call("phases"))

    def archived_count(self) -> int:
        return len(self._call("archived"))

    def latest_seq(self) -> int:
        return int(self._call("latest_seq"))

    def pending_level(self) -> str | None:
        """미처리 cascade 의 level 만. Hook 메시지 문자열은 내보내지 않는다 (ADR-009 §1)."""
        step = self._call("pending")
        return None if step is None else str(step.level)

    def load_state(self) -> dict[str, Any]:
        state = self._call("load_state")
        return state if isinstance(state, dict) else {}


class HookEngine:
    """로드된 Hook 모듈에 대한 읽기 전용 어댑터."""

    def __init__(self, module: ModuleType) -> None:
        missing = [name for name in ALLOWED_ATTRS if not hasattr(module, name)]
        if missing:
            raise EngineUnavailable("hook module lacks required attributes")
        self._module = module

    @property
    def module(self) -> ModuleType:
        return self._module

    @property
    def phase_re(self) -> re.Pattern[str]:
        return self._module.PHASE_RE

    @property
    def checkbox_re(self) -> re.Pattern[str]:
        return self._module.CHECKBOX_RE

    def as_int(self, value: Any, default: int = 0) -> int:
        return int(self._module.as_int(value, default))

    def read_doc(self, path: Path) -> Doc:
        """Hook `read_doc` 그대로. 없는 파일 = 빈 문서(Hook 과 같음).

        UTF-8 아님 → SOURCE_PARSE_ERROR, 읽기 실패 → SOURCE_UNREADABLE,
        `---` 로 시작하지만 frontmatter 가 닫히지 않음 → SOURCE_PARSE_ERROR (R6).
        """
        try:
            meta, body = self._module.read_doc(path)
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            raise SourceProblem(_classify(exc)) from None
        if not meta and body.startswith("---"):
            raise SourceProblem(SourceErrorCode.SOURCE_PARSE_ERROR)
        return Doc(dict(meta), body)

    def memory(self, root: Path) -> MemoryView:
        return MemoryView(self._module.Memory(root))


class HookLoader:
    """경로·mtime 별로 Hook 모듈을 한 번만 로드한다 (스레드 안전)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cache: dict[Path, tuple[int, HookEngine]] = {}

    def load(self, root: Path) -> HookEngine:
        path = root / HOOK_RELPATH
        try:
            mtime = path.stat().st_mtime_ns
        except OSError:
            raise EngineUnavailable("hook module not found") from None
        with self._lock:
            cached = self._cache.get(path)
            if cached and cached[0] == mtime:
                return cached[1]
            engine = HookEngine(_import_module(path))
            self._cache[path] = (mtime, engine)
            return engine


class _NoBytecodeLoader(importlib.machinery.SourceFileLoader):
    """`__pycache__/*.pyc` 를 쓰지 않는 로더 — 대시보드의 쓰기 대상은 `.control.json` 하나뿐이다 (W-01)."""

    def set_data(self, path: str, data: bytes, *, _mode: int = 0o666) -> None:
        return None


def _import_module(path: Path) -> ModuleType:
    digest = hashlib.sha256(str(path).encode()).hexdigest()[:16]
    name = f"_aidlc_monitor_hook_{digest}"
    spec = importlib.util.spec_from_file_location(
        name, path, loader=_NoBytecodeLoader(name, str(path))
    )
    if spec is None or spec.loader is None:
        raise EngineUnavailable("cannot build module spec")
    module = importlib.util.module_from_spec(spec)
    # dataclass 처리에 sys.modules 등록이 필요하다. 모듈 import 자체는 부작용이 없다 (ADR-009 Context).
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # noqa: BLE001 — 엔진 로드 실패는 패널 오류로 처리
        sys.modules.pop(name, None)
        log.warning("AI-DLC 엔진 로드 실패: %s", type(exc).__name__)
        raise EngineUnavailable("hook module failed to load") from None
    return module
