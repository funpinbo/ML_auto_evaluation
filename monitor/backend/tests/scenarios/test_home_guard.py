"""실제 홈 격리 가드 검증 (T-023, I-09, CON-06, privacy.md P-30).

음성 테스트: 감사 hook 가드가 실제 홈 아래 open/listdir/scandir 를 **시스템 호출 전에** 막는지,
테스트가 예외를 삼켜도 위반이 남는지, 허용 목록이 가드를 무력화하지 못하는지 확인한다.
실제 홈 아래에는 존재하지 않는 이름만 쓴다. 차단이 실패하더라도 내용을 읽지 않는다.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fixtures.home_guard import (
    HomeGuard,
    RealHomeAccessError,
    detect_real_homes,
    sensitive_paths,
)

PROBE = "qa-home-guard-probe-does-not-exist"


def _open(path: Path, mode: str = "r") -> None:
    with open(path, mode) as fh:
        fh.read(1)


@pytest.fixture(scope="session")
def _session_env_snapshot() -> dict[str, str | None]:
    """session 범위 fixture 가 보는 환경 (pytest_configure 이후, 테스트별 치환 이전)."""
    keys = (
        "HOME",
        "USERPROFILE",
        "AIDLC_ROOT",
        "CLAUDE_HOME",
        "CLAUDE_CONFIG_DIR",
        "XDG_CONFIG_HOME",
    )
    return {k: os.environ.get(k) for k in keys}


@pytest.fixture
def real_home(home_guard: HomeGuard) -> Path:
    if not home_guard.real_homes:
        pytest.skip("실제 홈을 감지하지 못한 환경")
    return Path(home_guard.real_homes[0])


# --- 세션 범위 격리 (①②) ------------------------------------------------------


def test_session_scope_sees_session_home(_session_env_snapshot, session_home):
    env = _session_env_snapshot
    assert env["HOME"] == str(session_home)
    assert env["USERPROFILE"] == str(session_home)
    for key in ("AIDLC_ROOT", "CLAUDE_HOME", "CLAUDE_CONFIG_DIR", "XDG_CONFIG_HOME"):
        assert env[key] is None, key


def test_session_home_is_not_real_home(session_home, home_guard):
    for home in home_guard.real_homes:
        assert not str(session_home.resolve()).startswith(home + os.sep)
        assert str(session_home.resolve()) != home


def test_claude_config_dir_unset_in_test():
    assert "CLAUDE_CONFIG_DIR" not in os.environ
    assert "XDG_CONFIG_HOME" not in os.environ


# --- 가드 설치·실제 홈 기록 (③) -------------------------------------------------


def test_guard_installed_and_enabled(home_guard):
    assert home_guard.installed and home_guard.enabled


def test_real_home_recorded_from_pwd(home_guard):
    pwd = pytest.importorskip("pwd")
    pw_dir = os.path.normcase(os.path.normpath(pwd.getpwuid(os.getuid()).pw_dir))
    if os.path.dirname(pw_dir) == pw_dir:
        pytest.skip("pwd 홈이 파일 시스템 루트")
    assert pw_dir in home_guard.real_homes


def test_detect_real_homes_from_environ_skips_root():
    homes = detect_real_homes({"HOME": "/x/fake-home", "USERPROFILE": os.sep})
    assert homes == (os.path.normcase(os.path.normpath("/x/fake-home")),)


def test_sensitive_paths_cover_claude_dirs_and_config_env(tmp_path):
    home = str(tmp_path / "h")
    paths = sensitive_paths([home], {"CLAUDE_CONFIG_DIR": str(tmp_path / "cfg")})
    norm = [os.path.normcase(p) for p in paths]
    for expected in (
        os.path.join(home, ".claude"),
        os.path.join(home, ".claude.json"),
        os.path.join(home, ".config", "claude"),
        str(tmp_path / "cfg"),
    ):
        assert os.path.normcase(os.path.normpath(expected)) in norm


# --- 음성: 가드가 실제로 잡는다 (③) ---------------------------------------------


@pytest.mark.parametrize(
    "access",
    [
        pytest.param(lambda p: _open(p / PROBE), id="open"),
        pytest.param(lambda p: (p / PROBE).read_text(encoding="utf-8"), id="read_text"),
        pytest.param(lambda p: os.listdir(p), id="listdir"),
        pytest.param(lambda p: os.scandir(p), id="scandir"),
        pytest.param(lambda p: list(p.iterdir()), id="iterdir"),
        pytest.param(lambda p: _open(p / ".claude" / PROBE, "rb"), id="claude_dir"),
    ],
)
def test_guard_blocks_real_home_access(home_guard, real_home, access):
    # RealHomeAccessError(PermissionError) 이어야 한다: FileNotFoundError 면 시스템 호출이 일어난 것
    with home_guard.expect() as caught, pytest.raises(RealHomeAccessError):
        access(real_home)
    assert len(caught) == 1
    assert caught[0].kind in {"home", "sensitive"}
    assert caught[0].hint.startswith("~/")


def test_guard_blocks_symlink_into_real_home(home_guard, real_home, tmp_path):
    link = tmp_path / "to-real-home"
    try:
        os.symlink(real_home, link, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlink 를 만들 수 없는 환경: {type(exc).__name__}")
    with home_guard.expect() as caught:
        with pytest.raises(RealHomeAccessError):
            _open(link / PROBE)
        with pytest.raises(RealHomeAccessError):
            os.listdir(link)
    assert len(caught) == 2


def test_swallowed_violation_is_still_recorded(home_guard, real_home):
    """테스트가 예외를 삼켜도 위반이 남아 `_home_guard_check` 가 실패시킨다."""
    try:
        _open(real_home / PROBE)
    except PermissionError:
        pass  # 일부러 삼킨다
    recorded = home_guard.take()  # 꺼내지 않으면 autouse 가 이 테스트를 실패시킨다
    assert len(recorded) == 1 and recorded[0].event == "open"


def test_violation_message_has_no_full_path(home_guard, real_home):
    with home_guard.expect(), pytest.raises(RealHomeAccessError) as info:
        _open(real_home / ".claude" / PROBE)
    assert PROBE not in str(info.value)
    assert str(real_home) not in str(info.value)


# --- 정당한 접근은 허용 ----------------------------------------------------------


def test_guard_allows_tmp_and_repo(home_guard, tmp_path):
    f = tmp_path / "ok.txt"
    f.write_text("x", encoding="utf-8")
    assert f.read_text(encoding="utf-8") == "x"
    assert os.listdir(tmp_path)
    repo = Path(__file__).resolve().parents[4]
    assert (repo / "CLAUDE.md").read_text(encoding="utf-8")
    assert home_guard.take() == []


# --- 허용 목록·플래그 (격리된 인스턴스, hook 미설치) ------------------------------


def _fake_guard(tmp_path: Path) -> tuple[HomeGuard, Path]:
    home = tmp_path / "realhome"
    guard = HomeGuard([str(home)], sensitive_paths([str(home)], {}))
    return guard, home


def test_allow_rejects_home_and_ancestors(tmp_path):
    guard, home = _fake_guard(tmp_path)
    assert guard.allow(home) is False
    assert guard.allow(tmp_path) is False  # 홈의 조상
    assert guard.allow(home / ".claude" / "x") is False  # 민감 경로 아래
    assert guard.allow(home / ".venv") is True  # 홈 아래 venv 는 허용 가능
    assert guard.classify(home / ".venv" / "lib" / "x.py") is None
    assert guard.classify(home / "other") == ("home", str(home / "other"))


def test_sensitive_wins_over_allow(tmp_path):
    guard, home = _fake_guard(tmp_path)
    guard.allowed.append(str(home))  # 직접 넣어도 민감 경로는 막힌다
    assert guard.classify(home / ".claude" / "x")[0] == "sensitive"
    assert guard.classify(home / ".claude.json")[0] == "sensitive"


def test_enabled_flag_and_disabled_context(tmp_path):
    guard, home = _fake_guard(tmp_path)
    target = str(home / "secret")
    with pytest.raises(RealHomeAccessError):
        guard.audit("open", (target, "r", 0))
    with guard.disabled():
        guard.audit("open", (target, "r", 0))  # 꺼지면 통과
    assert guard.enabled
    with pytest.raises(RealHomeAccessError):
        guard.audit("os.scandir", (target,))
    guard.audit("os.stat", (target,))  # 감시 대상 이벤트 아님
    guard.audit("open", (3, "r", 0))  # 정수 fd 는 보지 않음
    assert len(guard.take()) == 2


def test_classify_follows_relative_symlink(tmp_path):
    guard, _home = _fake_guard(tmp_path)
    work = tmp_path / "work"
    work.mkdir()
    link = work / "lnk"
    try:
        os.symlink(os.path.join("..", "realhome"), link)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlink 를 만들 수 없는 환경: {type(exc).__name__}")
    verdict = guard.classify(link / "f")
    assert verdict is not None and verdict[0] == "home"
