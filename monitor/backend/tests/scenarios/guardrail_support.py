"""가드레일 시나리오 공용 도우미 (qa, T-013): 인프로세스 앱 클라이언트와 입력 변형 조합."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from fixtures.engine import install_engine
from fixtures.runtime_files import write_claude_status
from fixtures.workspace import WorkspaceInfo

from app.config import Settings
from app.main import create_app

TEST_PORT = 18765
WORKSPACE_KINDS = ("empty", "partial", "full", "broken", "closed_stm")
# (이름, 스냅샷 종류, CLAUDE_HOME 상태): 데이터 소스 부재·손상 변형 (S-01·S-03)
SOURCE_VARIANTS = (
    ("normal", "normal", "with_jsonl"),
    ("no_rate_limits", "no_rate_limits", "with_jsonl"),
    ("snapshot_missing", "none", "with_jsonl"),
    ("snapshot_stale", "stale", "with_jsonl"),
    ("snapshot_broken", "broken", "with_jsonl"),
    ("project_dir_missing", "normal", "no_project_dir"),
    ("claude_home_missing", "normal", "no_home"),
)


def app_client(
    workspace: WorkspaceInfo, claude_home: Path, *, dist_dir: Path | None = None
) -> TestClient:
    """워크스페이스에 엔진을 넣고(이미 있으면 그대로) 앱을 만든다. 서버 오류는 예외 대신 500 으로 돌려받는다."""
    install_engine(workspace.root)
    settings = Settings(
        port=TEST_PORT,
        aidlc_root=workspace.root,
        claude_home=claude_home,
        dist_dir=dist_dir or workspace.root / ".no-dist",
    )
    return TestClient(
        create_app(settings),
        base_url=f"http://127.0.0.1:{TEST_PORT}",
        raise_server_exceptions=False,
    )


def prepare_snapshot(
    workspace: WorkspaceInfo, snapshot_kind: str, dir_name: str | None
) -> None:
    kwargs = {} if dir_name is None else {"transcript_dir_name": dir_name}
    write_claude_status(workspace.claude_status_file, snapshot_kind, **kwargs)
