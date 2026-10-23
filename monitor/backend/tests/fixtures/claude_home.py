"""임시 CLAUDE_HOME (`~/.claude` 대역) 구성.

`<root>/claude_home/` 아래에 `projects/<enc>/` JSONL, `settings.json`, 열면 안 되는 가짜 자격 증명
파일을 만든다. 실제 `~/.claude` 는 읽지도 쓰지도 않는다 (CON-06, privacy.md P-30).
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

from . import markers
from .jsonl_gen import JsonlManifest, write_project_jsonl


def encode_project_path(path: str | Path) -> str:
    """Claude Code 의 프로젝트 디렉터리 인코딩: 영숫자 외 모든 문자를 `-` 로 (contracts D-13)."""
    return re.sub(r"[^A-Za-z0-9]", "-", str(path))


@dataclass(frozen=True)
class ClaudeHome:
    home: Path  # CLAUDE_HOME 으로 주입한다
    project_dir: Path  # <home>/projects/<enc>
    dir_name: str  # <enc>. transcript_dir_name 후보. 응답·로그에 나오면 안 된다
    manifest: JsonlManifest | None

    @property
    def projects_dir(self) -> Path:
        return self.home / "projects"

    @property
    def settings_file(self) -> Path:
        return self.home / "settings.json"

    def forbidden_strings(self) -> tuple[str, ...]:
        """응답·로그·집계 어디에도 나오면 안 되는 값: 표식 + 경로 + 디렉터리 이름."""
        return (
            *markers.ALL_MARKERS,
            self.dir_name,
            str(self.home),
            str(self.project_dir),
        )


def build_claude_home(
    parent: Path,
    workspace_root: Path,
    *,
    with_jsonl: bool = True,
    with_decoys: bool = True,
    **jsonl_options: object,
) -> ClaudeHome:
    """`parent/claude_home` 을 만든다.

    - 프로젝트 디렉터리 이름은 `workspace_root` 를 인코딩한 값 (수집기의 폴백 해석 대상)
    - `with_jsonl=False` 면 projects/ 만 있고 프로젝트 디렉터리는 없음 (QS-04 "디렉터리 못 찾음")
    - decoys: `.credentials.json`, `history.jsonl` 은 읽히면 안 된다. 내용의 표식이 응답에 나오면 위반
    """
    home = parent / "claude_home"
    projects = home / "projects"
    projects.mkdir(parents=True)
    # 표식 문자열이 들어간 경로 요소를 하나 끼워 경로 노출 검사를 가능하게 한다
    dir_name = encode_project_path(workspace_root) + f"-{markers.DIR_NAME}"
    project_dir = projects / dir_name
    manifest = None
    if with_jsonl:
        manifest = write_project_jsonl(project_dir, **jsonl_options)  # type: ignore[arg-type]
    settings = {
        "statusLine": {"type": "command", "command": f"echo {markers.SETTINGS}"},
        "env": {
            "FAKE_TOKEN": markers.SETTINGS
        },  # statusLine 외 키는 읽지 않는다 (P-23)
    }
    home.joinpath("settings.json").write_text(json.dumps(settings), encoding="utf-8")
    if with_decoys:
        home.joinpath(".credentials.json").write_text(
            json.dumps({"token": markers.CREDENTIAL}), encoding="utf-8"
        )
        home.joinpath("history.jsonl").write_text(
            json.dumps({"display": markers.CREDENTIAL, "usage": {"input_tokens": 1}})
            + "\n",
            encoding="utf-8",
        )
    return ClaudeHome(
        home=home, project_dir=project_dir, dir_name=dir_name, manifest=manifest
    )


@dataclass(frozen=True)
class EscapeCase:
    """`~/.claude` 밖을 가리키는 symlink 음성 케이스 (P-28, P-29, T-07)."""

    outside_dir: Path  # CLAUDE_HOME 밖의 실제 디렉터리
    outside_file: Path  # 유효한 usage 줄이 든 파일. 읽히면 집계나 표식으로 드러난다
    dir_link: Path  # projects/<name> -> outside_dir (직속 하위 검사 대상)
    dir_link_name: str  # dir_link 의 이름 (transcript_dir_name 후보로 쓴다)
    file_link: Path  # <project_dir>/linked.jsonl -> outside_file
    subdir_link: Path  # <project_dir>/linkdir -> outside_dir


def add_symlink_escapes(parent: Path, claude_home: ClaudeHome) -> EscapeCase:
    """symlink 이탈 파일을 추가한다. 이 플랫폼에서 symlink 를 만들 수 없으면 OSError 를 그대로 던진다."""
    outside = parent / "outside"
    outside.mkdir()
    leak = outside / "leak.jsonl"
    line = {
        "type": "assistant",
        "timestamp": "2026-10-22T10:00:00.000Z",
        "requestId": f"req_{markers.ESCAPE}",
        "isSidechain": False,
        "message": {
            "model": "claude-fake-opus",
            "content": [{"type": "text", "text": markers.ESCAPE}],
            "usage": {
                "input_tokens": 424242,
                "output_tokens": 424242,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0,
            },
        },
    }
    leak.write_text(json.dumps(line) + "\n", encoding="utf-8")
    dir_link_name = "escape-dir"
    dir_link = claude_home.projects_dir / dir_link_name
    os.symlink(outside, dir_link, target_is_directory=True)
    file_link = claude_home.project_dir / "linked.jsonl"
    os.symlink(leak, file_link)
    subdir_link = claude_home.project_dir / "linkdir"
    os.symlink(outside, subdir_link, target_is_directory=True)
    return EscapeCase(outside, leak, dir_link, dir_link_name, file_link, subdir_link)
