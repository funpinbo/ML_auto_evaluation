"""`POST /links` / `GET /links` 통합 테스트 (T-013, backend 소유, FR-001).

stories/FR-001.md AC-1~AC-5 에 대응한다. Model/Dataset 은 업로드 API 를 거치지 않고
Repository(`repo.create_model`/`repo.create_dataset`)로 직접 만들어 둔다 — 이 Task 의
관심사는 링크 생성/조회이지 업로드 경로(T-010/T-011)가 아니다. 모든 테스트는 인메모리
SQLite(":memory:")를 사용해 실제 `workspace/data/`를 건드리지 않는다(02§5 테스트 격리).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api import app
from app.api import links as links_router
from app.eval import repository as repo


@pytest.fixture()
def conn():
    connection = repo.get_connection(":memory:")
    yield connection
    connection.close()


@pytest.fixture()
def client(conn):
    def override_get_db():
        yield conn

    app.dependency_overrides[links_router.get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _make_model(conn, name="model-a"):
    return repo.create_model(
        conn,
        name=name,
        path=f"workspace/data/models/{name}.py",
        framework="sklearn",
        problem_type="classification",
    )


def _make_dataset(conn, name="dataset-x"):
    return repo.create_dataset(
        conn, name=name, path=f"workspace/data/datasets/{name}.csv"
    )


# --- AC-1 기본 흐름 ------------------------------------------------------------------


def test_create_link_basic_flow(client: TestClient, conn):
    model_id = _make_model(conn)
    dataset_id = _make_dataset(conn)

    response = client.post(
        "/links", json={"model_id": model_id, "dataset_id": dataset_id}
    )

    assert response.status_code == 201
    assert response.json() == {"model_id": model_id, "dataset_id": dataset_id}
    assert repo.list_links(conn) == [{"model_id": model_id, "dataset_id": dataset_id}]


# --- AC-2 한 모델을 여러 데이터로 ------------------------------------------------------


def test_link_one_model_many_datasets(client: TestClient, conn):
    model_a = _make_model(conn, "model-a")
    dataset_x = _make_dataset(conn, "dataset-x")
    dataset_y = _make_dataset(conn, "dataset-y")

    r1 = client.post("/links", json={"model_id": model_a, "dataset_id": dataset_x})
    r2 = client.post("/links", json={"model_id": model_a, "dataset_id": dataset_y})

    assert r1.status_code == 201
    assert r2.status_code == 201
    links = repo.list_links(conn)
    assert len(links) == 2
    assert {link["dataset_id"] for link in links} == {dataset_x, dataset_y}


# --- AC-3 여러 모델을 한 데이터로 ------------------------------------------------------


def test_link_many_models_one_dataset(client: TestClient, conn):
    model_a = _make_model(conn, "model-a")
    model_b = _make_model(conn, "model-b")
    dataset_x = _make_dataset(conn, "dataset-x")

    r1 = client.post("/links", json={"model_id": model_a, "dataset_id": dataset_x})
    r2 = client.post("/links", json={"model_id": model_b, "dataset_id": dataset_x})

    assert r1.status_code == 201
    assert r2.status_code == 201
    links = repo.list_links(conn)
    assert {link["model_id"] for link in links} == {model_a, model_b}


# --- AC-4 목록 조회 -------------------------------------------------------------------


def test_list_links(client: TestClient, conn):
    assert client.get("/links").json() == []

    model_id = _make_model(conn)
    dataset_id = _make_dataset(conn)
    client.post("/links", json={"model_id": model_id, "dataset_id": dataset_id})

    response = client.get("/links")
    assert response.status_code == 200
    assert response.json() == [{"model_id": model_id, "dataset_id": dataset_id}]


# --- AC-5 존재하지 않는 model_id/dataset_id -> 4xx -------------------------------------


def test_create_link_missing_model_returns_4xx(client: TestClient, conn):
    dataset_id = _make_dataset(conn)

    response = client.post(
        "/links", json={"model_id": "nonexistent", "dataset_id": dataset_id}
    )

    assert 400 <= response.status_code < 500
    assert repo.list_links(conn) == []


def test_create_link_missing_dataset_returns_4xx(client: TestClient, conn):
    model_id = _make_model(conn)

    response = client.post(
        "/links", json={"model_id": model_id, "dataset_id": "nonexistent"}
    )

    assert 400 <= response.status_code < 500
    assert repo.list_links(conn) == []


# --- 중복 조합 -> 409 (복합 PK 제약, 중복 정책 자체는 미결정) ----------------------------


def test_create_link_duplicate_returns_409(client: TestClient, conn):
    model_id = _make_model(conn)
    dataset_id = _make_dataset(conn)

    first = client.post("/links", json={"model_id": model_id, "dataset_id": dataset_id})
    second = client.post(
        "/links", json={"model_id": model_id, "dataset_id": dataset_id}
    )

    assert first.status_code == 201
    assert second.status_code == 409
    assert repo.list_links(conn) == [{"model_id": model_id, "dataset_id": dataset_id}]
