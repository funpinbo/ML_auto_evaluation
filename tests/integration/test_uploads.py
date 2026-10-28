"""`POST /models` 통합 테스트 (T-010, backend 소유).

qa 테스트 케이스(workspace/project/qa/test-cases/FR-002.md) TC-002-01/02/04/06 에 대응한다.
더미 fixture(tests/fixtures/, qa 소유, T-005)를 그대로 업로드해 성공/실패 경로를 검증한다.
모든 테스트는 인메모리 SQLite(":memory:")와 임시 디렉터리(`tmp_path`)를 사용해 실제
`workspace/data/`를 건드리지 않는다(02§5 테스트 격리).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api import app
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

    def override_get_db():
        yield conn

    app.dependency_overrides[models_router.get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _upload_model(
    client: TestClient,
    *,
    script: Path,
    name: str,
    framework: str,
    problem_type: str | None,
):
    data = {"name": name, "framework": framework}
    if problem_type is not None:
        data["problem_type"] = problem_type
    with script.open("rb") as fh:
        return client.post(
            "/models",
            data=data,
            files={"file": (script.name, fh, "text/x-python")},
        )


# --- AC-1 / TC-002-01 ----------------------------------------------------------------


def test_upload_model_success_sklearn(client: TestClient, conn):
    response = _upload_model(
        client,
        script=FIXTURES / "dummy_classifier.py",
        name="dummy_classifier",
        framework="sklearn",
        problem_type="classification",
    )
    assert response.status_code == 201
    model_id = response.json()["model_id"]
    assert model_id

    stored = repo.get_model(conn, model_id)
    assert stored is not None
    assert stored["name"] == "dummy_classifier"
    assert stored["framework"] == "sklearn"
    assert stored["problem_type"] == "classification"


# --- AC-2 / TC-002-02 (프레임워크 분기 없음, D-11: dummy_regressor fixture 재사용) --------


def test_upload_model_success_pytorch_metadata_only(client: TestClient, conn):
    """framework=pytorch 로 선언해도 평가 엔진/모델 로더는 동일한 predict(X)->y 계약만 검사한다
    (ADR-002 Decision #3) — 응답 스키마가 AC-1 과 동일한 구조임을 확인."""
    response = _upload_model(
        client,
        script=FIXTURES / "dummy_regressor.py",
        name="dummy_regressor",
        framework="pytorch",
        problem_type="regression",
    )
    assert response.status_code == 201
    body = response.json()
    assert set(body.keys()) == {"model_id"}
    model_id = body["model_id"]

    stored = repo.get_model(conn, model_id)
    assert stored is not None
    assert stored["framework"] == "pytorch"
    assert stored["problem_type"] == "regression"


# --- AC-4 / TC-002-04 (QS-6 fail fast) -------------------------------------------------


def test_upload_model_missing_predict_rejected(client: TestClient, conn):
    response = _upload_model(
        client,
        script=FIXTURES / "no_predict.py",
        name="no_predict",
        framework="sklearn",
        problem_type="classification",
    )
    assert 400 <= response.status_code < 500
    assert "predict(X) -> y" in response.json()["detail"]
    # 계약 위반 시 Model 레코드가 생성되지 않는다.
    assert repo.list_models(conn) == []


# --- AC-6 / TC-002-06 (problem_type 필수) -----------------------------------------------


def test_upload_model_missing_problem_type_rejected(client: TestClient, conn):
    response = _upload_model(
        client,
        script=FIXTURES / "dummy_classifier.py",
        name="dummy_classifier",
        framework="sklearn",
        problem_type=None,
    )
    assert response.status_code == 422
    assert repo.list_models(conn) == []


# --- security 리뷰 FAIL 조치: 경로 이탈(CWE-22) 네거티브 케이스 ----------------------------
# `file.filename` 에 `../` 를 섞어 MODELS_DIR(여기서는 tmp_path / "models") 바깥으로
# 쓰기를 시도해도 저장 경로가 반드시 MODELS_DIR 하위로 제한되는지 확인한다.


@pytest.mark.parametrize(
    "malicious_filename",
    [
        "../../../evil.py",
        "..\\..\\..\\evil.py",
        "../../evil_sibling_dir_marker.py",
    ],
)
def test_upload_model_rejects_path_traversal_filename(
    client: TestClient, conn, tmp_path, malicious_filename
):
    models_dir = tmp_path / "models"
    with (FIXTURES / "dummy_classifier.py").open("rb") as fh:
        response = client.post(
            "/models",
            data={
                "name": "dummy_classifier",
                "framework": "sklearn",
                "problem_type": "classification",
            },
            files={"file": (malicious_filename, fh, "text/x-python")},
        )

    # 베이스네임만 사용하므로 경로 이탈이 아니라 정상적으로 models_dir 안에 저장되어
    # 업로드 자체는 성공해야 한다(predict 계약은 충족하는 fixture 사용).
    assert response.status_code == 201
    model_id = response.json()["model_id"]
    stored = repo.get_model(conn, model_id)
    assert stored is not None

    stored_path = Path(stored["path"]).resolve()
    assert stored_path.is_relative_to(models_dir.resolve())

    # tmp_path 바깥(workspace root 등)에 `evil.py` 가 생성되지 않았는지 확인.
    assert not (tmp_path.parent / "evil.py").exists()
    assert not (Path.cwd() / "evil.py").exists()


# --- GET /models / T-040/D-21 계약, TC-002-01 재실행 ------------------------------------


def test_list_models(client: TestClient, conn):
    assert client.get("/models").json() == []

    upload_response = _upload_model(
        client,
        script=FIXTURES / "dummy_classifier.py",
        name="dummy_classifier",
        framework="sklearn",
        problem_type="classification",
    )
    model_id = upload_response.json()["model_id"]

    response = client.get("/models")
    assert response.status_code == 200
    assert response.json() == [
        {
            "model_id": model_id,
            "name": "dummy_classifier",
            "framework": "sklearn",
            "problem_type": "classification",
        }
    ]
