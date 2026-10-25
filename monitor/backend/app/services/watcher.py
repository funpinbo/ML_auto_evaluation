"""변경 감지 (ADR-008, contracts/sse-events.md §3).

1초 tick 마다 topic 별 서명(stat 값 묶음)을 만들어 직전과 비교한다. 파일 내용은 읽지 않는다.
- `control` 은 파일 stat 에 화면 판정(view·버튼 상태)을 더한다 → heartbeat 120 s 경계도 잡힌다.
- `usage` 는 스냅샷 stat + `collector.refresh()` 뒤의 최근 활동 시각.
서명에 경로·내용을 담지만 밖으로 내보내지 않는다 — 결과는 topic 이름 집합뿐이다.
"""

from __future__ import annotations

import os
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

M1_TOPICS = ("memory", "tasks", "control", "usage", "plan", "pipeline")


def _stat(path: Path) -> tuple[int, int] | None:
    try:
        st = os.stat(path)
    except (OSError, ValueError):
        return None
    return (st.st_mtime_ns, st.st_size)


def _dir_stat(path: Path) -> tuple[Any, ...]:
    """디렉터리 자체 + 바로 아래 항목의 stat (재귀 없음)."""
    head = _stat(path)
    if head is None:
        return ()
    try:
        names = sorted(os.listdir(path))
    except OSError:
        return (head,)
    return (head, *((n, _stat(path / n)) for n in names))


class Watcher:
    """topic 서명 비교기. 여러 SSE 연결이 같은 인스턴스를 공유한다 (tick 은 한 번만 계산)."""

    def __init__(
        self,
        root: Path,
        *,
        control_view: Callable[[], Any] = lambda: None,
        usage_activity: Callable[[], Any] = lambda: None,
    ) -> None:
        mem = root / "workspace" / "memory"
        self._files: dict[str, list[Path]] = {
            "memory": [
                mem / "short-term.md",
                mem / "long-term.md",
                mem / ".cascade-state.json",
            ],
            "tasks": [mem / "tasks.md"],
            "plan": [mem / "plan.md", mem / "tasks.md"],
            "control": [mem / ".control.json", mem / ".monitor" / "loop-status.json"],
            "usage": [mem / ".monitor" / "claude-status.json"],
            "pipeline": [mem / "plan.md", mem / "tasks.md"],
        }
        self._dirs: dict[str, list[Path]] = {
            "memory": [mem / "archive"],
            "pipeline": [root / "workspace" / d for d in ("user", "project", "teams")],
        }
        self._extra: dict[str, Callable[[], Any]] = {
            "control": control_view,
            "usage": usage_activity,
        }
        self._last: dict[str, Any] | None = None
        self._lock = threading.Lock()

    def signature(self, topic: str) -> Any:
        parts: list[Any] = [_stat(p) for p in self._files.get(topic, [])]
        parts += [_dir_stat(d) for d in self._dirs.get(topic, [])]
        extra = self._extra.get(topic)
        if extra is not None:
            try:
                parts.append(extra())
            except Exception:  # noqa: BLE001 — 감지 실패는 "변경 없음"
                parts.append(None)
        return tuple(parts)

    def poll(self) -> list[str]:
        """직전 poll 이후 바뀐 topic. 첫 호출은 기준선만 잡고 빈 목록."""
        with self._lock:
            now = {t: self.signature(t) for t in M1_TOPICS}
            prev, self._last = self._last, now
        if prev is None:
            return []
        return [t for t in M1_TOPICS if prev.get(t) != now[t]]
