"""커밋된 프론트 dist 서빙 (ADR-005, ADR-011 §9).

라우터의 기본 처리기(`router.default`)로 등록한다 — 어떤 라우트와도 맞지 않을 때만 실행되므로
API 의 405(경로는 있고 메서드만 다름)를 가로채지 않는다(LTM: Starlette 405 가로채기).
- `/api` 또는 `/api/...` → 404 `NOT_FOUND` (메서드 무관)
- 그 밖: 파일이 있으면 GET/HEAD 로 서빙, 다른 메서드는 405 + `Allow: GET, HEAD`
- 파일이 없으면 404 `NOT_FOUND`. index.html 폴백(SPA) 없음
- `/` 는 `index.html`. dist 자체가 없으면 안내 HTML (ADR-005 §3)
"""

from __future__ import annotations

from pathlib import Path

from starlette.exceptions import HTTPException
from starlette.responses import FileResponse, HTMLResponse
from starlette.types import Receive, Scope, Send

from app.security import route_path

STATIC_METHODS = "GET, HEAD"
_IMMUTABLE = "public, max-age=31536000, immutable"
_NO_DIST_HTML = (
    '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
    "<title>AI-DLC Monitor</title></head><body>"
    "<h1>AI-DLC Monitor</h1><p>dist 없음 — <code>cd monitor/frontend &amp;&amp; npm ci "
    "&amp;&amp; npm run build</code> 후 다시 실행하세요. API 는 동작합니다.</p></body></html>"
)


def is_api_path(path: str) -> bool:
    return path == "/api" or path.startswith("/api/")


def resolve_static(dist_dir: Path, path: str) -> Path | None:
    """요청 경로를 dist 안의 일반 파일로 바꾼다. 이탈·숨김·이상한 세그먼트는 None."""
    if path in ("", "/"):
        parts = ["index.html"]
    else:
        parts = path.lstrip("/").split("/")
    for part in parts:
        if (
            not part
            or part in (".", "..")
            or part.startswith(".")
            or "\\" in part
            or "\x00" in part
            or ":" in part
        ):
            return None
    try:
        base = dist_dir.resolve(strict=True)
        candidate = base.joinpath(*parts).resolve(strict=True)
    except (OSError, RuntimeError):
        return None
    if candidate.parent != base and base not in candidate.parents:
        return None
    return candidate if candidate.is_file() else None


class StaticFallback:
    """`router.default` 로 쓰는 ASGI 앱."""

    def __init__(self, dist_dir: Path) -> None:
        self.dist_dir = dist_dir

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":  # websocket 은 HostGuard 가 이미 막는다
            return
        path = route_path(scope)
        if is_api_path(path):
            raise HTTPException(status_code=404)
        method = str(scope.get("method", "")).upper()
        target = resolve_static(self.dist_dir, path)
        dist_missing = path == "/" and not self.dist_dir.is_dir()
        if target is None and not dist_missing:
            raise HTTPException(status_code=404)
        if method not in ("GET", "HEAD"):
            raise HTTPException(status_code=405, headers={"Allow": STATIC_METHODS})
        if target is None:
            response = HTMLResponse(
                _NO_DIST_HTML, headers={"Cache-Control": "no-cache"}
            )
        else:
            in_assets = path.startswith("/assets/")
            response = FileResponse(
                target,
                headers={"Cache-Control": _IMMUTABLE if in_assets else "no-cache"},
            )
        await response(scope, receive, send)
