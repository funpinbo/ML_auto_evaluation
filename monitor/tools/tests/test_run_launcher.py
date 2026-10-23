"""run.py 순수 로직 테스트 (ADR-001 Consequences: 해시 마커·포트 선택은 함수로 분리해 pytest). cicd 소유.

네트워크·실제 설치 없이 돈다. 실제 기동은 T-007 수동 검증(`bash run.sh --no-browser`)과 UAT K2-W/K2-U.
"""

from __future__ import annotations

import http.server
import importlib.util
import json
import socket
import threading
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


run = _load("aidlc_run_launcher", REPO / "run.py")
dist = _load(
    "aidlc_check_dist_fresh", REPO / "monitor" / "tools" / "check_dist_fresh.py"
)


# ---------------------------------------------------------------- Python / venv


def test_python_version_gate() -> None:
    assert run.python_ok((3, 11))
    assert run.python_ok((3, 14))
    assert not run.python_ok((3, 10))
    assert not run.python_ok((2, 7))


def test_venv_python_path_per_os(tmp_path: Path) -> None:
    assert (
        run.venv_python(tmp_path, windows=True) == tmp_path / "Scripts" / "python.exe"
    )
    assert run.venv_python(tmp_path, windows=False) == tmp_path / "bin" / "python"


def test_venv_usable_rejects_missing(tmp_path: Path) -> None:
    assert not run.venv_usable(tmp_path / "bin" / "python")


# ---------------------------------------------------------------- 해시 마커


def test_install_needed_follows_marker(tmp_path: Path) -> None:
    req = tmp_path / "requirements.txt"
    req.write_text("fastapi==0.161.1\n", encoding="utf-8")
    venv = tmp_path / "venv"
    venv.mkdir()
    assert run.install_needed(venv, req)  # 마커 없음 → 설치
    run.marker_path(venv).write_text(
        run.requirements_digest(req) + "\n", encoding="ascii"
    )
    assert not run.install_needed(venv, req)  # 같으면 생략 (AC-5)
    req.write_text("fastapi==0.161.2\n", encoding="utf-8")
    assert run.install_needed(venv, req)  # 바뀌면 재설치 (AC-6)


def test_install_failure_leaves_no_marker(tmp_path: Path, monkeypatch) -> None:
    """pip 실패 시 마커를 쓰지 않는다 (AC-8). 실제 pip 대신 실패하는 명령을 쓴다."""
    req = tmp_path / "requirements.txt"
    req.write_text("x==1\n", encoding="utf-8")
    venv = tmp_path / "venv"
    venv.mkdir()
    run.marker_path(venv).write_text("stale\n", encoding="ascii")
    fake = tmp_path / "fakepy"
    fake.write_text(
        "#!/bin/sh\necho 'ERROR: No matching distribution found for x==1'\nexit 1\n"
    )
    fake.chmod(0o755)
    monkeypatch.setattr(run, "_runs", lambda cmd, timeout=60.0: True)
    if run.os.name == "nt":
        pytest.skip("셸 스크립트 가짜 pip 는 POSIX 전용")
    with pytest.raises(run.LaunchError) as err:
        run.install_requirements(fake, venv, req)
    assert "No matching distribution" in str(err.value)
    assert not run.marker_path(venv).exists()


# ---------------------------------------------------------------- 포트


@pytest.mark.parametrize(
    "raw", ["0", "00", "08765", "65536", "-1", "abc", "", "87 65", "+8765"]
)
def test_parse_port_rejects(raw: str) -> None:
    with pytest.raises(ValueError):
        run.parse_port(raw)


@pytest.mark.parametrize(
    "raw,expected", [("1", 1), ("8765", 8765), (" 9000 ", 9000), ("65535", 65535)]
)
def test_parse_port_accepts(raw: str, expected: int) -> None:
    assert run.parse_port(raw) == expected


def test_requested_port_precedence() -> None:
    assert run.requested_port(None, {}) == 8765
    assert run.requested_port(None, {"AIDLC_MONITOR_PORT": "9001"}) == 9001
    assert (
        run.requested_port(9100, {"AIDLC_MONITOR_PORT": "9001"}) == 9100
    )  # --port 우선
    with pytest.raises(run.LaunchError) as err:
        run.requested_port(None, {"AIDLC_MONITOR_PORT": "0"})  # 포트 0 금지 (D-19)
    assert err.value.code == 2


def test_choose_port_first_free() -> None:
    assert run.choose_port(8765, free=lambda p: True, ours=lambda p: False) == (
        "start",
        8765,
    )


def test_choose_port_detects_running_monitor() -> None:
    assert run.choose_port(8765, free=lambda p: False, ours=lambda p: p == 8765) == (
        "running",
        8765,
    )


def test_choose_port_skips_foreign_program() -> None:
    result = run.choose_port(8765, free=lambda p: p == 8767, ours=lambda p: False)
    assert result == ("start", 8767)  # AC-10


def test_choose_port_exhausted() -> None:
    with pytest.raises(run.LaunchError, match="8765~8774"):
        run.choose_port(8765, free=lambda p: False, ours=lambda p: False)


def test_choose_port_never_exceeds_65535() -> None:
    seen: list[int] = []
    with pytest.raises(run.LaunchError):
        run.choose_port(
            65534, free=lambda p: seen.append(p) or False, ours=lambda p: False
        )
    assert seen == [65534, 65535]


def test_port_free_detects_listener() -> None:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    sock.listen(1)
    try:
        assert not run.port_free(sock.getsockname()[1])
    finally:
        sock.close()


def test_server_command_has_port_and_no_host() -> None:
    cmd = run.server_command(Path("/v/bin/python"), 8766)
    assert cmd[1:] == ["-m", "app", "--port", "8766"]
    assert not any("host" in part for part in cmd)


# ---------------------------------------------------------------- health 판정 (D-34)


def _serve(status: int, body: object):
    payload = json.dumps(body).encode()

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args) -> None:
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


@pytest.mark.parametrize(
    "status,body,expected",
    [
        (200, {"data": {"status": "ok", "app": "aidlc-monitor"}}, True),
        (200, {"data": {"status": "ok", "app": "something-else"}}, False),
        (200, {"status": "ok"}, False),
        (400, {"error": {"code": "BAD_HOST", "message": "x"}}, False),  # 포트 불일치
        (200, ["not", "a", "dict"], False),
    ],
)
def test_is_our_server(status: int, body: object, expected: bool) -> None:
    server = _serve(status, body)
    try:
        assert run.is_our_server(server.server_address[1], timeout=2.0) is expected
    finally:
        server.shutdown()
        server.server_close()


def test_is_our_server_nothing_listening() -> None:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    assert run.is_our_server(port, timeout=0.5) is False


# ---------------------------------------------------------------- dist 신선도 (ADR-005 §4)


def _frontend(tmp_path: Path) -> Path:
    fe = tmp_path / "frontend"
    (fe / "src").mkdir(parents=True)
    (fe / "package.json").write_text("{}", encoding="utf-8")
    (fe / "index.html").write_text("<div id=app></div>\n", encoding="utf-8")
    (fe / "package-lock.json").write_text("{}\n", encoding="utf-8")
    (fe / "src" / "main.ts").write_text("console.log(1)\n", encoding="utf-8")
    return fe


def test_dist_check_without_frontend_is_graceful(tmp_path: Path) -> None:
    code, message = dist.check(tmp_path / "frontend")
    assert code == 0 and "no dist yet" in message


def test_dist_check_missing_dist_fails(tmp_path: Path) -> None:
    code, _ = dist.check(_frontend(tmp_path))
    assert code == 1


def test_dist_check_roundtrip_and_staleness(tmp_path: Path) -> None:
    fe = _frontend(tmp_path)
    (fe / "dist").mkdir()
    (fe / "dist" / "index.html").write_text("built", encoding="utf-8")
    assert dist.check(fe)[0] == 1  # 메타 없음
    dist.write_meta(fe)
    assert dist.check(fe)[0] == 0
    (fe / "src" / "main.ts").write_bytes(
        b"console.log(1)\r\n"
    )  # CRLF 만 다름 → 같은 해시
    assert dist.check(fe)[0] == 0
    (fe / "src" / "main.ts").write_text("console.log(2)\n", encoding="utf-8")
    assert dist.check(fe)[0] == 1
    dist.write_meta(fe)
    (fe / "src" / "extra.ts").write_text("", encoding="utf-8")  # 파일 추가도 감지
    assert dist.check(fe)[0] == 1


def test_dist_check_corrupt_meta(tmp_path: Path) -> None:
    fe = _frontend(tmp_path)
    (fe / "dist").mkdir()
    (fe / "dist" / "index.html").write_text("built", encoding="utf-8")
    (fe / "dist" / ".build-meta.json").write_text("{not json", encoding="utf-8")
    assert dist.check(fe)[0] == 1


def test_old_python_exits_without_side_effects(monkeypatch, capsys) -> None:
    """AC-7: 3.10 이하면 안내 후 0 이 아닌 코드, 가상환경을 만들지 않는다."""
    monkeypatch.setattr(run, "python_ok", lambda version=None: False)

    def _fail(*args, **kwargs):
        raise AssertionError("venv 를 만들면 안 된다")

    monkeypatch.setattr(run, "ensure_venv", _fail)
    assert run.main(["--no-browser"]) == 1
    err = capsys.readouterr().err
    assert "Python 3.11 이상이 필요합니다" in err
    assert "Traceback" not in err
