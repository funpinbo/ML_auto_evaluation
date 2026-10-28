"""app/api/datasets.py — `POST /datasets`, `GET /datasets` 라우터 (FR-002, T-011, backend 소유).

업로드된 CSV 파일을 `workspace/data/datasets/` 에 저장하고, "마지막 컬럼 = 라벨" 컨벤션
(ADR-002 §3, R6 — 열 수 ≥ 2)을 검증한 뒤 Repository(`app/eval/repository.py`)에 Dataset
레코드를 생성한다. 컨벤션 위반이면 저장은 그대로 두되(02§11 "업로드 데이터 삭제 금지")
Dataset 레코드는 생성하지 않고 4xx 를 반환한다(QS-6 fail fast — `app/api/models.py` 의
`predict` 계약 검증과 동일한 접근).

경로 이탈 방지(`_safe_storage_name`)는 T-010(`app/api/models.py`, D-20)에서 확정한 CWE-22
방어 패턴을 그대로 재사용한다. 공유 모듈로 추출하는 리팩토링은 이 Task 범위 밖이라 STM §5 에
Task 후보로 남긴다.
"""

from __future__ import annotations

import csv
import io
import logging
import sqlite3
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, status

from app.eval import repository as repo

logger = logging.getLogger(__name__)

router = APIRouter()

# 로컬 파일 저장소(20-architecture-analysis.md §4 "로컬 파일 저장소", workspace/data/).
# 모듈 속성으로 둬서 테스트가 `monkeypatch.setattr`로 임시 디렉터리로 교체할 수 있게 한다
# (`app/api/models.py` 의 `MODELS_DIR` 와 동일한 패턴, D-20).
DATASETS_DIR = Path("workspace/data/datasets")


class DatasetContractError(Exception):
    """업로드된 CSV 가 "마지막 컬럼 = 라벨" 컨벤션(ADR-002 §3, R6)을 만족하지 못할 때 발생한다."""


def _safe_storage_name(filename: str | None) -> str:
    """업로드 파일명에서 베이스네임만 취해 저장 파일명을 만든다 (CWE-22 경로 이탈 방지).

    `app/api/models.py::_safe_storage_name` 와 동일한 로직이다(T-010, D-20) — 데이터셋
    저장 경로(`DATASETS_DIR`)에도 동일한 방어가 필요해 그대로 재사용한다.
    """
    base = Path(filename or "").name
    if not base or base in {".", ".."}:
        base = "upload.csv"
    return f"{uuid.uuid4().hex}_{base}"


def validate_last_column_label_convention(contents: bytes) -> None:
    """CSV 바이트 내용의 헤더(첫 행) 열 수를 확인한다 (ADR-002 §3, R6 "마지막 컬럼 = 라벨").

    열 수가 2 미만이면 피처 컬럼이 하나도 남지 않아 컨벤션을 적용할 수 없으므로
    `DatasetContractError` 를 올린다. FastAPI 등 웹 프레임워크에 의존하지 않는다
    (`app/eval/model_loader.py` 와 동일한 원칙 — 팀 특화 지침 "도메인 로직은 프레임워크에
    의존하지 않게 분리").
    """
    text = contents.decode("utf-8", errors="replace")
    reader = csv.reader(io.StringIO(text))
    try:
        header = next(reader)
    except StopIteration as exc:
        raise DatasetContractError(
            "CSV 파일이 비어 있습니다. 마지막 컬럼 = 라벨 컨벤션을 적용할 열이 없습니다"
            " (ADR-002 §3)."
        ) from exc
    if len(header) < 2:
        raise DatasetContractError(
            f"CSV 열 수가 {len(header)}개입니다. 마지막 컬럼 = 라벨 컨벤션(피처 1개 이상 +"
            " 라벨 1개, 최소 2열)을 적용할 수 없습니다(ADR-002 §3, R6)."
        )


def get_db() -> sqlite3.Connection:
    """요청마다 SQLite 커넥션을 열고 끝나면 닫는다(FastAPI 의존성 주입).

    `app/api/models.py::get_db` 와 동일한 패턴(D-19) — 테스트는
    `app.dependency_overrides[get_db]` 로 `":memory:"` 커넥션으로 교체한다(02§5 테스트 격리).
    """
    conn = repo.get_connection()
    try:
        yield conn
    finally:
        conn.close()


@router.post("/datasets", status_code=status.HTTP_201_CREATED)
async def upload_dataset(
    file: UploadFile,
    name: str = Form(...),
    conn: sqlite3.Connection = Depends(get_db),  # noqa: B008 — FastAPI 표준 패턴(의도된 사용)
) -> dict:
    """데이터셋 CSV 를 업로드한다 (FR-002, ADR-002 §3).

    - CSV 열 수 < 2(마지막 컬럼 = 라벨 컨벤션 위반, R6)면 422 + ERROR 로그, Dataset
      레코드를 생성하지 않는다(QS-6 fail fast).
    """
    DATASETS_DIR.mkdir(parents=True, exist_ok=True)
    storage_name = _safe_storage_name(file.filename)
    datasets_dir_resolved = DATASETS_DIR.resolve()
    dest = (DATASETS_DIR / storage_name).resolve()
    if not dest.is_relative_to(datasets_dir_resolved):
        # 베이스네임만 사용했으므로 정상적으로는 도달하지 않는 방어적 가드(CWE-22).
        logger.error("데이터셋 업로드 거부(경로 이탈 시도): filename=%s", file.filename)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="invalid filename"
        )
    contents = await file.read()
    dest.write_bytes(contents)

    try:
        validate_last_column_label_convention(contents)
    except DatasetContractError as exc:
        logger.error(
            "데이터셋 업로드 실패(CSV 컨벤션 위반): name=%s error=%s", name, exc
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc

    dataset_id = repo.create_dataset(conn, name=name, path=str(dest))
    logger.info("데이터셋 업로드 완료: dataset_id=%s name=%s", dataset_id, name)
    return {"dataset_id": dataset_id}


@router.get("/datasets")
def list_datasets(
    conn: sqlite3.Connection = Depends(get_db),  # noqa: B008 — FastAPI 표준 패턴(의도된 사용)
) -> list[dict]:
    """등록된 Dataset 목록을 반환한다 (T-040/D-22 계약: `GET /datasets -> 200
    [{dataset_id, name}]`, qa TC-002-03 재실행 대상)."""
    rows = repo.list_datasets(conn)
    return [{"dataset_id": row["id"], "name": row["name"]} for row in rows]
