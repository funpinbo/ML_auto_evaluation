"""app/web/routes.py — Web UI 페이지 라우터 (소유 팀: frontend, FR-002 T-012).

`app.web` 은 `app.api.app`(backend 소유 FastAPI 인스턴스, `app/api/__init__.py`)에
의존하는 방향으로만 연결된다(20-architecture-analysis.md §4 "webui --> api" edge,
frontend charter §2). 이 모듈을 import 하면 부작용으로 템플릿/정적 파일 라우트가 공유
`app` 인스턴스에 자가 등록(self-register)된다 — backend 소유 파일(`app/api/__init__.py`)을
frontend 가 직접 수정하지 않고도 웹 UI 를 같은 프로세스에 연결하는 방법이다.

실행 시 필요한 조건: `app/__main__.py`(T-036, ADR-005, backend 소유)가 기동 전에
`import app.web` (또는 동등하게 이 모듈을 import) 해야 라우트가 등록된다. 이 한 줄이
아직 반영되지 않았다면 STM §5 Task 후보를 참고.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api import app as _app

_WEB_DIR = Path(__file__).parent
TEMPLATES_DIR = _WEB_DIR / "templates"
STATIC_DIR = _WEB_DIR / "static"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter()


@router.get("/")
def upload_page(request: Request):
    """업로드 화면(FR-002, T-012) — 모델/데이터 업로드 폼 + 목록.

    목록(`GET /models`, `GET /datasets`)과 업로드 제출(`POST /models`, `POST /datasets`)은
    서버 렌더링 없이 `app/web/static/upload.js` 가 fetch 로 채운다(바닐라 JS, Node 빌드 없음).
    """
    return templates.TemplateResponse(request, "upload.html", {})


# 공유 `app` 인스턴스에 자가 등록(위 모듈 docstring 참고). 이 두 줄이 이 패키지가
# 유일하게 `app.api.app` 객체를 건드리는 지점이며, 파일(`app/api/__init__.py`) 자체는
# 수정하지 않는다.
_app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
_app.include_router(router)

__all__ = ["router", "templates"]
