"""backend 테스트 공용 도우미 (backend 소유, T-005).

- qa fixture 가 만든 workspace 루트에 저장소의 AI-DLC 엔진(`memory_cascade.py`, `aidlc.py`, 템플릿)을
  복사해 넣는다. 앱은 ADR-009 대로 `<AIDLC_ROOT>/aidlc/...` 만 본다.
- 앱 설정은 환경 변수(`app_env` 방식)와 같은 값을 `Settings` 로 만든다. 포트는 기본값(8765)이 아닌
  값을 써서 포트 리터럴 하드코딩을 드러낸다.
- TestClient 는 반드시 `base_url="http://127.0.0.1:<port>"` (LTM 패턴).
- 원시 ASGI 호출(`asgi_http`)은 httpx 가 만들 수 없는 헤더 구성(Host 0개·2개, 빈 Host)에 쓴다.
"""

from __future__ import annotations

import asyncio
import json
import shutil
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_DIR.parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict, Field

from app.config import Settings
from app.main import MonitorApp, create_app

RECEIVE_DISCONNECT_SEC = 0.05
TEST_PORT = 18765
OTHER_PORT = 18766
BASE_URL = f"http://127.0.0.1:{TEST_PORT}"
ORIGIN = f"http://127.0.0.1:{TEST_PORT}"
ENGINE_FILES = (
    Path("aidlc") / "hooks" / "memory_cascade.py",
    Path("aidlc") / "scripts" / "aidlc.py",
)
TEMPLATE_DIRS = ("user", "project", "memory")


def install_engine(root: Path) -> None:
    """저장소의 Hook·CLI·템플릿을 fixture 루트에 복사한다. 이미 있는 파일은 덮어쓰지 않는다."""
    for rel in ENGINE_FILES:
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO_ROOT / rel, dest)
    for name in TEMPLATE_DIRS:
        src = REPO_ROOT / "aidlc" / "templates" / name
        dest_dir = root / "aidlc" / "templates" / name
        dest_dir.mkdir(parents=True, exist_ok=True)
        for f in src.glob("*.md"):
            target = dest_dir / f.name
            if not target.exists():
                shutil.copy2(f, target)


def make_settings(
    root: Path, *, dist_dir: Path | None = None, claude_home: Path | None = None
) -> Settings:
    return Settings(
        port=TEST_PORT,
        aidlc_root=root,
        claude_home=claude_home or root / ".no-claude-home",
        dist_dir=dist_dir or root / ".no-dist",
    )


def make_client(app: MonitorApp) -> TestClient:
    return TestClient(app, base_url=BASE_URL, raise_server_exceptions=False)


def client_for(root: Path, **kwargs: Any) -> TestClient:
    dist_dir = kwargs.pop("dist_dir", None)
    return make_client(create_app(make_settings(root, dist_dir=dist_dir), **kwargs))


def build_dist(parent: Path) -> Path:
    dist = parent / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text(
        "<!doctype html><title>fake dist</title>", encoding="utf-8"
    )
    (dist / "assets" / "app-abc123.js").write_text("console.log(1)\n", encoding="utf-8")
    return dist


def write_doc(path: Path, meta: dict[str, object], body: str = "\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    front = "\n".join(f"{k}: {v}" for k, v in meta.items())
    path.write_text(f"---\n{front}\n---\n{body}", encoding="utf-8")


def assert_error(response: Any, status: int, code: str) -> dict[str, Any]:
    assert response.status_code == status, (response.status_code, response.text)
    body = response.json()
    assert set(body) == {"error"}, body
    assert set(body["error"]) == {"code", "message"}
    assert body["error"]["code"] == code
    return body


def walk_keys(node: Any) -> Iterable[str]:
    if isinstance(node, dict):
        for k, v in node.items():
            yield k
            yield from walk_keys(v)
    elif isinstance(node, list):
        for v in node:
            yield from walk_keys(v)


@dataclass
class RawResponse:
    status: int
    headers: list[tuple[bytes, bytes]]
    body: bytes
    messages: list[dict[str, Any]]

    def header(self, name: str) -> str | None:
        for k, v in self.headers:
            if k.decode().lower() == name.lower():
                return v.decode("latin-1")
        return None

    def json(self) -> Any:
        return json.loads(self.body.decode("utf-8"))


def http_scope(
    method: str,
    path: str,
    headers: list[tuple[bytes, bytes]],
    *,
    query: bytes = b"",
) -> dict[str, Any]:
    return {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "root_path": "",
        "query_string": query,
        "headers": headers,
        "client": ("127.0.0.1", 50000),
        "server": ("127.0.0.1", TEST_PORT),
        "state": {},
    }


def asgi_http(app: Any, scope: dict[str, Any], body: bytes = b"") -> RawResponse:
    """ASGI 앱을 scope 하나로 직접 호출한다 (H-17·H-18·H-19 등)."""
    messages: list[dict[str, Any]] = []
    sent_body = {"done": False}

    async def receive() -> dict[str, Any]:
        if not sent_body["done"]:
            sent_body["done"] = True
            return {"type": "http.request", "body": body, "more_body": False}
        # I-24: 두 번째 receive 는 연결 종료를 기다리는 경로(스트림 등)뿐이다 — 짧게 끊어 테스트가 걸리지 않게.
        await asyncio.sleep(RECEIVE_DISCONNECT_SEC)
        return {"type": "http.disconnect"}

    async def send(message: dict[str, Any]) -> None:
        messages.append(message)

    asyncio.run(app(scope, receive, send))
    start = next(m for m in messages if m["type"] == "http.response.start")
    payload = b"".join(
        m.get("body", b"") for m in messages if m["type"] == "http.response.body"
    )
    return RawResponse(
        start["status"], list(start.get("headers", [])), payload, messages
    )


# ---------------------------------------------------------------- 아직 없는 대상의 대역
# privacy.md §5.1·§5.2 의 대상 중 health(T-006)·control(T-008)·events(T-011)는 아직 구현 전이다.
# 가드는 라우팅보다 바깥이라 거부 케이스는 실제 라우트와 무관하게 성립한다. 통과 케이스가 "가드를 지나
# 핸들러에 닿았다"를 보이도록 같은 경로·메서드의 대역 라우트를 뒤에 붙인다. 실제 라우트가 생기면
# 먼저 등록된 실제 라우트가 매치되므로 대역은 가려지고 같은 테스트가 실제 라우트를 검증한다.
# control(T-008)은 실제 라우트가 생겨 대역에서 뺐다 — 통과 기대값은 "400/403/422 아님"(I-25):
# 활성 루프가 없으면 pause 409 `NO_ACTIVE_LOOP`, resume 200(멱등). `PASS_STATUS_NO_LOOP` 참조.
STUB_TARGETS = (
    ("/api/v1/health", "GET"),
    ("/api/v1/events", "GET"),
)
PASS_STATUS_NO_LOOP = {"/api/v1/control/pause": 409, "/api/v1/control/resume": 200}
CONTROL_REL = "workspace/memory/.control.json"
GUARD_REJECT_STATUSES = (400, 403, 422)


class StubBody(BaseModel):
    """`POST /control/*` 본문 대역 (20 §5 F3: `{}` 또는 `{"max_pause_sec": 600~86400}`)."""

    model_config = ConfigDict(extra="forbid")
    max_pause_sec: int | None = Field(default=None, ge=600, le=86400)


def add_stub_targets(app: MonitorApp) -> list[str]:
    def post_factory(target: str) -> Any:
        def post_stub(body: StubBody) -> dict[str, str]:
            return {"stub": target}

        return post_stub

    def get_factory(target: str) -> Any:
        def get_stub() -> dict[str, str]:
            return {"stub": target}

        return get_stub

    added: list[str] = []
    for path, method in STUB_TARGETS:
        factory = post_factory if method == "POST" else get_factory
        app.add_api_route(
            path, factory(path), methods=[method], include_in_schema=False
        )
        added.append(path)
    return added
