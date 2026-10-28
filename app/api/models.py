"""app/api/models.py — `POST /models` 라우터 (FR-002, backend 소유).

업로드 파일을 `workspace/data/models/` 에 저장하고, 모델 로더(`app/eval/model_loader.py`)
로 `predict(X) -> y` 계약(ADR-002)을 검증한 뒤 Repository(`app/eval/repository.py`)에
Model 레코드를 생성한다. 계약 위반 시 저장은 그대로 두되(02§11 "업로드 데이터 삭제 금지") Model
레코드는 생성하지 않고 4xx 를 반환한다(QS-6 fail fast, FR-002 AC-4).
"""

from __future__ import annotations

import logging
import sqlite3
import uuid
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, status

from app.eval import model_loader
from app.eval import repository as repo

logger = logging.getLogger(__name__)

router = APIRouter()

# 로컬 파일 저장소(20-architecture-analysis.md §4 "로컬 파일 저장소", workspace/data/).
# 모듈 속성으로 둬서 테스트가 `monkeypatch.setattr`로 임시 디렉터리로 교체할 수 있게 한다.
MODELS_DIR = Path("workspace/data/models")


def _safe_storage_name(filename: str | None) -> str:
    """업로드 파일명에서 베이스네임만 취해 저장 파일명을 만든다 (CWE-22 경로 이탈 방지).

    `file.filename` 은 클라이언트가 보낸 신뢰할 수 없는 값이다 — `../../../evil.py` 처럼
    디렉터리 구성요소가 섞여 있으면 `MODELS_DIR` 바깥으로 경로 이탈(임의 파일 쓰기)이
    가능해진다(security 리뷰 FAIL, T-010). `Path(...).name` 으로 디렉터리 구성요소를 모두
    제거한 베이스네임만 사용하고, 결과가 비거나 `.`/`..` 뿐이면 고정 파일명으로 대체한다.
    """
    base = Path(filename or "").name
    if not base or base in {".", ".."}:
        base = "upload.py"
    return f"{uuid.uuid4().hex}_{base}"


def get_db() -> sqlite3.Connection:
    """요청마다 SQLite 커넥션을 열고 끝나면 닫는다(FastAPI 의존성 주입).

    테스트는 `app.dependency_overrides[get_db]` 로 `":memory:"` 커넥션으로 교체해
    실제 `workspace/data/ml_miniops.db` 파일을 건드리지 않는다(02§5 테스트 격리).
    """
    conn = repo.get_connection()
    try:
        yield conn
    finally:
        conn.close()


@router.post("/models", status_code=status.HTTP_201_CREATED)
async def upload_model(
    file: UploadFile,
    name: str = Form(...),
    framework: Literal["pytorch", "sklearn"] = Form(...),
    problem_type: Literal["classification", "regression"] = Form(...),
    conn: sqlite3.Connection = Depends(get_db),  # noqa: B008 — FastAPI 표준 패턴(의도된 사용)
) -> dict:
    """모델 스크립트를 업로드한다 (FR-002 AC-1/AC-2/AC-4/AC-6).

    - `problem_type` 누락/오값은 pydantic(`Literal`+`Form(...)`)이 자동으로 422 를
      반환한다(AC-6).
    - `predict(X) -> y` 계약 위반(또는 모듈 로드 실패)이면 422 + ERROR 로그, Model
      레코드를 생성하지 않는다(AC-4, QS-6).
    """
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    storage_name = _safe_storage_name(file.filename)
    models_dir_resolved = MODELS_DIR.resolve()
    dest = (MODELS_DIR / storage_name).resolve()
    if not dest.is_relative_to(models_dir_resolved):
        # 베이스네임만 사용했으므로 정상적으로는 도달하지 않는 방어적 가드(CWE-22).
        logger.error("모델 업로드 거부(경로 이탈 시도): filename=%s", file.filename)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="invalid filename"
        )
    contents = await file.read()
    dest.write_bytes(contents)

    try:
        model_loader.validate_predict_contract(dest)
    except model_loader.ModelContractError as exc:
        logger.error("모델 업로드 실패(predict 계약 위반): name=%s error=%s", name, exc)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc

    model_id = repo.create_model(
        conn,
        name=name,
        path=str(dest),
        framework=framework,
        problem_type=problem_type,
    )
    logger.info(
        "모델 업로드 완료: model_id=%s name=%s framework=%s problem_type=%s",
        model_id,
        name,
        framework,
        problem_type,
    )
    return {"model_id": model_id}


@router.get("/models")
def list_models(
    conn: sqlite3.Connection = Depends(get_db),  # noqa: B008 — FastAPI 표준 패턴(의도된 사용)
) -> list[dict]:
    """등록된 Model 목록을 반환한다 (T-040/D-21 계약: `GET /models -> 200
    [{model_id, name, framework, problem_type}]`, qa TC-002-01 재실행 대상)."""
    rows = repo.list_models(conn)
    return [
        {
            "model_id": row["id"],
            "name": row["name"],
            "framework": row["framework"],
            "problem_type": row["problem_type"],
        }
        for row in rows
    ]
