"""실제 홈 접근 감시 (T-023, I-09, CON-06, privacy.md P-30).

HOME 환경 변수 치환만으로는 `pwd`·하드코딩 경로·symlink 로 실제 홈에 닿는 코드를 막지 못한다.
그래서 `sys.addaudithook` 으로 `open`·`os.listdir`·`os.scandir` 감사 이벤트를 보고, 경로가
실제 홈 아래면 **시스템 호출 전에** `RealHomeAccessError` 를 던지고 위반을 기록한다.

설계
- 실제 홈은 conftest import 시점(환경 변수를 바꾸기 전)에 `HOME`·`USERPROFILE`·`HOMEDRIVE+HOMEPATH`·
  `expanduser("~")`·`pwd.getpwuid(getuid()).pw_dir` 에서 모은다. `/` 같은 루트는 감시 대상에서 뺀다
  (전부 막혀 버린다). 시작 시 설정돼 있던 `CLAUDE_CONFIG_DIR`·`CLAUDE_HOME` 값도 민감 경로에 넣는다.
- 민감 경로(`~/.claude`, `~/.claude.json`, `~/.config/claude`, 위 환경 변수 값)는 허용 목록보다 우선한다.
- 허용 목록: pytest·Python 이 정당하게 읽는 곳. 저장소 루트, `sys.prefix`/`exec_prefix`/`base_*`,
  설치 시점의 `sys.path` 항목(venv·user site-packages 가 홈 아래여도 import 가능), 임시 디렉터리
  (`tempfile.gettempdir()`, Windows 는 보통 홈 아래). 단 실제 홈 자체이거나 그 **조상**인 항목, 민감
  경로 아래 항목은 허용 목록에 넣지 않는다(넣으면 가드가 무력해진다).
- symlink: 경로를 앞에서부터 한 단계씩 따라가며(`islink`/`readlink`) 대상이 실제 홈으로 들어가는
  순간 멈춘다. 따라서 tmp 의 링크가 홈을 가리켜도 잡고, 판정을 위해 홈 안을 `stat` 하지 않는다.
  허용 경로로 가는 길의 조상 디렉터리(예: 홈 아래 저장소면 홈 자체)만 `lstat` 될 수 있다.
- 한계: 정수 fd, `dir_fd` 기준 상대 경로, 감사 이벤트가 없는 호출(`os.stat`, `os.readlink` 등)은 보지
  않는다. 목적은 "파일 내용·목록을 읽는 접근" 차단이다.
- 감사 hook 은 제거할 수 없다. 대신 `enabled` 플래그로 끄고 켤 수 있고, 음성 테스트는 `expect()`
  블록 안에서 접근을 시도한다. 그 블록의 위반은 테스트 실패로 세지 않고 블록이 돌려준 목록에만 담긴다.
  접근 자체는 블록 안에서도 차단된다(실제 홈은 열리지 않는다).
- 실패 메시지는 이벤트·분류·`~/<첫 경로 요소>` 만 적는다(전체 경로·내용은 적지 않는다).
"""

from __future__ import annotations

import os
import sys
import tempfile
import threading
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

GUARDED_EVENTS = frozenset({"open", "os.listdir", "os.scandir"})
_MAX_LINK_HOPS = 40


class RealHomeAccessError(PermissionError):
    """테스트가 실제 홈 아래 경로를 열거나 나열하려 했다."""


@dataclass(frozen=True)
class Violation:
    event: str
    kind: str  # "sensitive" | "home"
    hint: str  # "~/<첫 경로 요소>" — 전체 경로는 남기지 않는다

    def __str__(self) -> str:
        return f"{self.event} {self.kind} {self.hint}"


def _norm(path: str) -> str:
    return os.path.normcase(os.path.normpath(os.path.abspath(path)))


def _is_under(path: str, root: str) -> bool:
    return path == root or path.startswith(root.rstrip(os.sep) + os.sep)


def _is_filesystem_root(path: str) -> bool:
    return os.path.dirname(path) == path


def detect_real_homes(environ: dict[str, str] | None = None) -> tuple[str, ...]:
    """환경 변수를 바꾸기 전에 호출한다. 실제 홈 후보(정규화, 중복 제거)."""
    env = dict(os.environ if environ is None else environ)
    candidates: list[str] = []
    for key in ("HOME", "USERPROFILE"):
        if env.get(key):
            candidates.append(env[key])
    if env.get("HOMEDRIVE") and env.get("HOMEPATH"):
        candidates.append(env["HOMEDRIVE"] + env["HOMEPATH"])
    if environ is None:
        candidates.append(os.path.expanduser("~"))
        try:
            import pwd

            candidates.append(pwd.getpwuid(os.getuid()).pw_dir)
        except (ImportError, KeyError, AttributeError, OSError):
            pass  # Windows 등 pwd 가 없는 플랫폼
    homes: list[str] = []
    for raw in candidates:
        if not raw or raw == "~":
            continue
        norm = _norm(raw)
        if not _is_filesystem_root(norm) and norm not in homes:
            homes.append(norm)
    return tuple(homes)


def sensitive_paths(
    real_homes: Iterable[str], environ: dict[str, str] | None = None
) -> tuple[str, ...]:
    env = os.environ if environ is None else environ
    out: list[str] = []
    for home in real_homes:
        out += [
            os.path.join(home, ".claude"),
            os.path.join(home, ".claude.json"),
            os.path.join(home, ".config", "claude"),
        ]
    for key in ("CLAUDE_CONFIG_DIR", "CLAUDE_HOME"):
        if env.get(key):
            out.append(env[key])
    result: list[str] = []
    for raw in out:
        norm = _norm(raw)
        if not _is_filesystem_root(norm) and norm not in result:
            result.append(norm)
    return tuple(result)


def default_allowed_roots(repo_root: Path) -> list[str]:
    roots = [
        str(repo_root),
        sys.prefix,
        sys.exec_prefix,
        sys.base_prefix,
        sys.base_exec_prefix,
        tempfile.gettempdir(),
    ]
    roots += [p for p in sys.path if p]
    return roots


class HomeGuard:
    def __init__(
        self,
        real_homes: Iterable[str],
        sensitive: Iterable[str] = (),
        allowed: Iterable[str] = (),
    ) -> None:
        self.real_homes = tuple(real_homes)
        self.sensitive = tuple(_norm(p) for p in sensitive)
        self.allowed: list[str] = []
        self.rejected_allow: list[str] = []
        for root in allowed:
            self.allow(root)
        self.enabled = True
        self.installed = False
        self.violations: list[Violation] = []
        self._expect_stack: list[list[Violation]] = []
        self._local = threading.local()

    # --- 구성 ---------------------------------------------------------------
    def allow(self, root: str | os.PathLike[str]) -> bool:
        """허용 목록에 추가한다. 실제 홈이거나 그 조상, 민감 경로 아래면 거부하고 False."""
        norm = _norm(os.fspath(root))
        if any(_is_under(home, norm) for home in self.real_homes) or any(
            _is_under(norm, s) for s in self.sensitive
        ):
            self.rejected_allow.append(norm)
            return False
        if norm not in self.allowed:
            self.allowed.append(norm)
        return True

    def install(self) -> None:
        if not self.installed:
            sys.addaudithook(self.audit)
            self.installed = True

    # --- 판정 ---------------------------------------------------------------
    def _lexical(self, path: str) -> str | None:
        if any(_is_under(path, s) for s in self.sensitive):
            return "sensitive"
        if any(_is_under(path, h) for h in self.real_homes) and not any(
            _is_under(path, a) for a in self.allowed
        ):
            return "home"
        return None

    def classify(self, path: str | bytes | os.PathLike) -> tuple[str, str] | None:
        """`(kind, 판정된 경로)` 또는 None. symlink 를 따라가되 홈 안은 stat 하지 않는다."""
        current = _norm(os.fsdecode(os.fspath(path)))
        hops = 0
        while True:
            verdict = self._lexical(current)
            if verdict:
                return verdict, current
            drive, rest = os.path.splitdrive(current)
            parts = [p for p in rest.split(os.sep) if p]
            prefix = drive + os.sep
            redirected = False
            for index, part in enumerate(parts):
                # 조상 디렉터리는 분류하지 않는다: 전체 경로가 위에서 통과했으면 조상은 허용 경로로
                # 가는 길(예: 홈 아래 저장소의 홈 자체)이고, 링크인지 여부만 본다.
                candidate = os.path.join(prefix, part)
                if os.path.islink(candidate):
                    hops += 1
                    if hops > _MAX_LINK_HOPS:
                        return None  # 순환 링크: OS 가 ELOOP 로 실패시킨다
                    target = os.readlink(candidate)
                    base = (
                        target
                        if os.path.isabs(target)
                        else os.path.join(prefix, target)
                    )
                    current = _norm(os.path.join(base, *parts[index + 1 :]))
                    redirected = True
                    break
                prefix = candidate
            if not redirected:
                return None

    def _hint(self, path: str) -> str:
        for home in self.real_homes:
            if _is_under(path, home):
                rel = path[len(home) :].lstrip(os.sep)
                return "~/" + (rel.split(os.sep, 1)[0] if rel else "")
        return "<sensitive>"

    def audit(self, event: str, args: tuple) -> None:
        if event not in GUARDED_EVENTS or not self.enabled:
            return
        if getattr(self._local, "busy", False):
            return
        target = args[0] if args else None
        if event == "os.scandir" and target is None:
            target = "."
        if target is None or isinstance(target, int):
            return
        self._local.busy = True
        try:
            try:
                result = self.classify(target)
            except (TypeError, ValueError, OSError):
                return
            if result is None:
                return
            kind, hit = result
            violation = Violation(event, kind, self._hint(hit))
            (self._expect_stack[-1] if self._expect_stack else self.violations).append(
                violation
            )
        finally:
            self._local.busy = False
        raise RealHomeAccessError(
            f"real home access blocked by test guard: {violation}"
        )

    # --- 테스트 지원 ----------------------------------------------------------
    @contextmanager
    def expect(self) -> Iterator[list[Violation]]:
        """음성 테스트용: 블록 안의 위반은 여기에만 담고 테스트 실패로 세지 않는다(차단은 유지)."""
        caught: list[Violation] = []
        self._expect_stack.append(caught)
        try:
            yield caught
        finally:
            self._expect_stack.pop()

    @contextmanager
    def disabled(self) -> Iterator[None]:
        """감시를 잠시 끈다. 끈 동안의 접근은 실제로 일어나므로 테스트에서는 `expect()` 를 쓴다."""
        previous = self.enabled
        self.enabled = False
        try:
            yield
        finally:
            self.enabled = previous

    def take(self) -> list[Violation]:
        taken, self.violations = self.violations, []
        return taken
