"""공용 pytest fixture (qa 소유, T-003).

원칙
- 실제 `~/.claude`·홈 디렉터리를 쓰지 않는다. 모든 테스트에서 HOME 을 임시 경로로 바꾸고
  AIDLC_ROOT / CLAUDE_HOME 을 지워, 테스트가 필요한 값을 명시적으로 주입하게 한다 (CON-06).
- 경로는 환경 변수로 주입한다: `app_env` 는 AIDLC_ROOT·CLAUDE_HOME 을 설정한다.
- fixture 생성은 결정적(seed 고정)이다.

tests/ 에는 `__init__.py` 가 없다. pytest 기본 import 모드(prepend)가 이 디렉터리를
sys.path 에 넣으므로 `from fixtures...` 로 가져온다. 테스트 파일 이름은 디렉터리가 달라도
겹치지 않게 짓는다.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest

# importmode=importlib 로 실행해도 fixtures 패키지를 찾도록 보강한다.
_TESTS_DIR = str(Path(__file__).resolve().parent)
if _TESTS_DIR not in sys.path:
    sys.path.insert(0, _TESTS_DIR)

from fixtures.claude_home import (  # noqa: E402
    ClaudeHome,
    EscapeCase,
    add_symlink_escapes,
    build_claude_home,
)
from fixtures.jsonl_gen import FIXED_NOW  # noqa: E402
from fixtures.runtime_files import write_claude_status  # noqa: E402
from fixtures.workspace import WorkspaceInfo, build_workspace  # noqa: E402


@pytest.fixture(autouse=True)
def _isolate_home(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> Path:
    """실제 홈을 가리킬 수 있는 환경 변수를 임시 경로로 바꾼다."""
    fake_home = tmp_path_factory.mktemp("fake_home")
    for var in ("HOME", "USERPROFILE"):
        monkeypatch.setenv(var, str(fake_home))
    for var in ("AIDLC_ROOT", "CLAUDE_HOME"):
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

    def make(kind: str = "full", *, task_count: int = 12, name: str | None = None) -> WorkspaceInfo:
        counter["n"] += 1
        return build_workspace(
            tmp_path / "workspaces", kind, task_count=task_count, name=name or f"{kind}-{counter['n']}"
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
        return build_claude_home(tmp_path / f"home-{counter['n']}", workspace_root, **options)

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
        return {"AIDLC_ROOT": str(self.workspace.root), "CLAUDE_HOME": str(self.claude_home.home)}


@pytest.fixture
def app_env(full_workspace: WorkspaceInfo, claude_home: ClaudeHome, monkeypatch: pytest.MonkeyPatch) -> AppEnv:
    """full workspace + 정상 스냅샷 + CLAUDE_HOME 을 만들고 환경 변수로 주입한다."""
    write_claude_status(
        full_workspace.claude_status_file, "normal", transcript_dir_name=claude_home.dir_name
    )
    env = AppEnv(full_workspace, claude_home)
    for key, value in env.env.items():
        monkeypatch.setenv(key, value)
    return env
