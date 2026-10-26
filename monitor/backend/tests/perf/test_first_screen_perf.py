"""P-01·P-02 성능 (NFR-001, QS-01·02): Task 100개 + 30일 JSONL 에서 첫 화면·REST·SSE 지연.

기본 실행에서는 제외된다(`conftest.pytest_collection_modifyitems`). 켜는 방법:

    monitor/.venv/bin/python -m pytest monitor/backend/tests/perf -m perf -s

fixture 크기는 test-strategy §5 의 하한 추정(`responses_per_day=300, body_pad=9000`, 실측 ≈ 333 MB)이고
(`QA_PERF_BODY_PAD=18000` 으로 상한 규모),
측정값(MB, 줄 수, 생성·기동·응답 시간)은 `-s` 출력의 `[perf]` 줄로 남는다.

기준
- 서버 기동 직후 Must 패널 REST 첫 응답이 모두 ≤ 2 초 (사용량은 warming 부분값 허용, 브라우저처럼 동시 요청)
- 데우기가 끝난 뒤 패널별 REST p95 ≤ 200 ms
- 파일 변경 → SSE `changed` 이벤트 ≤ 5 초
"""

from __future__ import annotations

import os
import shutil
import statistics
import tempfile
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import httpx
import pytest
from fixtures.claude_home import ClaudeHome, build_claude_home
from fixtures.endpoints import MUST_PANELS
from fixtures.engine import install_engine
from fixtures.live_server import LiveServer, live_server
from fixtures.runtime_files import write_claude_status
from fixtures.workspace import WorkspaceInfo, build_workspace

pytestmark = pytest.mark.perf

TASK_COUNT = 100
RESPONSES_PER_DAY = 300
# 줄마다 붙이는 본문 채움 바이트. 9000 ≈ 333 MB(실측), 상한 658 MB 근처는 QA_PERF_BODY_PAD=18000
BODY_PAD = int(os.environ.get("QA_PERF_BODY_PAD", "9000"))
FIRST_SCREEN_LIMIT_SEC = 2.0
REST_P95_LIMIT_SEC = 0.2
SSE_LIMIT_SEC = 5.0
WARM_TIMEOUT_SEC = 300.0
P95_ROUNDS = 40
BASELINE_TICKS_SEC = 2.5  # SSE 허브 tick(1 s) 2회 이상


def report(**values: object) -> None:
    print("[perf] " + " ".join(f"{k}={v}" for k, v in values.items()))


@dataclass(frozen=True)
class PerfData:
    workspace: WorkspaceInfo
    claude_home: ClaudeHome
    megabytes: float
    lines: int
    generate_sec: float


@pytest.fixture(scope="module")
def perf_data() -> Iterator[PerfData]:
    # pytest 가 임시 디렉터리를 3회분 보관하므로 수백 MB 는 직접 만들고 지운다
    base = Path(tempfile.mkdtemp(prefix="qa-perf-"))
    try:
        started = time.monotonic()
        workspace = build_workspace(base, "full", task_count=TASK_COUNT, name="ws")
        install_engine(workspace.root)
        home = build_claude_home(
            base,
            workspace.root,
            responses_per_day=RESPONSES_PER_DAY,
            body_pad=BODY_PAD,
        )
        write_claude_status(
            workspace.claude_status_file, "normal", transcript_dir_name=home.dir_name
        )
        elapsed = time.monotonic() - started
        manifest = home.manifest
        assert manifest is not None
        lines = sum(path.read_bytes().count(b"\n") for path in [*manifest.files])
        data = PerfData(workspace, home, manifest.bytes_written / 1e6, lines, elapsed)
        report(
            fixture_mb=f"{data.megabytes:.1f}",
            lines=lines,
            files=len(manifest.files),
            tasks=TASK_COUNT,
            generate_sec=f"{elapsed:.2f}",
        )
        yield data
    finally:
        shutil.rmtree(base, ignore_errors=True)


def timed_get(client: httpx.Client, path: str) -> tuple[str, float, httpx.Response]:
    start = time.perf_counter()
    response = client.get(path)
    return path, time.perf_counter() - start, response


def wait_until_warm(server: LiveServer) -> float:
    """health 의 `usage_warming.state` 가 done 이 될 때까지 기다린다. 걸린 시간(초)."""
    start = time.monotonic()
    while time.monotonic() - start < WARM_TIMEOUT_SEC:
        warming = server.client.get("/api/v1/health").json()["data"]["usage_warming"]
        if warming["state"] == "done":
            return time.monotonic() - start
        time.sleep(0.25)
    raise TimeoutError("사용량 데우기가 제한 시간 안에 끝나지 않음")


@pytest.fixture(scope="module")
def warm_server(perf_data: PerfData) -> Iterator[LiveServer]:
    work = Path(tempfile.mkdtemp(prefix="qa-perf-srv-"))
    try:
        with live_server(
            perf_data.workspace.root, perf_data.claude_home.home, work
        ) as server:
            warm_sec = wait_until_warm(server)
            series = server.client.get("/api/v1/usage/timeseries?range=30d&group=none")
            totals = series.json()["data"]["totals"]
            # 측정이 빈 집계 위에서 이뤄지지 않았음을 확인한다
            assert totals["output_tokens"] > 0
            report(
                warm_sec_after_healthy=f"{warm_sec:.2f}",
                output_tokens_30d=totals["output_tokens"],
            )
            yield server
    finally:
        shutil.rmtree(work, ignore_errors=True)


def test_first_screen_panels_respond_within_2_seconds(perf_data, tmp_path) -> None:
    """P-01: 서버 기동 직후 첫 화면(브라우저처럼 Must 패널 동시 요청)의 첫 응답 시간."""
    with live_server(
        perf_data.workspace.root, perf_data.claude_home.home, tmp_path
    ) as server:
        startup_sec = server.healthy_at - server.started_at
        start = time.perf_counter()
        with ThreadPoolExecutor(max_workers=len(MUST_PANELS)) as pool:
            results = list(
                pool.map(lambda path: timed_get(server.client, path), MUST_PANELS)
            )
        first_screen_sec = time.perf_counter() - start

    for path, seconds, response in results:
        assert response.status_code == 200, path
        meta_status = response.json()["meta"]["status"]
        assert meta_status != "error", path
        report(panel=path, status=meta_status, first_response_sec=f"{seconds:.3f}")
    report(
        process_start_to_health_sec=f"{startup_sec:.2f}",
        first_screen_all_panels_sec=f"{first_screen_sec:.3f}",
    )
    assert first_screen_sec <= FIRST_SCREEN_LIMIT_SEC


@pytest.mark.parametrize("path", MUST_PANELS)
def test_rest_p95_after_warmup_under_200ms(warm_server: LiveServer, path: str) -> None:
    timed_get(warm_server.client, path)  # 데우기 요청 1회는 버린다
    samples = []
    for _ in range(P95_ROUNDS):
        _, seconds, response = timed_get(warm_server.client, path)
        assert response.status_code == 200
        samples.append(seconds)
    p95 = statistics.quantiles(samples, n=20)[-1]
    report(
        panel=path,
        p50_ms=f"{statistics.median(samples) * 1000:.1f}",
        p95_ms=f"{p95 * 1000:.1f}",
    )
    assert p95 <= REST_P95_LIMIT_SEC


def test_change_reaches_sse_within_5_seconds(
    warm_server: LiveServer, perf_data: PerfData
) -> None:
    """P-02: tasks.md 변경 → `changed` 이벤트까지의 시간 (감시 주기 1초 포함)."""
    tasks_file = perf_data.workspace.memory / "tasks.md"
    frames = warm_server.sse_frames(timeout=SSE_LIMIT_SEC + 5)
    for frame in frames:
        if frame.startswith(("event: ready", "event: warming")):
            break
    # 허브의 첫 tick 이 변경 감지 기준선을 잡는다. 그 뒤의 변경만 알림 대상이다.
    time.sleep(BASELINE_TICKS_SEC)
    changed_at = time.perf_counter()
    tasks_file.write_text(
        tasks_file.read_text(encoding="utf-8") + "\n<!-- perf touch -->\n",
        encoding="utf-8",
    )
    for frame in frames:
        if frame.startswith("event: changed"):
            break
    else:
        pytest.fail("changed 이벤트를 받지 못함")
    latency = time.perf_counter() - changed_at
    frames.close()
    report(change_to_sse_sec=f"{latency:.2f}")
    assert latency <= SSE_LIMIT_SEC
