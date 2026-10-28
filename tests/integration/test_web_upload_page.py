"""`GET /` 업로드 화면 통합 테스트 (T-012, frontend 소유).

`app.web`(Jinja2 템플릿 + 바닐라 JS, app/web/routes.py)이 공유 FastAPI `app` 인스턴스
(app.api.app)에 자가 등록되는지, R2 경고 문구(threat-model.md §2.4, LTM I-11)가 실제
HTML 에 노출되는지, 정적 파일(static/style.css, static/upload.js)이 서빙되는지, 그리고
업로드 폼이 호출하는 `POST /models`/`POST /datasets` 가 같은 프로세스에서 실제로 동작하는지
(모델/데이터 업로드 성공 플로우, FR-002 AC-1/AC-3)를 pytest로 확인한다.

backend 소유 라우터(app/api/models.py, app/api/datasets.py)의 세부 계약 테스트는
tests/integration/test_uploads.py, tests/integration/test_datasets.py 가 이미 커버한다
(이 파일은 중복하지 않고, Web UI 가 그 계약을 올바르게 호출/렌더링하는지만 확인한다).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# `app.web` 을 import 하는 순간 app/web/routes.py 의 부작용으로 "/" 라우트와
# /static 마운트가 app.api.app 에 등록된다 (app/web/__init__.py 참고).
import app.web
from app.api import app
from app.api import datasets as datasets_router
from app.api import models as models_router
from app.eval import repository as repo

FIXTURES = Path(__file__).parent.parent / "fixtures"


@pytest.fixture()
def conn():
    connection = repo.get_connection(":memory:")
    yield connection
    connection.close()


@pytest.fixture()
def client(tmp_path, monkeypatch, conn):
    monkeypatch.setattr(models_router, "MODELS_DIR", tmp_path / "models")
    monkeypatch.setattr(datasets_router, "DATASETS_DIR", tmp_path / "datasets")

    def override_get_db():
        yield conn

    app.dependency_overrides[models_router.get_db] = override_get_db
    app.dependency_overrides[datasets_router.get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_upload_page_renders_with_r2_warning_and_forms(client: TestClient):
    response = client.get("/")
    assert response.status_code == 200
    html = response.text

    # R2 경고 문구 노출 확인(LTM I-11, threat-model.md §2.4, T-012 DoD).
    assert "본인이 작성/신뢰하는 스크립트만 업로드" in html

    # 두 업로드 폼과 problem_type 라디오(FR-002, 30§5.2)가 화면에 존재하는지 확인.
    assert 'data-testid="model-upload-form"' in html
    assert 'data-testid="dataset-upload-form"' in html
    assert 'data-testid="model-problem-type-classification"' in html
    assert 'data-testid="model-problem-type-regression"' in html
    assert 'data-testid="model-framework-sklearn"' in html
    assert 'data-testid="model-framework-pytorch"' in html

    # 빈 상태(empty state) 기본 노출 확인(최초 로딩 전 서버 렌더링 시점의 폴백).
    assert 'data-testid="model-list-empty"' in html
    assert 'data-testid="dataset-list-empty"' in html


def test_static_assets_served(client: TestClient):
    css = client.get("/static/style.css")
    js = client.get("/static/upload.js")
    assert css.status_code == 200
    assert js.status_code == 200
    assert (
        "model-upload-form" in js.text
    )  # JS가 템플릿과 동일한 data-testid 셀렉터를 사용


def test_model_upload_flow_via_same_app_instance(client: TestClient, conn):
    """업로드 화면이 호출하는 POST /models 가 Web UI 와 같은 app 인스턴스에서 동작하는지 확인
    (수동 업로드 성공 확인, T-012 DoD) — FR-002 AC-1."""
    assert client.get("/models").json() == []

    with (FIXTURES / "dummy_classifier.py").open("rb") as fh:
        response = client.post(
            "/models",
            data={
                "name": "dummy_classifier",
                "framework": "sklearn",
                "problem_type": "classification",
            },
            files={"file": ("dummy_classifier.py", fh, "text/x-python")},
        )
    assert response.status_code == 201
    model_id = response.json()["model_id"]

    listed = client.get("/models").json()
    assert listed == [
        {
            "model_id": model_id,
            "name": "dummy_classifier",
            "framework": "sklearn",
            "problem_type": "classification",
        }
    ]


def test_dataset_upload_flow_via_same_app_instance(client: TestClient, conn):
    """FR-002 AC-3 — 데이터 업로드도 동일한 app 인스턴스에서 성공 확인."""
    assert client.get("/datasets").json() == []

    with (FIXTURES / "classification_data.csv").open("rb") as fh:
        response = client.post(
            "/datasets",
            data={"name": "classification_data"},
            files={"file": ("classification_data.csv", fh, "text/csv")},
        )
    assert response.status_code == 201
    dataset_id = response.json()["dataset_id"]

    listed = client.get("/datasets").json()
    assert listed == [{"dataset_id": dataset_id, "name": "classification_data"}]


def test_model_upload_rejects_missing_predict_with_error_detail(
    client: TestClient, conn
):
    """FR-002 AC-4 — 화면이 보여줄 오류 메시지(02§6 {"detail": ...})가 predict 계약을 명시."""
    with (FIXTURES / "no_predict.py").open("rb") as fh:
        response = client.post(
            "/models",
            data={
                "name": "no_predict",
                "framework": "sklearn",
                "problem_type": "classification",
            },
            files={"file": ("no_predict.py", fh, "text/x-python")},
        )
    assert 400 <= response.status_code < 500
    assert "predict(X) -> y" in response.json()["detail"]
    assert client.get("/models").json() == []


def test_dataset_upload_rejects_single_column_csv(client: TestClient, conn):
    """FR-002 AC-5 — 열 수 부족 CSV 는 4xx + 미등록."""
    with (FIXTURES / "bad_single_column.csv").open("rb") as fh:
        response = client.post(
            "/datasets",
            data={"name": "bad_single_column"},
            files={"file": ("bad_single_column.csv", fh, "text/csv")},
        )
    assert 400 <= response.status_code < 500
    assert client.get("/datasets").json() == []
