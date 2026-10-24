"""기록·스냅샷 파일을 여는 단일 지점 (privacy.md §4 P-29, I-10, security 리뷰 조치).

JSONL(수집기·해석기 폴백)과 상태 스냅샷은 모두 이 함수로만 연다:
1. `lstat` — 정규 파일, symlink 아님, `st_nlink == 1`(하드 링크는 `resolve()` 로 이탈을 판정할 수 없어 거부)
2. `os.open(O_RDONLY | O_NOFOLLOW | O_NONBLOCK)` — 검사와 열기 사이에 symlink·FIFO 로 바뀌어도 멈추거나 따라가지 않음
3. `fstat` — 정규 파일, `(st_dev, st_ino)` 가 1의 결과와 같고 `st_nlink == 1`. 아니면 닫고 거부

거부는 None. 호출자는 고정 문구 WARN 의 건수로만 남긴다(경로·이름 없음).
"""

from __future__ import annotations

import os
import stat

OPEN_FLAGS = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)


def _acceptable(st: os.stat_result) -> bool:
    return stat.S_ISREG(st.st_mode) and st.st_nlink == 1


def open_regular(
    path: str | os.PathLike[str], expect: os.stat_result | None = None
) -> tuple[int, os.stat_result] | None:
    """검사를 모두 통과하면 `(fd, fstat 결과)`. `expect` 가 있으면 그 파일(dev, ino)과 같아야 한다."""
    try:
        before = os.lstat(path)
    except (OSError, ValueError):
        return None
    if not _acceptable(before):
        return None
    if expect is not None and (expect.st_dev, expect.st_ino) != (
        before.st_dev,
        before.st_ino,
    ):
        return None
    try:
        fd = os.open(path, OPEN_FLAGS)
    except (OSError, ValueError):
        return None
    try:
        after = os.fstat(fd)
    except OSError:
        os.close(fd)
        return None
    if not _acceptable(after) or (after.st_dev, after.st_ino) != (
        before.st_dev,
        before.st_ino,
    ):
        os.close(fd)
        return None
    return fd, after
