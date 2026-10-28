"""app/api/links.py — `POST /links`, `GET /links` 라우터 (FR-001, T-013, backend 소유).

Model-Dataset N:M 연결(Link)을 생성/조회한다. `model_dataset_link` 테이블은 복합 PK
(model_id, dataset_id) 뿐이고 별도 link_id 가 없으므로(app/eval/repository.py L57-61),
응답 바디는 `{model_id, dataset_id}` 로 echo 한다(FR-001.md "POST /links ... → 201 {link_id}
(또는 동등 응답)" 의 "동등 응답"에 해당, STM T-013 §2 분석).

에러 매핑(models.py/datasets.py 의 "422+ERROR 로그" 스타일 재사용, LTM §2):
  - `repo.NotFoundError`(model_id/dataset_id 미존재) -> 404 (FR-001 AC-5 "4xx")
  - `sqlite3.IntegrityError`(동일 (model_id, dataset_id) 중복, 복합 PK 제약) -> 409
    (중복 연결 허용 여부 자체는 미결정 — FR-001.md Out of scope, architecture Task 후보
    STM §5 기록 — 이 라우터는 DB 제약 위반을 그대로 409 로만 번역한다)
"""

from __future__ import annotations

import logging
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.eval import repository as repo

logger = logging.getLogger(__name__)

router = APIRouter()


class LinkCreateRequest(BaseModel):
    model_id: str
    dataset_id: str


def get_db() -> sqlite3.Connection:
    """요청마다 SQLite 커넥션을 열고 끝나면 닫는다(FastAPI 의존성 주입).

    `app/api/models.py::get_db` / `app/api/datasets.py::get_db` 와 동일한 패턴(D-19) —
    테스트는 `app.dependency_overrides[get_db]` 로 `":memory:"` 커넥션으로 교체한다
    (02§5 테스트 격리).
    """
    conn = repo.get_connection()
    try:
        yield conn
    finally:
        conn.close()


@router.post("/links", status_code=status.HTTP_201_CREATED)
def create_link(
    body: LinkCreateRequest,
    conn: sqlite3.Connection = Depends(get_db),  # noqa: B008 — FastAPI 표준 패턴(의도된 사용)
) -> dict:
    """Model-Dataset Link 1건을 생성한다 (FR-001 AC-1/AC-2/AC-3).

    - 존재하지 않는 model_id/dataset_id 면 404 + ERROR 로그(AC-5).
    - 동일 (model_id, dataset_id) 조합이 이미 있으면 409 + WARN 로그(복합 PK 제약,
      중복 정책 자체는 미결정).
    """
    try:
        repo.create_link(conn, model_id=body.model_id, dataset_id=body.dataset_id)
    except repo.NotFoundError as exc:
        logger.error(
            "링크 생성 실패(model/dataset 미존재): model_id=%s dataset_id=%s error=%s",
            body.model_id,
            body.dataset_id,
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except sqlite3.IntegrityError as exc:
        logger.warning(
            "링크 생성 실패(중복 조합): model_id=%s dataset_id=%s error=%s",
            body.model_id,
            body.dataset_id,
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"link already exists: model_id={body.model_id} dataset_id={body.dataset_id}",
        ) from exc

    logger.info(
        "링크 생성 완료: model_id=%s dataset_id=%s", body.model_id, body.dataset_id
    )
    return {"model_id": body.model_id, "dataset_id": body.dataset_id}


@router.get("/links")
def list_links(
    conn: sqlite3.Connection = Depends(get_db),  # noqa: B008 — FastAPI 표준 패턴(의도된 사용)
) -> list[dict]:
    """등록된 Link 목록을 (model_id, dataset_id) 쌍으로 빠짐없이 반환한다(FR-001 AC-4)."""
    return repo.list_links(conn)
