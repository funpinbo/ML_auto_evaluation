"""`POST /datasets` / `GET /datasets` 통합 테스트 (T-011, backend 소유).

qa 테스트 케이스(workspace/project/qa/test-cases/FR-002.md) TC-002-03(데이터셋 목록 조회)/
TC-002-05(네거티브: bad_single_column.csv)에 대응한다. 더미 fixture(tests/fixtures/, qa 소유,
T-005)를 그대로 업로드해 성공/실패 경로를 검증한다. 모든 테스트는 인메모리 SQLite(":memory:")와
임시 디렉터리(`tmp_path`)를 사용해 실제 `workspace/data/`를 건드리지 않는다(02§5 테스트 격리).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api import app
from app.api import datasets as datasets_router
from app.eval import repository as repo

FIXTURES = Path(__file__).parent.parent / "fixtures"


@pytest.fixture()
def conn():
    connection = repo.get_connection(":memory:")
    yield connection
    connection.close()


@pytest.fixture()
def client(tmp_path, monkeypatch, conn):
    monkeypatch.setattr(datasets_router, "DATASETS_DIR", tmp_path / "datasets")

    def override_get_db():
        yield conn

    app.dependency_overrides[datasets_router.get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _upload_dataset(client: TestClient, *, csv_path: Path, name: str):
    with csv_path.open("rb") as fh:
        return client.post(
            "/datasets",
            data={"name": name},
            files={"file": (csv_path.name, fh, "text/csv")},
        )


# --- 성공 경로 (ADR-002 §3, 마지막 컬럼=라벨) ------------------------------------------


def test_upload_dataset_success(client: TestClient, conn):
    response = _upload_dataset(
        client,
        csv_path=FIXTURES / "classification_data.csv",
        name="classification_data",
    )
    assert response.status_code == 201
    dataset_id = response.json()["dataset_id"]
    assert dataset_id

    stored = repo.get_dataset(conn, dataset_id)
    assert stored is not None
    assert stored["name"] == "classification_data"


# --- 네거티브 / TC-002-05 (CSV 열 1개 -> 마지막 컬럼=라벨 컨벤션 적용 불가) -----------------


def test_upload_dataset_single_column_rejected(client: TestClient, conn):
    response = _upload_dataset(
        client, csv_path=FIXTURES / "bad_single_column.csv", name="bad_single_column"
    )
    assert 400 <= response.status_code < 500
    assert "마지막 컬럼" in response.json()["detail"]
    # 컨벤션 위반 시 Dataset 레코드가 생성되지 않는다.
    assert repo.list_datasets(conn) == []


# --- GET /datasets / TC-002-03 ---------------------------------------------------------


def test_list_datasets(client: TestClient, conn):
    assert client.get("/datasets").json() == []

    upload_response = _upload_dataset(
        client, csv_path=FIXTURES / "regression_data.csv", name="regression_data"
    )
    dataset_id = upload_response.json()["dataset_id"]

    response = client.get("/datasets")
    assert response.status_code == 200
    assert response.json() == [{"dataset_id": dataset_id, "name": "regression_data"}]


# --- 경로 이탈(CWE-22) 네거티브 케이스 (`app/api/models.py` 와 동일한 방어, D-20) -----------


@pytest.mark.parametrize(
    "malicious_filename",
    [
        "../../../evil.csv",
        "..\\..\\..\\evil.csv",
        "../../evil_sibling_dir_marker.csv",
    ],
)
def test_upload_dataset_rejects_path_traversal_filename(
    client: TestClient, conn, tmp_path, malicious_filename
):
    datasets_dir = tmp_path / "datasets"
    with (FIXTURES / "classification_data.csv").open("rb") as fh:
        response = client.post(
            "/datasets",
            data={"name": "classification_data"},
            files={"file": (malicious_filename, fh, "text/csv")},
        )

    # 베이스네임만 사용하므로 경로 이탈이 아니라 정상적으로 datasets_dir 안에 저장되어
    # 업로드 자체는 성공해야 한다(컨벤션을 충족하는 fixture 사용).
    assert response.status_code == 201
    dataset_id = response.json()["dataset_id"]
    stored = repo.get_dataset(conn, dataset_id)
    assert stored is not None

    stored_path = Path(stored["path"]).resolve()
    assert stored_path.is_relative_to(datasets_dir.resolve())

    assert not (tmp_path.parent / "evil.csv").exists()
    assert not (Path.cwd() / "evil.csv").exists()
