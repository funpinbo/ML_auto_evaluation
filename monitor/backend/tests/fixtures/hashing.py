"""디렉터리 트리 해시·비교 (CON-03 / QS-07 / T-04).

조회 전후에 workspace 전체가 바뀌지 않았는지, 새로 생긴 파일이 무엇인지 확인한다.
파일 내용뿐 아니라 심볼릭 링크 대상과 빈 디렉터리도 포함한다.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from pathlib import Path


def tree_manifest(root: Path, *, exclude: tuple[str, ...] = ()) -> dict[str, str]:
    """`상대경로 -> 지문` 을 돌려준다. exclude 는 제외할 상대경로 접두사(예: `.pytest_cache`)."""
    manifest: dict[str, str] = {}
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames.sort()
        base = Path(dirpath)
        for name in [*dirnames, *sorted(filenames)]:
            path = base / name
            rel = path.relative_to(root).as_posix()
            if any(rel == ex or rel.startswith(ex.rstrip("/") + "/") for ex in exclude):
                continue
            if path.is_symlink():
                manifest[rel] = "link:" + os.readlink(path)
            elif path.is_dir():
                manifest[rel] = "dir"
            else:
                manifest[rel] = "file:" + hashlib.sha256(path.read_bytes()).hexdigest()
    return manifest


def hash_tree(root: Path, *, exclude: tuple[str, ...] = ()) -> str:
    """트리 전체의 단일 sha256. 내용·이름·링크 대상 중 무엇이 바뀌어도 값이 달라진다."""
    digest = hashlib.sha256()
    for rel, fingerprint in sorted(tree_manifest(root, exclude=exclude).items()):
        digest.update(f"{rel}\0{fingerprint}\n".encode())
    return digest.hexdigest()


@dataclass(frozen=True)
class TreeDiff:
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    changed: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return bool(self.added or self.removed or self.changed)


def diff_manifests(before: dict[str, str], after: dict[str, str]) -> TreeDiff:
    """두 `tree_manifest` 결과의 차이."""
    return TreeDiff(
        added=sorted(set(after) - set(before)),
        removed=sorted(set(before) - set(after)),
        changed=sorted(
            k for k in before.keys() & after.keys() if before[k] != after[k]
        ),
    )
