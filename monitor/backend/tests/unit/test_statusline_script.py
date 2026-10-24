"""status line 스크립트 `aidlc/hooks/statusline.{sh,py}` (ADR-003 Decision 2·3, privacy P-23·P-24·P-31).

스크립트를 임시 저장소 사본(`<tmp>/repo/aidlc/hooks/`)에 복사해 서브프로세스로 실행한다. 스크립트는 자기 위치
기준 저장소 루트에 쓰므로 실제 저장소 workspace 는 건드리지 않는다. HOME 은 임시 경로, CLAUDE_CONFIG_DIR 은
지운다(실제 `~/.claude` 를 읽지 않음, D-16).
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest
from fixtures import markers
from fixtures.contracts import schema_errors
from usage_support import walk_values

REPO_ROOT = Path(__file__).resolve().parents[4]
HOOKS = REPO_ROOT / "aidlc" / "hooks"
BASH = shutil.which("bash")

STDIN: dict[str, Any] = {
    "session_id": f"{markers.SESSION}-1",
    "transcript_path": f"/home/{markers.PATH}/.claude/projects/-home-fake-project/{markers.UUID}.jsonl",
    "cwd": f"/home/{markers.CWD}/project",
    "workspace": {"current_dir": f"/{markers.CWD}", "project_dir": f"/{markers.PATH}"},
    "model": {"id": "claude-fake-opus", "display_name": markers.EXTRA},
    "version": "2.1.0",
    "output_style": {"name": markers.EXTRA},
    "rate_limits": {
        "five_hour": {"used_percentage": 42.5, "resets_at": 1792742400},
        "seven_day": {"used_percentage": 17.5, "resets_at": 1793174400.0},
    },
    "cost": {
        "total_cost_usd": 1.234,
        "total_duration_ms": 345000,
        "total_lines_added": 5,
    },
    "context_window": {
        "used_percentage": 8,
        "context_window_size": 200000,
        "current_usage": {"x": 1},
    },
    "extra": markers.BODY,
}


class Env:
    def __init__(self, tmp: Path) -> None:
        self.repo = tmp / "repo"
        self.hooks = self.repo / "aidlc" / "hooks"
        self.hooks.mkdir(parents=True)
        for name in ("statusline.sh", "statusline.py"):
            shutil.copy2(HOOKS / name, self.hooks / name)
        self.memory = self.repo / "workspace" / "memory"
        self.memory.mkdir(parents=True)
        self.snapshot = self.memory / ".monitor" / "claude-status.json"
        self.home = tmp / "home"
        (self.home / ".claude").mkdir(parents=True)

    def set_global(self, status_line: object, extra: dict | None = None) -> None:
        doc = {
            "statusLine": status_line,
            "env": {"TOKEN": markers.SETTINGS},
            **(extra or {}),
        }
        (self.home / ".claude" / "settings.json").write_text(
            json.dumps(doc), encoding="utf-8"
        )

    def env(self, **extra: str) -> dict[str, str]:
        env = {
            k: v
            for k, v in os.environ.items()
            if k not in ("CLAUDE_CONFIG_DIR", "CLAUDE_HOME", "AIDLC_ROOT")
        }
        env.update(
            HOME=str(self.home), USERPROFILE=str(self.home), PYTHONDONTWRITEBYTECODE="1"
        )
        env.update(extra)
        return env

    def run(
        self,
        stdin: bytes | dict,
        *,
        via_bash: bool = False,
        env: dict | None = None,
        timeout: float = 15,
    ):
        data = stdin if isinstance(stdin, bytes) else json.dumps(stdin).encode()
        if via_bash:
            cmd = [BASH, str(self.hooks / "statusline.sh")]
        else:
            cmd = [sys.executable, str(self.hooks / "statusline.py")]
        start = time.monotonic()
        proc = subprocess.run(
            cmd,
            input=data,
            capture_output=True,
            env=env or self.env(),
            timeout=timeout,
            check=False,
        )
        return proc, time.monotonic() - start


@pytest.fixture
def sl(tmp_path) -> Env:
    return Env(tmp_path)


def _snapshot(sl: Env) -> dict:
    return json.loads(sl.snapshot.read_text(encoding="utf-8"))


def test_snapshot_whitelist_and_schema(sl) -> None:
    proc, _ = sl.run(STDIN)
    assert proc.returncode == 0
    doc = _snapshot(sl)
    assert schema_errors(doc, "claude-status") == []
    assert (
        doc["session_hash"]
        == hashlib.sha256(STDIN["session_id"].encode()).hexdigest()[:12]
    )
    assert doc["transcript_dir_name"] == "-home-fake-project"
    assert doc["model_id"] == "claude-fake-opus" and doc["claude_version"] == "2.1.0"
    assert (
        doc["rate_limits"]["seven_day"]["resets_at"] == 1793174400
    )  # 정수 float → int
    assert doc["cost"] == {"total_cost_usd": 1.234, "total_duration_ms": 345000}
    assert doc["context_window"] == {
        "used_percentage": 8,
        "context_window_size": 200000,
    }
    raw = sl.snapshot.read_text(encoding="utf-8")
    markers.assert_no_markers(raw, *walk_values(doc), where="snapshot")
    assert proc.stdout.decode().strip().endswith("AI-DLC 5h 43% · 7d 18% · $1.23")
    assert proc.stderr == b""


def test_runs_through_bash_launcher(sl) -> None:
    if BASH is None:
        pytest.skip("bash 없음")
    proc, _ = sl.run(STDIN, via_bash=True)
    assert proc.returncode == 0 and b"AI-DLC 5h 43%" in proc.stdout
    assert _snapshot(sl)["schema"] == 1


def test_bash_launcher_without_python_prints_empty_line(sl) -> None:
    if BASH is None:
        pytest.skip("bash 없음")
    empty = sl.repo / "empty-bin"
    empty.mkdir()
    proc, _ = sl.run(STDIN, via_bash=True, env=sl.env(PATH=str(empty)))
    assert proc.returncode == 0 and proc.stdout == b"\n"
    assert not sl.snapshot.exists()


def test_launcher_is_lf_and_executable() -> None:
    data = (HOOKS / "statusline.sh").read_bytes()
    assert b"\r\n" not in data and data.startswith(b"#!/usr/bin/env bash\n")
    assert b"\r\n" not in (HOOKS / "statusline.py").read_bytes()


def test_no_rate_limits_shows_context(sl) -> None:
    data = {k: v for k, v in STDIN.items() if k not in ("rate_limits", "cost")}
    proc, _ = sl.run(data)
    doc = _snapshot(sl)
    assert doc["rate_limits"] is None and doc["cost"] is None
    assert schema_errors(doc, "claude-status") == []
    assert proc.stdout.decode().strip() == "AI-DLC ctx 8%"


@pytest.mark.parametrize(
    "path",
    [
        None,
        "",
        "s.jsonl",
        "/a/../s.jsonl",
        "/a/b c/s.jsonl",
        "C:\\Users\\x\\-proj\\s.jsonl",
    ],
)
def test_transcript_dir_name_only_one_valid_segment(sl, path) -> None:
    data = dict(STDIN, transcript_path=path)
    sl.run(data)
    doc = _snapshot(sl)
    expected = {"C:\\Users\\x\\-proj\\s.jsonl": "-proj"}.get(path)
    assert doc["transcript_dir_name"] == expected
    assert schema_errors(doc, "claude-status") == []


def test_odd_values_are_nulled_not_stored(sl) -> None:
    data = dict(
        STDIN,
        session_id=7,
        version="v" * 100,
        model={"id": ["x"]},
        rate_limits={
            "five_hour": {"used_percentage": 140, "resets_at": -1},
            "seven_day": "x",
        },
        cost={"total_cost_usd": True, "total_duration_ms": 1.5},
        context_window={"used_percentage": "8", "context_window_size": -3},
    )
    proc, _ = sl.run(data)
    doc = _snapshot(sl)
    assert schema_errors(doc, "claude-status") == []
    assert (
        doc["session_hash"] is None
        and doc["claude_version"] is None
        and doc["model_id"] is None
    )
    assert doc["rate_limits"] == {
        "five_hour": {"used_percentage": None, "resets_at": None},
        "seven_day": None,
    }
    assert proc.stdout.decode().strip() == "AI-DLC"


def test_atomic_replace_leaves_no_temp_files(sl) -> None:
    sl.run(STDIN)
    first = sl.snapshot.stat().st_ino
    sl.run(dict(STDIN, version="2.2.0"))
    assert _snapshot(sl)["claude_version"] == "2.2.0"
    assert sl.snapshot.stat().st_ino != first  # 제자리 쓰기가 아니라 교체
    assert sorted(p.name for p in sl.snapshot.parent.iterdir()) == [
        "claude-status.json"
    ]


def test_broken_stdin_exits_zero_without_snapshot(sl) -> None:
    for payload in (b"{not json", b"", b"[1,2]", b"\xff\xfe"):
        proc, _ = sl.run(payload)
        assert proc.returncode == 0 and proc.stdout.decode().strip() == "AI-DLC"
    assert not sl.snapshot.exists()


def test_write_error_still_exits_zero(sl) -> None:
    (sl.memory / ".monitor").write_text("not a dir", encoding="utf-8")
    proc, _ = sl.run(STDIN)
    assert (
        proc.returncode == 0 and b"AI-DLC 5h 43%" in proc.stdout and proc.stderr == b""
    )


def test_no_workspace_memory_no_write(sl) -> None:
    shutil.rmtree(sl.repo / "workspace")
    proc, _ = sl.run(STDIN)
    assert proc.returncode == 0 and not (sl.repo / "workspace").exists()


# ---------------------------------------------------------------- 체이닝 (P-23·P-24)
def _py_cmd(code: str) -> str:
    return f'"{sys.executable}" -c "{code}"'


def test_chains_global_command_with_same_stdin(sl) -> None:
    sl.set_global(
        {
            "type": "command",
            "command": _py_cmd(
                "import sys,hashlib;print('GLOBAL', hashlib.sha256(sys.stdin.buffer.read()).hexdigest()[:8])"
            ),
        }
    )
    data = json.dumps(STDIN).encode()
    proc, _ = sl.run(data)
    lines = proc.stdout.decode().splitlines()
    assert lines[0] == f"GLOBAL {hashlib.sha256(data).hexdigest()[:8]}"
    assert lines[-1].startswith("AI-DLC 5h 43%")
    assert markers.SETTINGS not in sl.snapshot.read_text(encoding="utf-8")


def test_chained_output_comes_after_snapshot_is_saved(sl) -> None:
    probe = sl.repo / "seen.txt"
    snap = str(sl.snapshot).replace("\\", "/")
    sl.set_global(
        {
            "type": "command",
            "command": _py_cmd(
                f"import os;open(r'{probe}','w').write(str(os.path.exists(r'{snap}')))"
            ),
        }
    )
    sl.run(STDIN)
    assert probe.read_text() == "True"


def test_chain_timeout_2s_kills_group(sl) -> None:
    sl.set_global(
        {
            "type": "command",
            "command": _py_cmd("import time;print('late');time.sleep(30)"),
        }
    )
    proc, elapsed = sl.run(STDIN)
    assert proc.returncode == 0
    assert elapsed < 6, f"{elapsed:.1f}s"
    assert b"late" not in proc.stdout and b"AI-DLC 5h 43%" in proc.stdout


def _pids_matching(pattern: str) -> list[int]:
    found: list[int] = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            cmd = (entry / "cmdline").read_bytes().replace(b"\0", b" ").decode()
        except OSError:
            continue
        if pattern in cmd:
            found.append(int(entry.name))
    return found


@pytest.mark.skipif(not Path("/proc").is_dir() or os.name == "nt", reason="/proc 필요")
def test_chain_timeout_kills_grandchildren(sl, request) -> None:
    """qa 변이: killpg → proc.kill() 이면 손자(sleep)가 파이프를 잡아 늦어지고 남는다."""
    tag = f"{os.getpid() % 1000:03d}{int(time.time()) % 1000:03d}"
    a, b = f"6{tag}1", f"6{tag}2"

    def cleanup() -> None:
        for pid in _pids_matching(f"sleep {a}") + _pids_matching(f"sleep {b}"):
            try:
                os.kill(pid, 9)
            except OSError:
                pass

    request.addfinalizer(cleanup)
    sl.set_global({"type": "command", "command": f"sleep {a} & sleep {b}; wait"})
    proc, elapsed = sl.run(STDIN)
    assert proc.returncode == 0 and b"AI-DLC 5h 43%" in proc.stdout
    assert elapsed < 2.8, f"{elapsed:.2f}s"
    deadline = time.monotonic() + 1.0
    left = _pids_matching(f"sleep {a}") + _pids_matching(f"sleep {b}")
    while left and time.monotonic() < deadline:
        time.sleep(0.05)
        left = _pids_matching(f"sleep {a}") + _pids_matching(f"sleep {b}")
    assert left == [], "남은 손자 프로세스"


def test_self_reference_is_skipped(sl) -> None:
    probe = sl.repo / "ran.txt"
    sl.set_global(
        {
            "type": "command",
            "command": _py_cmd(f"open(r'{probe}','w')")
            + " # aidlc/hooks/statusline.sh",
        }
    )
    proc, _ = sl.run(STDIN)
    assert not probe.exists() and proc.stdout.decode().strip().startswith("AI-DLC")


@pytest.mark.parametrize(
    "status_line",
    [
        None,
        "echo x",
        {"type": "static", "command": "echo x"},
        {"type": "command", "command": 5},
        {"type": "command", "command": "  "},
    ],
)
def test_unusable_global_status_line_is_ignored(sl, status_line) -> None:
    sl.set_global(status_line)
    proc, _ = sl.run(STDIN)
    assert proc.returncode == 0 and proc.stdout.decode().splitlines() == [
        "AI-DLC 5h 43% · 7d 18% · $1.23"
    ]


def test_broken_global_settings_and_failing_command(sl) -> None:
    (sl.home / ".claude" / "settings.json").write_text("{broken", encoding="utf-8")
    assert sl.run(STDIN)[0].returncode == 0
    sl.set_global({"type": "command", "command": "exit 3"})
    proc, _ = sl.run(STDIN)
    assert proc.returncode == 0 and proc.stdout.decode().splitlines() == [
        "AI-DLC 5h 43% · 7d 18% · $1.23"
    ]


def test_claude_config_dir_is_respected(sl, tmp_path) -> None:
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    (cfg / "settings.json").write_text(
        json.dumps({"statusLine": {"type": "command", "command": "echo FROMCFG"}}),
        encoding="utf-8",
    )
    proc, _ = sl.run(STDIN, env=sl.env(CLAUDE_CONFIG_DIR=str(cfg)))
    assert proc.stdout.decode().splitlines()[0] == "FROMCFG"


def test_project_settings_register_status_line_only() -> None:
    settings = json.loads(
        (REPO_ROOT / ".claude" / "settings.json").read_text(encoding="utf-8")
    )
    assert settings["statusLine"] == {
        "type": "command",
        "command": 'bash "${CLAUDE_PROJECT_DIR:-.}/aidlc/hooks/statusline.sh"',
        "refreshInterval": 30,
    }
    assert set(settings) == {"hooks", "statusLine"}
    for event in ("SessionStart", "PostToolUse", "Stop", "PreCompact"):
        assert "aidlc/hooks/run.sh" in json.dumps(settings["hooks"][event])
