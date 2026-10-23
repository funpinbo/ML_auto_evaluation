#!/usr/bin/env python3
"""로컬 PR 게이트 — user/02 §10 공통 DoD 검사를 한 번에 실행한다 (원격 CI 없음, 01 §3). cicd 소유.

    python monitor/tools/check.py            # 전체
    python monitor/tools/check.py --build    # 프론트 npm run build 도 실행(dist 를 다시 쓴다)

검사는 끄지 않는다. 하나가 실패해도 나머지를 계속 돌리고 마지막에 요약한 뒤, 하나라도 FAIL 이면 exit 1.
SKIP 은 대상이 아직 없을 때만(예: monitor/frontend 가 생기기 전) 쓴다.

도구는 `monitor/.venv` 의 Python 으로 실행한다(없으면 지금 Python). 개발 의존성:
`monitor/.venv/bin/python -m pip install -r monitor/backend/requirements-dev.txt`.
"""

from __future__ import annotations

import argparse
import filecmp
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MONITOR = REPO / "monitor"
BACKEND = MONITOR / "backend"
FRONTEND = MONITOR / "frontend"
TOOLS = MONITOR / "tools"
PY_TARGETS = ["run.py", "monitor/backend", "monitor/tools"]
LAUNCHER_TYPED = [
    "--cache-dir",
    "monitor/.mypy_cache",
    "run.py",
    "monitor/tools/check.py",
    "monitor/tools/check_dist_fresh.py",
]


def tool_python() -> str:
    venv = MONITOR / ".venv"
    vpy = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    return str(vpy) if vpy.is_file() else sys.executable


@dataclass
class Result:
    name: str
    status: str  # PASS | FAIL | SKIP
    detail: str
    seconds: float


def run_step(name: str, cmd: list[str], cwd: Path) -> Result:
    print(
        f"\n=== {name}: {' '.join(cmd)}  (cwd={cwd.relative_to(REPO).as_posix() or '.'})",
        flush=True,
    )
    start = time.monotonic()
    try:
        code = subprocess.run(cmd, cwd=str(cwd), check=False).returncode
    except OSError as exc:
        return Result(name, "FAIL", f"실행 불가: {exc}", time.monotonic() - start)
    status = "PASS" if code == 0 else "FAIL"
    return Result(name, status, f"exit {code}", time.monotonic() - start)


def check_api_reference(py: str) -> Result:
    """docs/api/reference.md 가 openapi.json 에서 다시 만든 결과와 같은지 (CLAUDE.md: 직접 편집 금지)."""
    name = "API 레퍼런스 신선도"
    print(f"\n=== {name}", flush=True)
    start = time.monotonic()
    spec = REPO / "workspace" / "project" / "contracts" / "openapi.json"
    current = REPO / "docs" / "api" / "reference.md"
    if not spec.is_file():
        return Result(name, "SKIP", "openapi.json 없음", 0.0)
    with tempfile.TemporaryDirectory() as tmp:
        cmd = [
            py,
            str(REPO / "aidlc" / "scripts" / "openapi_docs.py"),
            "render",
            str(spec),
            "-o",
            tmp,
        ]
        proc = subprocess.run(
            cmd, cwd=str(REPO), capture_output=True, text=True, check=False
        )
        fresh = Path(tmp) / "reference.md"
        if proc.returncode != 0 or not fresh.is_file():
            return Result(
                name,
                "FAIL",
                f"렌더 실패 exit {proc.returncode}",
                time.monotonic() - start,
            )
        same = current.is_file() and filecmp.cmp(fresh, current, shallow=False)
    detail = "최신" if same else "다름 — openapi_docs.py render 로 재생성"
    print(detail)
    return Result(name, "PASS" if same else "FAIL", detail, time.monotonic() - start)


def frontend_steps(build: bool) -> list[tuple[str, list[str], Path]] | str:
    if not (FRONTEND / "package.json").is_file():
        return "monitor/frontend 없음 (T-012 전)"
    npm = shutil.which("npm")
    npx = shutil.which("npx")
    if not npm or not npx:
        return "npm 없음"
    steps = [
        ("frontend eslint", [npm, "run", "lint"], FRONTEND),
        ("frontend vue-tsc", [npx, "vue-tsc", "--noEmit"], FRONTEND),
        ("frontend vitest", [npm, "test"], FRONTEND),
    ]
    if build:
        steps.insert(0, ("frontend build", [npm, "run", "build"], FRONTEND))
    return steps


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="check.py")
    parser.add_argument(
        "--build", action="store_true", help="npm run build 를 먼저 실행"
    )
    args = parser.parse_args(argv)
    py = tool_python()
    results: list[Result] = []

    results.append(
        run_step(
            "ruff format --check",
            [py, "-m", "ruff", "format", "--check", *PY_TARGETS],
            REPO,
        )
    )
    results.append(
        run_step("ruff check", [py, "-m", "ruff", "check", *PY_TARGETS], REPO)
    )
    results.append(run_step("mypy (backend)", [py, "-m", "mypy"], BACKEND))
    results.append(
        run_step(
            "mypy (launcher/tools)",
            [py, "-m", "mypy", "--python-version", "3.11", *LAUNCHER_TYPED],
            REPO,
        )
    )
    results.append(
        run_step(
            "pytest backend (cov ≥ 70%)",
            [
                py,
                "-m",
                "pytest",
                "-q",
                "-p",
                "no:cacheprovider",
                "--cov",
                "--cov-report=term",
            ],
            BACKEND,
        )
    )
    results.append(
        run_step(
            "pytest launcher/tools",
            [py, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests"],
            TOOLS,
        )
    )
    fe = frontend_steps(args.build)
    if isinstance(fe, str):
        if fe == "npm 없음":
            results.append(
                Result(
                    "frontend lint/type/test",
                    "FAIL",
                    "monitor/frontend 가 있는데 npm 없음 — Node 설치 필요",
                    0.0,
                )
            )
        else:
            results.append(Result("frontend lint/type/test", "SKIP", fe, 0.0))
    else:
        for name, cmd, cwd in fe:
            results.append(run_step(name, cmd, cwd))
    results.append(
        run_step("dist 신선도", [py, str(TOOLS / "check_dist_fresh.py")], REPO)
    )
    results.append(
        run_step(
            "OpenAPI export diff", [py, "scripts/export_openapi.py", "--check"], BACKEND
        )
    )
    results.append(check_api_reference(py))

    print("\n=== 요약")
    width = max(len(r.name) for r in results)
    for r in results:
        print(f"  {r.status:<4}  {r.name:<{width}}  {r.detail}  ({r.seconds:.1f}s)")
    failed = [r for r in results if r.status == "FAIL"]
    print(f"\n게이트: {'FAIL' if failed else 'PASS'} ({len(failed)} 실패, python={py})")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
