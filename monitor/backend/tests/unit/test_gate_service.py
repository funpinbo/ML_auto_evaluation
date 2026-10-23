"""Gate 서비스 (ADR-009 §5): 출력 파싱, timeout, TTL 캐시, check 외 서브커맨드 금지."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from app.services.gates import GateService, RunOutput, parse_output, subprocess_runner

PASS_OUT = "OK    user/01.md  (0개 미작성)\n\nGATE PASS — user layer: 미작성 0개, 누락 문서 0개\n"
FAIL_OUT = (
    "MISSING  project/10-business-analysis.md\nTODO  project/00-interpretation.md  (2개 미작성)\n"
    "        L3: {{x}}\n\nGATE FAIL — project layer: 미작성 2개, 누락 문서 1개\n"
)


def test_parse_pass_fail_missing_target_and_garbage() -> None:
    ok = parse_output("user", RunOutput(0, PASS_OUT), "t")
    assert (ok.result, ok.unwritten, ok.missing, ok.no_documents) == (
        "PASS",
        0,
        0,
        False,
    )
    fail = parse_output("project", RunOutput(1, FAIL_OUT), "t")
    assert (fail.result, fail.unwritten, fail.missing) == ("FAIL", 2, 1)
    assert fail.file_unwritten == {"project/00-interpretation.md": 2}
    empty = parse_output(
        "docs",
        RunOutput(0, "\nGATE PASS — docs layer: 미작성 0개, 누락 문서 0개\n"),
        "t",
    )
    assert empty.no_documents is True
    missing = parse_output(
        "docs", RunOutput(1, "docs 가 없습니다. /aidlc-docs 을 먼저 실행하세요.\n"), "t"
    )
    assert (
        missing.result == "FAIL"
        and missing.target_missing
        and missing.unwritten is None
    )
    garbage = parse_output(
        "user", RunOutput(1, "Traceback ...\nUnicodeDecodeError\n"), "t"
    )
    assert (
        garbage.result == "UNKNOWN" and garbage.error_code.value == "SOURCE_PARSE_ERROR"
    )


def _root(tmp_path: Path) -> Path:
    script = tmp_path / "aidlc" / "scripts" / "aidlc.py"
    script.parent.mkdir(parents=True)
    script.write_text("# fake\n", encoding="utf-8")
    (tmp_path / "workspace" / "user").mkdir(parents=True)
    return tmp_path


def test_ttl_cache_and_signature_invalidation(tmp_path: Path) -> None:
    root = _root(tmp_path)
    calls: list[list[str]] = []
    now = [100.0]

    def runner(argv, cwd, timeout):
        calls.append(argv)
        return RunOutput(0, PASS_OUT)

    svc = GateService(runner=runner, clock=lambda: now[0])
    svc.check(root, "user")
    now[0] += 4.9
    svc.check(root, "user")
    assert len(calls) == 1  # TTL 안 + 서명 같음 → 재사용
    (root / "workspace" / "user" / "new.md").write_text("x", encoding="utf-8")
    svc.check(root, "user")
    assert len(calls) == 2  # 대상 변경 → 재실행
    now[0] += 5.1
    svc.check(root, "user")
    assert len(calls) == 3  # TTL 만료
    assert all(a[2:] == ["check", "user"] for a in calls)


def test_timeout_and_oserror_and_missing_script(tmp_path: Path) -> None:
    root = _root(tmp_path)

    def slow(argv, cwd, timeout):
        raise subprocess.TimeoutExpired(argv, timeout)

    def broken(argv, cwd, timeout):
        raise OSError("no exec")

    assert (
        GateService(runner=slow).check(root, "user").error_code.value == "GATE_TIMEOUT"
    )
    assert (
        GateService(runner=broken).check(root, "user").error_code.value
        == "SOURCE_UNREADABLE"
    )
    assert (
        GateService().check(tmp_path / "nope", "docs").error_code.value
        == "SOURCE_MISSING"
    )
    with pytest.raises(ValueError):
        GateService().check(root, "status")


def test_default_runner_refuses_non_check(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        subprocess_runner(["python", "aidlc.py", "status"], tmp_path, 1.0)


def test_default_runner_real_timeout(tmp_path: Path) -> None:
    script = tmp_path / "slow.py"
    script.write_text("import time; time.sleep(5)\n", encoding="utf-8")
    import sys

    with pytest.raises(subprocess.TimeoutExpired):
        subprocess_runner([sys.executable, str(script), "check", "user"], tmp_path, 0.3)
