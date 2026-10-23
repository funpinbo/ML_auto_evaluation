"""설정 (D-16 환경 변수 주입, D-19 포트 단일 출처·0 금지)."""

from __future__ import annotations

from pathlib import Path

import pytest
from backend_support import TEST_PORT

from app.config import BIND_HOST, DEFAULT_PORT, Settings, parse_port, validate_port


def test_bind_host_is_loopback_literal() -> None:
    assert BIND_HOST == "127.0.0.1"


@pytest.mark.parametrize("raw", ["0", "65536", "-1", "08765", "abc", "", "1.5", " "])
def test_bad_ports_rejected(raw: str) -> None:
    with pytest.raises(ValueError):
        parse_port(raw)


@pytest.mark.parametrize("bad", [True, "8765", 8.0])
def test_validate_port_types(bad) -> None:
    with pytest.raises(TypeError):
        validate_port(bad)


def test_port_zero_rejected_by_settings(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        Settings(port=0, aidlc_root=tmp_path, claude_home=tmp_path, dist_dir=tmp_path)


def test_from_env_paths_and_port(tmp_path: Path) -> None:
    env = {"AIDLC_ROOT": str(tmp_path / "r"), "CLAUDE_HOME": str(tmp_path / "c"),
           "AIDLC_MONITOR_PORT": str(TEST_PORT)}  # fmt: skip
    s = Settings.from_env(env)
    assert s.aidlc_root == tmp_path / "r" and s.claude_home == tmp_path / "c"
    assert s.port == TEST_PORT
    assert s.allowed_hosts == {f"127.0.0.1:{TEST_PORT}", f"localhost:{TEST_PORT}"}
    assert s.allowed_origins == {
        f"http://127.0.0.1:{TEST_PORT}",
        f"http://localhost:{TEST_PORT}",
    }
    assert Settings.from_env(env, port=9000).port == 9000  # --port 가 우선


def test_from_env_defaults_use_fake_home(_isolate_home: Path) -> None:
    s = Settings.from_env({})
    assert s.port == DEFAULT_PORT
    assert s.claude_home == _isolate_home / ".claude"
    assert (s.aidlc_root / "aidlc" / "hooks" / "memory_cascade.py").is_file()


def test_main_cli_parses_port_without_host_option(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.__main__ as entry

    captured = {}

    def fake_run(app, **kwargs):
        captured.update(kwargs, app=app)

    monkeypatch.setattr(entry.uvicorn, "run", fake_run)
    monkeypatch.setattr(entry, "setup_logging", lambda: None)
    assert entry.main(["--port", str(TEST_PORT)]) == 0
    assert captured["host"] == "127.0.0.1" and captured["port"] == TEST_PORT
    assert captured["app"].settings.port == TEST_PORT
    with pytest.raises(SystemExit):
        entry.main(["--host", "0.0.0.0"])
