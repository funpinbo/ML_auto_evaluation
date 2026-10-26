"""S-05·S-06 본문 비노출 (NFR-003, privacy T-01·T-02): fixture 본문 표식이 어디에도 나오지 않는다.

검사 대상은 모든 GET 응답(본문·헤더), SSE 프레임, 로그 전체다. 표식 12종과 CLAUDE_HOME 경로·프로젝트
디렉터리 경로·`transcript_dir_name` 값(`ClaudeHome.forbidden_strings()`)을 금지 문자열로 쓴다.
- 인프로세스: 입력 변형 전체(깨진 JSONL 줄, 오래된·깨진 스냅샷)를 `caplog` 로 로그까지 확인.
- 실서버: 서브프로세스가 stderr 로 쓴 로그 파일 전체와 SSE 프레임까지 확인.
"""

from __future__ import annotations

import logging

import pytest
from fixtures.endpoints import ALL_GETS
from fixtures.engine import install_engine
from fixtures.live_server import live_server
from fixtures.markers import (
    FALSE_POSITIVE_TOKENS,
    assert_no_markers,
    find_marker_labels,
)
from fixtures.runtime_files import write_claude_status
from guardrail_support import app_client

SNAPSHOT_KINDS = ("normal", "no_rate_limits", "stale", "broken")


def _response_text(response) -> str:
    headers = "\n".join(f"{k}: {v}" for k, v in response.headers.items())
    return f"{response.url}\n{headers}\n{response.text}"


@pytest.mark.parametrize("workspace_kind", ["full", "broken", "closed_stm"])
@pytest.mark.parametrize("snapshot_kind", SNAPSHOT_KINDS)
def test_responses_and_logs_have_no_markers(
    workspace_kind, snapshot_kind, workspace_factory, claude_home_factory, caplog
) -> None:
    workspace = workspace_factory(workspace_kind)
    home = claude_home_factory(workspace.root)
    write_claude_status(
        workspace.claude_status_file, snapshot_kind, transcript_dir_name=home.dir_name
    )
    client = app_client(workspace, home.home)
    forbidden = home.forbidden_strings()

    with caplog.at_level(logging.DEBUG):
        for path in ALL_GETS:
            assert_no_markers(
                _response_text(client.get(path)),
                extra=forbidden,
                where=f"response {path}",
            )
    assert_no_markers(caplog.text, extra=forbidden, where="log")


def test_usage_series_excludes_false_positive_tokens(
    full_workspace, claude_home_factory
) -> None:
    """S-07: 집계에는 허용 필드의 토큰만 합쳐진다 — 거짓 양성(본문 속 usage)·decoy 값이 섞이지 않는다.

    정확한 합계 대조(생성기·오라클·API)는 backend `tests/api/test_usage_api.py` 가 한다.
    """
    home = claude_home_factory(full_workspace.root)
    write_claude_status(
        full_workspace.claude_status_file, "normal", transcript_dir_name=home.dir_name
    )
    client = app_client(full_workspace, home.home)
    response = client.get("/api/v1/usage/timeseries?range=30d&group=none")
    assert response.json()["meta"]["status"] != "error"
    text = response.text
    assert str(FALSE_POSITIVE_TOKENS) not in text
    assert find_marker_labels(text) == []


@pytest.mark.parametrize(
    ("workspace_kind", "snapshot_kind"), [("full", "normal"), ("broken", "broken")]
)
def test_live_server_responses_sse_and_logs_have_no_markers(
    workspace_kind, snapshot_kind, workspace_factory, claude_home_factory, tmp_path
) -> None:
    workspace = workspace_factory(workspace_kind)
    install_engine(workspace.root)
    home = claude_home_factory(workspace.root)
    write_claude_status(
        workspace.claude_status_file, snapshot_kind, transcript_dir_name=home.dir_name
    )
    forbidden = home.forbidden_strings()

    with live_server(workspace.root, home.home, tmp_path) as server:
        for path in ALL_GETS:
            assert_no_markers(
                _response_text(server.client.get(path)),
                extra=forbidden,
                where=f"live {path}",
            )
        frames = []
        for frame in server.sse_frames():
            frames.append(frame)
            if frame.startswith("event: ready"):
                break
        assert frames, "SSE 프레임을 받지 못함"
        assert_no_markers("".join(frames), extra=forbidden, where="sse")

    log = server.log_text()
    assert log.strip(), "서버 로그가 비어 있으면 검사가 의미 없다"
    assert_no_markers(log, extra=forbidden, where="server log")
