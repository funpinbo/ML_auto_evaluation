"""패널 결과 누적기 — 소스 문제를 `meta` 로 모은다 (NFR-002, ADR-011 §1).

경고 문구는 고정 문자열이며 파일 내용·절대 경로를 담지 않는다 (ADR-011 §8).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.models.envelope import Meta, SourceError, SourceErrorCode

SOURCE_MESSAGES: dict[SourceErrorCode, str] = {
    SourceErrorCode.SOURCE_MISSING: "소스 파일이 없습니다.",
    SourceErrorCode.SOURCE_PARSE_ERROR: "소스 파일 형식을 읽을 수 없습니다.",
    SourceErrorCode.SOURCE_UNREADABLE: "소스 파일을 읽을 수 없습니다.",
    SourceErrorCode.GATE_TIMEOUT: "Gate 검사가 시간 안에 끝나지 않았습니다.",
    SourceErrorCode.PROJECT_DIR_NOT_FOUND: "프로젝트 기록 폴더를 찾을 수 없습니다.",
    SourceErrorCode.SNAPSHOT_STALE: "스냅샷이 오래되었습니다.",
}


def iso_utc(ts: datetime) -> str:
    return ts.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


@dataclass
class Panel:
    status: str = "ok"
    warnings: list[str] = field(default_factory=list)
    error: SourceError | None = None
    data: Any = None
    _mtime: float | None = None

    def warn(self, message: str) -> None:
        if message not in self.warnings:
            self.warnings.append(message)

    def fail(self, code: SourceErrorCode, message: str | None = None) -> None:
        self.status = "error"
        self.error = SourceError(code=code, message=message or SOURCE_MESSAGES[code])

    def empty(self, message: str) -> None:
        self.status = "empty"
        self.warn(message)

    def touch(self, *paths: Path) -> None:
        """읽은 파일의 mtime 을 source_mtime 후보로 기록한다."""
        for path in paths:
            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue
            if self._mtime is None or mtime > self._mtime:
                self._mtime = mtime

    def meta(self, now: datetime) -> Meta:
        status = self.status
        if status == "ok" and self.warnings:
            status = "partial"
        source = (
            None
            if self._mtime is None
            else iso_utc(datetime.fromtimestamp(self._mtime, UTC))
        )
        return Meta(
            status=status,  # type: ignore[arg-type]
            warnings=list(self.warnings),
            error=self.error,
            generated_at=iso_utc(now),
            source_mtime=source,
        )
