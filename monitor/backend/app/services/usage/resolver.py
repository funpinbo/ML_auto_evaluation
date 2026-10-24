"""이 저장소의 Claude Code 기록 디렉터리 해석 (ADR-002 Decision 1, D-13, contracts/README §3, privacy.md §4).

순서
1. 규칙 인코딩: 저장소 절대 경로의 영숫자 외 문자를 `-` 로 바꾼 이름(대소문자 무시 비교로 보완).
2. 스냅샷 힌트 `transcript_dir_name`: 계약 pattern 으로 **재검증**(P-25) 후 사용.
3. 폴백: `projects/*` 의 최근 30일 JSONL 에서 사전 필터를 통과한 usage 줄의 `cwd` 만 비교(P-05).

모든 후보는 `resolve()` 결과의 parent 가 `projects` 의 `resolve()` 와 정확히 같아야 한다(직속 하위, P-27) —
밖을 가리키는 symlink 는 여기서 거부된다(P-28). 실패는 값·경로 없이 코드로만 돌려준다.
`~/.claude` 아래에서는 `projects/` 목록과 그 하위 JSONL 만 본다(P-21).
"""

from __future__ import annotations

import os
import re
import stat
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from app.services.usage.privacy_filter import USAGE_NEEDLE, extract_cwd

# contracts/claude-status.schema.json `transcript_dir_name.pattern` 과 문자 그대로 같다 (P-25 diff 대상).
DIR_NAME_PATTERN = r"^(?!\.{1,2}(?![\s\S]))[A-Za-z0-9._-]{1,255}(?![\s\S])"
DIR_NAME_RE = re.compile(DIR_NAME_PATTERN)
MAX_AGE_SEC = 30 * 86400
CWD_SCAN_MAX_LINES = 200  # 파일당 폴백 탐색 줄 수 상한 (첫 usage 줄의 cwd 면 충분)
CWD_SCAN_MAX_BYTES = 4 * 1024 * 1024


class ResolveSource(str, Enum):
    encoded = "encoded"
    hint = "hint"
    cwd = "cwd"


class HintProblem(str, Enum):
    """힌트를 무시한 이유. 로그에는 이 코드만 쓴다 (D-13)."""

    INVALID_NAME = "HINT_INVALID_NAME"
    OUTSIDE_PROJECTS = "HINT_OUTSIDE_PROJECTS"
    NOT_FOUND = "HINT_NOT_FOUND"


@dataclass(frozen=True)
class Resolution:
    path: Path | None  # resolve() 된 프로젝트 디렉터리. 응답·로그에 내보내지 않는다
    source: ResolveSource | None
    hint_problem: HintProblem | None = None


def encode_project_path(path: str | os.PathLike[str]) -> str:
    """Claude Code 의 프로젝트 디렉터리 이름 규칙: 영숫자 외 모든 문자 → `-`."""
    return re.sub(r"[^A-Za-z0-9]", "-", os.fspath(path))


def valid_dir_name(name: object) -> bool:
    """계약 pattern 재검증. `re.match` + `(?![\\s\\S])` 끝 앵커 = 전체 일치 (끝 개행 함정 없음)."""
    return isinstance(name, str) and DIR_NAME_RE.match(name) is not None


def direct_child(projects: Path, name: str) -> Path | None:
    """`projects/<name>` 을 resolve 해서 parent 가 projects 의 resolve 와 같은 디렉터리면 그 경로."""
    try:
        root = projects.resolve(strict=True)
        target = (projects / name).resolve(strict=True)
    except (OSError, RuntimeError, ValueError):
        return None
    if target.parent != root:
        return None
    try:
        if not stat.S_ISDIR(os.stat(target).st_mode):
            return None
    except (OSError, ValueError):
        return None
    return target


def _same_path(a: str, b: str) -> bool:
    def norm(p: str) -> str:
        return os.path.normcase(os.path.normpath(p)).rstrip("\\/").casefold()

    return norm(a) == norm(b)


def iter_jsonl(
    root: Path, *, cutoff: float | None = None
) -> Iterator[os.DirEntry[str]]:
    """`root` 아래 `**/*.jsonl` 정규 파일(재귀, subagents/ 포함). symlink 는 파일·디렉터리 모두 따라가지 않는다."""
    stack = [str(root)]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as it:
                entries = list(it)
        except OSError:
            continue
        for entry in entries:
            try:
                if entry.is_symlink():
                    continue
                if entry.is_dir(follow_symlinks=False):
                    stack.append(entry.path)
                    continue
                if not entry.name.endswith(".jsonl") or not entry.is_file(
                    follow_symlinks=False
                ):
                    continue
                if (
                    cutoff is not None
                    and entry.stat(follow_symlinks=False).st_mtime < cutoff
                ):
                    continue
            except OSError:
                continue
            yield entry


def _file_has_cwd(path: str, repo: str) -> bool:
    """사전 필터를 통과한 줄에서만 `cwd` 를 꺼내 비교하고 바로 버린다."""
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except OSError:
        return False
    with os.fdopen(fd, "rb") as fh:
        read = 0
        for n, raw in enumerate(fh):
            read += len(raw)
            if n >= CWD_SCAN_MAX_LINES or read > CWD_SCAN_MAX_BYTES:
                break
            if USAGE_NEEDLE not in raw:
                continue
            cwd = extract_cwd(raw.rstrip(b"\r\n"))
            if cwd is not None:
                return _same_path(cwd, repo)
    return False


def _scan_cwd(projects: Path, repo: str, now: float) -> Path | None:
    cutoff = now - MAX_AGE_SEC
    try:
        with os.scandir(projects) as it:
            names = sorted(e.name for e in it)
    except OSError:
        return None
    for name in names:
        if not valid_dir_name(name):
            continue
        candidate = direct_child(projects, name)
        if candidate is None:
            continue
        files = sorted(
            iter_jsonl(candidate, cutoff=cutoff),
            key=lambda e: _mtime(e),
            reverse=True,
        )
        for entry in files[:20]:
            if _file_has_cwd(entry.path, repo):
                return candidate
    return None


def _mtime(entry: os.DirEntry[str]) -> float:
    try:
        return entry.stat(follow_symlinks=False).st_mtime
    except OSError:
        return 0.0


def _encoded(projects: Path, repo: str) -> Path | None:
    name = encode_project_path(repo)
    if not valid_dir_name(name):
        return None
    found = direct_child(projects, name)
    if found is not None:
        return found
    # macOS·Windows 대소문자 차이 보완 (ADR-002 §1.1): 목록에서 대소문자 무시로 같은 이름
    try:
        with os.scandir(projects) as it:
            names = [e.name for e in it]
    except OSError:
        return None
    for other in sorted(names):
        if other.casefold() == name.casefold() and valid_dir_name(other):
            found = direct_child(projects, other)
            if found is not None:
                return found
    return None


def resolve_project_dir(
    claude_home: Path,
    repo_root: Path,
    hint: str | None,
    *,
    now: float,
    allow_cwd_scan: bool = True,
    resolve_repo: Callable[[Path], Path] = lambda p: p.resolve(),
) -> Resolution:
    """규칙 → 힌트 → cwd 폴백. 찾지 못하면 `path=None` (패널은 PROJECT_DIR_NOT_FOUND)."""
    projects = claude_home / "projects"
    try:
        repo = str(resolve_repo(repo_root))
    except (OSError, RuntimeError):
        repo = os.path.abspath(repo_root)
    problem: HintProblem | None = None
    found = _encoded(projects, repo)
    if found is not None:
        return Resolution(found, ResolveSource.encoded)
    if hint is not None:
        if not valid_dir_name(hint):
            problem = HintProblem.INVALID_NAME
        else:
            found = direct_child(projects, hint)
            if found is not None:
                return Resolution(found, ResolveSource.hint)
            problem = (
                HintProblem.NOT_FOUND
                if not os.path.lexists(projects / hint)
                else HintProblem.OUTSIDE_PROJECTS
            )
    if allow_cwd_scan:
        found = _scan_cwd(projects, repo, now)
        if found is not None:
            return Resolution(found, ResolveSource.cwd, problem)
    return Resolution(None, None, problem)
