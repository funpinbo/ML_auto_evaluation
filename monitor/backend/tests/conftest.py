"""공용 pytest fixture (qa 소유, T-003).

원칙
- 실제 `~/.claude`·홈 디렉터리를 쓰지 않는다 (CON-06, I-09). 3겹으로 막는다.
  1. 세션 시작(`pytest_configure`): HOME/USERPROFILE 을 세션 임시 홈으로 바꾸고 AIDLC_ROOT /
     CLAUDE_HOME / CLAUDE_CONFIG_DIR / XDG_CONFIG_HOME 을 지운다. session·module 범위 fixture 와
     수집 시점 import 도 실제 홈을 보지 못한다. 종료(`pytest_unconfigure`) 때 원래 값으로 되돌린다.
  2. 테스트마다(`_isolate_home`, autouse): 같은 변수를 테스트 전용 임시 홈으로 다시 바꾼다.
  3. 감사 hook(`fixtures/home_guard.py`): 실제 홈 아래 open/listdir/scandir 를 시스템 호출 전에
     막고 기록한다. 테스트가 예외를 삼켜도 `_home_guard_check` 가 그 테스트를 실패시킨다.
     실제 홈은 이 모듈 import 시점(환경 변수를 바꾸기 전)에 환경 변수와 `pwd` 로 기록한다.
- 경로는 환경 변수로 주입한다: `app_env` 는 AIDLC_ROOT·CLAUDE_HOME 을 설정한다.
- fixture 생성은 결정적(seed 고정)이다.

tests/ 에는 `__init__.py` 가 없다. pytest 기본 import 모드(prepend)가 이 디렉터리를
sys.path 에 넣으므로 `from fixtures...` 로 가져온다. 테스트 파일 이름은 디렉터리가 달라도
겹치지 않게 짓는다.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

# importmode=importlib 로 실행해도 fixtures 패키지를 찾도록 보강한다.
_TESTS_DIR = str(Path(__file__).resolve().parent)
if _TESTS_DIR not in sys.path:
    sys.path.insert(0, _TESTS_DIR)

from fixtures.claude_home import (
    ClaudeHome,
    EscapeCase,
    add_symlink_escapes,
    build_claude_home,
)
from fixtures.home_guard import (
    HomeGuard,
    default_allowed_roots,
    detect_real_homes,
    sensitive_paths,
)
from fixtures.jsonl_gen import FIXED_NOW
from fixtures.runtime_files import write_claude_status
from fixtures.workspace import WorkspaceInfo, build_workspace


# 환경 변수를 바꾸기 전에 기록한다 (import 시점 = 세션 시작 전).
REPO_ROOT = Path(__file__).resolve().parents[3]
HOME_VARS = ("HOME", "USERPROFILE")
CLEARED_VARS = ("AIDLC_ROOT", "CLAUDE_HOME", "CLAUDE_CONFIG_DIR", "XDG_CONFIG_HOME")
REAL_HOMES = detect_real_homes()
HOME_GUARD = HomeGuard(REAL_HOMES, sensitive_paths(REAL_HOMES))
_SAVED_ENV: dict[str, str | None] = {}
_SESSION_HOME: dict[str, str] = {}


def pytest_configure(config: pytest.Config) -> None:
    for root in default_allowed_roots(REPO_ROOT):
        HOME_GUARD.allow(root)
    session_home = tempfile.mkdtemp(prefix="qa-session-home-")
    _SESSION_HOME["path"] = session_home
    for var in (*HOME_VARS, *CLEARED_VARS):
        _SAVED_ENV[var] = os.environ.get(var)
    for var in HOME_VARS:
        os.environ[var] = session_home
    for var in CLEARED_VARS:
        os.environ.pop(var, None)
    HOME_GUARD.install()


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """테스트 밖(수집·session fixture 등)에서 생긴 위반도 세션 실패로 만든다."""
    leftover = HOME_GUARD.take()
    if leftover:
        sys.stderr.write(
            "\n[home-guard] 테스트 밖 실제 홈 접근: "
            + ", ".join(str(v) for v in leftover)
            + "\n"
        )
        session.exitstatus = pytest.ExitCode.TESTS_FAILED


def pytest_unconfigure(config: pytest.Config) -> None:
    for var, value in _SAVED_ENV.items():
        if value is None:
            os.environ.pop(var, None)
        else:
            os.environ[var] = value
    _SAVED_ENV.clear()
    session_home = _SESSION_HOME.pop("path", None)
    if session_home:
        shutil.rmtree(session_home, ignore_errors=True)


@pytest.fixture(scope="session")
def home_guard() -> HomeGuard:
    """감사 hook 가드. 음성 테스트는 `with home_guard.expect() as caught:` 안에서 접근을 시도한다."""
    return HOME_GUARD


@pytest.fixture(scope="session")
def session_home() -> Path:
    return Path(_SESSION_HOME["path"])


@pytest.fixture(autouse=True)
def _home_guard_check() -> Iterator[None]:
    """테스트가 RealHomeAccessError 를 삼켜도 기록된 위반이 있으면 실패시킨다.

    시작 시 비우지 않는다: 수집·앞선 teardown 의 위반도 버리지 않고 이 테스트 실패로 드러낸다.
    """
    yield
    found = HOME_GUARD.take()
    if found:
        pytest.fail(
            "실제 홈 접근 감지: " + ", ".join(str(v) for v in found), pytrace=False
        )


@pytest.fixture(autouse=True)
def _isolate_home(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> Path:
    """실제 홈을 가리킬 수 있는 환경 변수를 테스트 전용 임시 경로로 바꾼다."""
    fake_home = tmp_path_factory.mktemp("fake_home")
    for var in HOME_VARS:
        monkeypatch.setenv(var, str(fake_home))
    for var in CLEARED_VARS:
        monkeypatch.delenv(var, raising=False)
    return fake_home


@pytest.fixture
def fixed_now():
    """시계 의존을 없애기 위한 고정 현재 시각 (UTC)."""
    return FIXED_NOW


@pytest.fixture
def workspace_factory(tmp_path: Path) -> Callable[..., WorkspaceInfo]:
    """`workspace_factory("closed_stm", task_count=100)` 처럼 호출한다. kind 마다 한 번만 만들 수 있다."""
    counter = {"n": 0}

    def make(
        kind: str = "full", *, task_count: int = 12, name: str | None = None
    ) -> WorkspaceInfo:
        counter["n"] += 1
        return build_workspace(
            tmp_path / "workspaces",
            kind,
            task_count=task_count,
            name=name or f"{kind}-{counter['n']}",
        )

    return make


@pytest.fixture
def empty_workspace(workspace_factory) -> WorkspaceInfo:
    return workspace_factory("empty")


@pytest.fixture
def partial_workspace(workspace_factory) -> WorkspaceInfo:
    return workspace_factory("partial")


@pytest.fixture
def full_workspace(workspace_factory) -> WorkspaceInfo:
    return workspace_factory("full")


@pytest.fixture
def broken_workspace(workspace_factory) -> WorkspaceInfo:
    return workspace_factory("broken")


@pytest.fixture
def closed_stm_workspace(workspace_factory) -> WorkspaceInfo:
    return workspace_factory("closed_stm")


@pytest.fixture
def workspace_100_tasks(workspace_factory) -> WorkspaceInfo:
    """성능 시나리오용: Task 100개 (NFR-001)."""
    return workspace_factory("full", task_count=100)


@pytest.fixture
def claude_home_factory(tmp_path: Path) -> Callable[..., ClaudeHome]:
    """`claude_home_factory(workspace_root, days=3, responses_per_day=5)` 처럼 호출한다."""
    counter = {"n": 0}

    def make(workspace_root: Path, **options: object) -> ClaudeHome:
        counter["n"] += 1
        return build_claude_home(
            tmp_path / f"home-{counter['n']}", workspace_root, **options
        )

    return make


@pytest.fixture
def claude_home(full_workspace: WorkspaceInfo, claude_home_factory) -> ClaudeHome:
    """full workspace 에 대응하는 CLAUDE_HOME (30일 JSONL + 경계 입력 포함)."""
    return claude_home_factory(full_workspace.root)


@pytest.fixture
def symlink_escape(tmp_path: Path, claude_home: ClaudeHome) -> EscapeCase:
    """`~/.claude` 밖을 가리키는 symlink 음성 케이스. symlink 를 못 만드는 환경에서는 건너뛴다."""
    try:
        return add_symlink_escapes(tmp_path, claude_home)
    except (OSError, NotImplementedError) as exc:  # 예: 권한 없는 Windows
        pytest.skip(f"symlink 를 만들 수 없는 환경: {type(exc).__name__}")


@dataclass(frozen=True)
class AppEnv:
    """서버가 시작될 때 받는 입력 전체. 백엔드 테스트는 이것으로 앱 팩토리를 구성한다."""

    workspace: WorkspaceInfo
    claude_home: ClaudeHome

    @property
    def env(self) -> dict[str, str]:
        return {
            "AIDLC_ROOT": str(self.workspace.root),
            "CLAUDE_HOME": str(self.claude_home.home),
        }


@pytest.fixture
def app_env(
    full_workspace: WorkspaceInfo,
    claude_home: ClaudeHome,
    monkeypatch: pytest.MonkeyPatch,
) -> AppEnv:
    """full workspace + 정상 스냅샷 + CLAUDE_HOME 을 만들고 환경 변수로 주입한다."""
    write_claude_status(
        full_workspace.claude_status_file,
        "normal",
        transcript_dir_name=claude_home.dir_name,
    )
    env = AppEnv(full_workspace, claude_home)
    for key, value in env.env.items():
        monkeypatch.setenv(key, value)
    return env
