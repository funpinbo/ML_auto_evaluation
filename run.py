#!/usr/bin/env python3
"""AI-DLC Monitor 원클릭 실행 (SCOPE-01, ADR-001). 표준 라이브러리만 쓴다.

    python run.py [--port N] [--no-browser]

순서: Python 3.11+ 확인 → `monitor/.venv` 준비(없을 때만) → requirements 해시 마커가 다르면
`pip install -r monitor/backend/requirements.txt` → 포트 선택(기본 8765, `AIDLC_MONITOR_PORT`,
`--port` 가 우선. 사용 중이면 `/api/v1/health` 로 자기 서버인지 확인 → 자기 서버면 브라우저만 열고
끝, 아니면 다음 포트) → `python -m app --port N`(127.0.0.1 고정, D-19·D-32) → health 200 대기
(최대 20 s) → 브라우저 → Ctrl+C 로 종료.

호스트를 바꾸는 옵션은 없다(QS-05, NFR-003). 쓰기는 `monitor/.venv` 와 그 안의 해시 마커뿐이다
(pip 캐시도 쓰지 않는다, 02 §11·AC-14).

이 파일은 오래된 Python 에서도 "3.11 이상 필요" 안내를 낼 수 있게 3.7 문법까지만 쓴다.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

MIN_PYTHON = (3, 11)
APP_ID = "aidlc-monitor"
BIND_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
PORT_ENV = "AIDLC_MONITOR_PORT"
PORT_ATTEMPTS = 10  # ADR-001 §2.4: 사용 중이면 다음 포트, 최대 10개
HEALTH_TIMEOUT_S = 20.0
HEALTH_PATH = "/api/v1/health"
STOP_GRACE_S = 5.0
# 정상 종료로 보는 서버 종료 코드: uvicorn 은 정상 종료 뒤 받은 신호를 다시 올려 -SIGINT/-SIGTERM 으로
# 끝난다. 130/143 = 셸 표기, 3221225786 = Windows STATUS_CONTROL_C_EXIT.
_STOP_CODES = frozenset({0, -signal.SIGINT, -signal.SIGTERM, 130, 143, 3221225786})

REPO = Path(__file__).resolve().parent
MONITOR = REPO / "monitor"
BACKEND = MONITOR / "backend"
VENV = MONITOR / ".venv"
REQUIREMENTS = BACKEND / "requirements.txt"
MARKER_NAME = ".requirements.sha256"

PYTHON_HELP = "https://www.python.org/downloads/ 에서 Python 3.11 이상을 설치한 뒤 다시 실행하세요."


class LaunchError(Exception):
    """사용자에게 원인 한 줄 + 다음 행동 한 줄로 보여 줄 실패."""

    def __init__(self, message: str, hint: str = "", code: int = 1) -> None:
        super().__init__(message)
        self.hint = hint
        self.code = code


def say(message: str) -> None:
    print(f"[monitor] {message}", flush=True)


# ---------------------------------------------------------------- Python / venv


def python_ok(version: tuple[int, ...] | None = None) -> bool:
    return tuple(version if version is not None else sys.version_info[:2]) >= MIN_PYTHON


def venv_python(venv_dir: Path, windows: bool | None = None) -> Path:
    windows = (os.name == "nt") if windows is None else windows
    if windows:
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def _runs(cmd: list[str], timeout: float = 60.0) -> bool:
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def venv_usable(vpy: Path) -> bool:
    """venv 의 python 이 실제로 실행되고 3.11+ 인지 (옮겨진·깨진 venv 를 걸러낸다)."""
    if not vpy.is_file():
        return False
    check = "import sys; sys.exit(sys.version_info[:2] < (3, 11))"
    return _runs([str(vpy), "-c", check])


def ensure_venv(venv_dir: Path) -> Path:
    import shutil
    import venv

    vpy = venv_python(venv_dir)
    if venv_usable(vpy):
        say("가상환경 준비 — 기존 monitor/.venv 사용")
        return vpy
    say("가상환경 준비 — monitor/.venv 생성 중")
    try:
        venv.EnvBuilder(with_pip=True, clear=venv_dir.exists()).create(str(venv_dir))
    except (OSError, subprocess.CalledProcessError) as exc:
        shutil.rmtree(
            venv_dir, ignore_errors=True
        )  # 반쯤 만든 venv 는 다음 실행에서 다시 만든다
        raise LaunchError(
            f"가상환경을 만들지 못했습니다: {type(exc).__name__}: {exc}",
            "Debian/Ubuntu 는 python3-venv 패키지가 필요합니다 (sudo apt install python3-venv).",
        ) from None
    if not venv_usable(vpy):
        shutil.rmtree(venv_dir, ignore_errors=True)
        raise LaunchError(
            "가상환경의 Python 을 실행하지 못했습니다.",
            "monitor/.venv 를 지우고 다시 실행하세요.",
        )
    return vpy


# ---------------------------------------------------------------- 설치 (해시 마커)


def requirements_digest(requirements: Path) -> str:
    """requirements 파일 바이트의 sha256. 한 글자라도 바뀌면 재설치한다(AC-6)."""
    return hashlib.sha256(requirements.read_bytes()).hexdigest()


def marker_path(venv_dir: Path) -> Path:
    return venv_dir / MARKER_NAME


def install_needed(venv_dir: Path, requirements: Path) -> bool:
    marker = marker_path(venv_dir)
    try:
        recorded = marker.read_text(encoding="ascii").strip()
    except (OSError, UnicodeDecodeError):
        return True
    return recorded != requirements_digest(requirements)


def _pip_env() -> dict[str, str]:
    env = dict(os.environ)
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    env["PIP_NO_INPUT"] = "1"
    # requirements.txt 의 한글 주석에 BOM/인코딩 선언이 없어, 로케일이 cp949 인 Windows 에서
    # pip 가 시스템 로케일로 디코딩을 시도해 UnicodeDecodeError 가 난다. UTF-8 모드를 강제한다.
    env["PYTHONUTF8"] = "1"
    env.pop("PIP_USER", None)  # venv 밖(사용자 site)으로 설치되지 않게
    env.pop("PYTHONHOME", None)
    return env


def install_requirements(vpy: Path, venv_dir: Path, requirements: Path) -> None:
    marker = marker_path(venv_dir)
    digest = requirements_digest(requirements)
    try:
        marker.unlink()  # 설치 도중 실패하면 마커가 없어 다음 실행에서 다시 설치한다(AC-8)
    except FileNotFoundError:
        pass
    env = _pip_env()
    if not _runs([str(vpy), "-m", "pip", "--version"]):
        _runs([str(vpy), "-m", "ensurepip", "--default-pip"], timeout=300)
    cmd = [
        str(vpy),
        "-m",
        "pip",
        "install",
        "--no-cache-dir",  # 사용자 전역 pip 캐시에 쓰지 않는다(AC-14)
        "--progress-bar",
        "off",
        "-r",
        str(requirements),
    ]
    tail: collections.deque[str] = collections.deque(maxlen=30)
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as exc:
        raise LaunchError(
            f"pip 를 실행하지 못했습니다: {exc}",
            "monitor/.venv 를 지우고 다시 실행하세요.",
        ) from None
    assert proc.stdout is not None
    for line in proc.stdout:
        line = line.rstrip()
        tail.append(line)
        print(f"  {line}", flush=True)
    code = proc.wait()
    if code != 0:
        errors = [ln for ln in tail if "ERROR" in ln or "error" in ln.lower()]
        summary = (errors or list(tail) or ["(출력 없음)"])[-3:]
        raise LaunchError(
            "패키지 설치에 실패했습니다: " + " / ".join(s.strip() for s in summary),
            "인터넷 연결(PyPI 접속)을 확인한 뒤 다시 실행하세요. 다음 실행에서 설치를 다시 시도합니다.",
        )
    marker.write_text(digest + "\n", encoding="ascii")


# ---------------------------------------------------------------- 포트


def parse_port(raw: str) -> int:
    """app.config.parse_port 와 같은 규칙: 10진수, 선행 0 없음, 1~65535 (포트 0 금지, D-19·D-32)."""
    text = raw.strip()
    if not text.isdigit() or (len(text) > 1 and text.startswith("0")):
        raise ValueError("port must be a decimal integer without leading zeros")
    value = int(text)
    if not 1 <= value <= 65535:
        raise ValueError("port must be between 1 and 65535")
    return value


def requested_port(cli_port: int | None, env: dict[str, str] | os._Environ[str]) -> int:
    if cli_port is not None:
        return cli_port
    raw = env.get(PORT_ENV)
    if not raw:
        return DEFAULT_PORT
    try:
        return parse_port(raw)
    except ValueError:
        raise LaunchError(
            f"{PORT_ENV}={raw!r} 는 올바른 포트가 아닙니다.",
            "1~65535 사이 10진수(선행 0 없음)로 바꾸거나 환경 변수를 지우세요.",
            code=2,
        ) from None


def port_free(port: int, host: str = BIND_HOST) -> bool:
    """uvicorn 이 바인딩할 수 있는지 미리 본다."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if os.name != "nt":
            # uvicorn 과 같은 옵션. Windows 의 SO_REUSEADDR 는 남의 포트를 빼앗을 수 있어 쓰지 않는다.
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, port))
    except OSError:
        return False
    finally:
        sock.close()
    return True


def probe_health(port: int, timeout: float = 2.0) -> dict | None:
    """`GET http://127.0.0.1:<port>/api/v1/health` 의 envelope `data`. 실패하면 None.

    HTTP 200 이 아니면(예: 400 BAD_HOST = 다른 포트로 뜬 서버, D-34) None 이다.
    """
    url = f"http://{BIND_HOST}:{port}{HEALTH_PATH}"
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # 프록시 우회
    try:
        with opener.open(url, timeout=timeout) as resp:
            if resp.status != 200:
                return None
            body = json.loads(resp.read(65536).decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError):
        return None
    data = body.get("data") if isinstance(body, dict) else None
    return data if isinstance(data, dict) else None


def is_our_server(port: int, timeout: float = 2.0) -> bool:
    data = probe_health(port, timeout=timeout)
    return data is not None and data.get("app") == APP_ID


def choose_port(
    start: int, attempts: int = PORT_ATTEMPTS, free=port_free, ours=is_our_server
):
    """(동작, 포트). 동작 = "start"(빈 포트) | "running"(이미 Monitor 가 실행 중)."""
    for port in range(start, min(start + attempts, 65536)):
        if free(port):
            return "start", port
        if ours(port):
            return "running", port
        say(f"포트 {port} 는 다른 프로그램이 사용 중 — 다음 포트 시도")
    last = min(start + attempts, 65536) - 1
    raise LaunchError(
        f"사용할 수 있는 포트가 없습니다 ({start}~{last} 모두 사용 중).",
        f"--port 또는 {PORT_ENV} 로 다른 포트를 지정하세요.",
    )


# ---------------------------------------------------------------- 서버


def server_command(vpy: Path, port: int) -> list[str]:
    """호스트 옵션은 넘기지 않는다 — 서버가 127.0.0.1 상수로 바인딩한다(app/config.py BIND_HOST)."""
    return [str(vpy), "-m", "app", "--port", str(port)]


def start_server(vpy: Path, port: int) -> subprocess.Popen:
    env = dict(os.environ)
    env.pop(PORT_ENV, None)  # --port 가 단일 출처(D-19)
    env.pop("PYTHONHOME", None)
    kwargs: dict = {"cwd": str(BACKEND), "env": env}
    return subprocess.Popen(server_command(vpy, port), **kwargs)


def wait_healthy(
    proc: subprocess.Popen, port: int, timeout: float = HEALTH_TIMEOUT_S
) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise LaunchError(
                f"서버가 시작되지 않았습니다 (종료 코드 {proc.returncode}). 원인은 위 콘솔 로그를 보세요.",
                "문제가 계속되면 monitor/.venv 를 지우고 다시 실행하세요.",
            )
        if is_our_server(port, timeout=1.0):
            return
        time.sleep(0.25)
    raise LaunchError(
        f"서버가 시작되지 않았습니다 ({int(timeout)}초 안에 health 200 없음). 원인은 위 콘솔 로그를 보세요.",
        "다른 포트(--port)로 다시 실행해 보세요.",
    )


def stop_server(proc: subprocess.Popen, grace: float = STOP_GRACE_S) -> int:
    """Ctrl+C 는 콘솔이 자식에게도 보내므로 먼저 기다리고, 안 끝나면 terminate → kill."""
    try:
        return proc.wait(timeout=grace)
    except subprocess.TimeoutExpired:
        pass
    proc.terminate()
    try:
        return proc.wait(timeout=grace)
    except subprocess.TimeoutExpired:
        proc.kill()
        return proc.wait()


def open_browser(url: str) -> None:
    import webbrowser

    say(f"브라우저 열기 {url}")
    try:
        if not webbrowser.open(url):
            say(f"브라우저를 열지 못했습니다 — 주소를 직접 여세요: {url}")
    except Exception:  # noqa: BLE001 - 브라우저 실패로 서버를 멈추지 않는다
        say(f"브라우저를 열지 못했습니다 — 주소를 직접 여세요: {url}")


# ---------------------------------------------------------------- main


def _cli_port(raw: str) -> int:
    try:
        return parse_port(raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from None


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="run.py", description="AI-DLC Monitor 를 설치·실행하고 브라우저로 엽니다."
    )
    parser.add_argument(
        "--port", type=_cli_port, default=None, help=f"기본 {DEFAULT_PORT}"
    )
    parser.add_argument(
        "--no-browser", action="store_true", help="브라우저를 열지 않는다"
    )
    return parser.parse_args(argv)


def _configure_console() -> None:
    """한글을 못 쓰는 콘솔(인코딩)에서도 트레이스백 없이 출력한다."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(errors="replace")
        except ValueError:
            pass


def run(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    say(f"Python 확인 — {sys.version.split()[0]} ({sys.executable})")
    if not REQUIREMENTS.is_file():
        raise LaunchError(
            f"{REQUIREMENTS.relative_to(REPO)} 가 없습니다.",
            "저장소를 다시 내려받으세요.",
        )
    start = requested_port(args.port, os.environ)

    vpy = ensure_venv(VENV)
    if install_needed(VENV, REQUIREMENTS):
        say("패키지 설치 — monitor/backend/requirements.txt (처음 한 번, 1~2분)")
        install_requirements(vpy, VENV, REQUIREMENTS)
    else:
        say("설치 생략 — requirements 변경 없음")

    action, port = choose_port(start)
    url = f"http://{BIND_HOST}:{port}/"
    if action == "running":
        say(f"이미 실행 중 {url}")
        if not args.no_browser:
            open_browser(url)
        return 0

    say(f"서버 시작 {url}")
    proc = start_server(vpy, port)
    stopping = {"flag": False}

    def _on_term(signum, frame):  # signal 핸들러 시그니처
        stopping["flag"] = True
        raise KeyboardInterrupt

    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _on_term)
    try:
        wait_healthy(proc, port)
        say(f"준비 완료 {url} (종료: Ctrl+C)")
        if not args.no_browser:
            open_browser(url)
        code = proc.wait()
        return 0 if code in _STOP_CODES else code
    except KeyboardInterrupt:
        say("종료 중…")
        if stopping["flag"] and proc.poll() is None:
            proc.terminate()  # SIGTERM 은 런처에만 왔으므로 자식에게 전달
        code = stop_server(proc)
        say("서버를 종료했습니다.")
        return 0 if code in _STOP_CODES else code
    except LaunchError:
        if proc.poll() is None:
            proc.terminate()
            stop_server(proc, grace=5.0)
        raise


def main(argv: list[str] | None = None) -> int:
    _configure_console()
    if not python_ok():
        found = ".".join(str(n) for n in sys.version_info[:3])
        print(
            f"[monitor] Python 3.11 이상이 필요합니다 (현재 {found}).", file=sys.stderr
        )
        print(f"[monitor] {PYTHON_HELP}", file=sys.stderr)
        return 1
    try:
        return run(argv)
    except LaunchError as exc:
        print(f"[monitor] 오류: {exc}", file=sys.stderr)
        if exc.hint:
            print(f"[monitor] {exc.hint}", file=sys.stderr)
        return exc.code
    except KeyboardInterrupt:
        print("[monitor] 중단했습니다.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
