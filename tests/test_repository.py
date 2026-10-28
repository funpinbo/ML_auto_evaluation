"""app/eval/repository.py 쿼리 함수 단위 테스트 (T-009, backend 소유).

더미 fixture(tests/fixtures/, qa 소유, T-005)의 경로를 model/dataset 레코드의 `path` 값으로
참조하는 수준으로만 사용한다 — 실제 `predict` 호출/CSV 파싱은 이 Task 범위 밖(model_loader는
별도 Task). 모든 테스트는 인메모리 SQLite(":memory:")로 실행해 저장소 실제 파일을 건드리지 않는다
(02§5 "실제 사용자 업로드 데이터 대신 더미로 테스트", 02§11 전역 환경/데이터 보호와는 무관하게
테스트 격리를 위함).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.eval import repository as repo

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture()
def conn():
    connection = repo.get_connection(":memory:")
    yield connection
    connection.close()


# --- Model ---------------------------------------------------------------------


def test_create_and_get_model(conn: sqlite3.Connection):
    model_id = repo.create_model(
        conn,
        name="dummy_classifier",
        path=str(FIXTURES / "dummy_classifier.py"),
        framework="sklearn",
        problem_type="classification",
    )
    model = repo.get_model(conn, model_id)
    assert model is not None
    assert model["id"] == model_id
    assert model["name"] == "dummy_classifier"
    assert model["framework"] == "sklearn"
    assert model["problem_type"] == "classification"
    # D-03: problem_type_source 는 사용자가 직접 지정("user_declared")이 기본값
    assert model["problem_type_source"] == "user_declared"


def test_get_model_missing_returns_none(conn: sqlite3.Connection):
    assert repo.get_model(conn, "nonexistent") is None


def test_create_model_reupload_always_creates_new_record(conn: sqlite3.Connection):
    """ADR-004/D-15: 동일 name/path 로 재업로드해도 항상 신규 레코드(새 id)를 만든다."""
    first_id = repo.create_model(
        conn,
        name="dummy_classifier",
        path=str(FIXTURES / "dummy_classifier.py"),
        framework="sklearn",
        problem_type="classification",
    )
    second_id = repo.create_model(
        conn,
        name="dummy_classifier",
        path=str(FIXTURES / "dummy_classifier.py"),
        framework="sklearn",
        problem_type="classification",
    )
    assert first_id != second_id
    assert len(repo.list_models(conn)) == 2


def test_list_models_empty(conn: sqlite3.Connection):
    assert repo.list_models(conn) == []


# --- Dataset ---------------------------------------------------------------------


def test_create_and_get_dataset(conn: sqlite3.Connection):
    dataset_id = repo.create_dataset(
        conn, name="classification_data", path=str(FIXTURES / "classification_data.csv")
    )
    dataset = repo.get_dataset(conn, dataset_id)
    assert dataset is not None
    assert dataset["name"] == "classification_data"


def test_list_datasets(conn: sqlite3.Connection):
    repo.create_dataset(conn, name="a", path=str(FIXTURES / "classification_data.csv"))
    repo.create_dataset(conn, name="b", path=str(FIXTURES / "regression_data.csv"))
    datasets = repo.list_datasets(conn)
    assert {d["name"] for d in datasets} == {"a", "b"}


# --- Link (FR-001) ----------------------------------------------------------------


def _make_model(conn, name="m", problem_type="classification"):
    return repo.create_model(
        conn,
        name=name,
        path=str(FIXTURES / "dummy_classifier.py"),
        framework="sklearn",
        problem_type=problem_type,
    )


def _make_dataset(conn, name="d"):
    return repo.create_dataset(
        conn, name=name, path=str(FIXTURES / "classification_data.csv")
    )


def test_create_link_basic_flow(conn: sqlite3.Connection):
    """FR-001 AC-1."""
    model_id = _make_model(conn)
    dataset_id = _make_dataset(conn)
    repo.create_link(conn, model_id=model_id, dataset_id=dataset_id)
    links = repo.list_links(conn)
    assert links == [{"model_id": model_id, "dataset_id": dataset_id}]


def test_create_link_one_model_many_datasets(conn: sqlite3.Connection):
    """FR-001 AC-2: 한 모델을 여러 데이터로."""
    model_a = _make_model(conn, name="A")
    dataset_x = _make_dataset(conn, name="X")
    dataset_y = _make_dataset(conn, name="Y")
    repo.create_link(conn, model_id=model_a, dataset_id=dataset_x)
    repo.create_link(conn, model_id=model_a, dataset_id=dataset_y)
    links = repo.list_links(conn)
    assert len(links) == 2
    assert {link["dataset_id"] for link in links} == {dataset_x, dataset_y}
    # 기존 Link(Model A, Dataset X) 그대로 유지됨
    assert {"model_id": model_a, "dataset_id": dataset_x} in links


def test_create_link_many_models_one_dataset(conn: sqlite3.Connection):
    """FR-001 AC-3: 여러 모델을 한 데이터로."""
    model_a = _make_model(conn, name="A")
    model_b = _make_model(conn, name="B")
    dataset_x = _make_dataset(conn, name="X")
    repo.create_link(conn, model_id=model_a, dataset_id=dataset_x)
    repo.create_link(conn, model_id=model_b, dataset_id=dataset_x)
    links = repo.list_links(conn)
    assert {link["model_id"] for link in links} == {model_a, model_b}


def test_create_link_missing_model_raises_not_found(conn: sqlite3.Connection):
    """FR-001 AC-5: 미업로드 model_id 로 연결 시도 -> 생성되지 않고 오류."""
    dataset_id = _make_dataset(conn)
    with pytest.raises(repo.NotFoundError):
        repo.create_link(conn, model_id="nonexistent", dataset_id=dataset_id)
    assert repo.list_links(conn) == []


def test_create_link_missing_dataset_raises_not_found(conn: sqlite3.Connection):
    """FR-001 AC-5: 미업로드 dataset_id 로 연결 시도 -> 생성되지 않고 오류."""
    model_id = _make_model(conn)
    with pytest.raises(repo.NotFoundError):
        repo.create_link(conn, model_id=model_id, dataset_id="nonexistent")
    assert repo.list_links(conn) == []


def test_create_link_duplicate_raises_integrity_error(conn: sqlite3.Connection):
    """model_dataset_link 복합 PK 가 동일 조합 중복 삽입을 차단한다(D-15, 변경 없음)."""
    model_id = _make_model(conn)
    dataset_id = _make_dataset(conn)
    repo.create_link(conn, model_id=model_id, dataset_id=dataset_id)
    with pytest.raises(sqlite3.IntegrityError):
        repo.create_link(conn, model_id=model_id, dataset_id=dataset_id)


# --- Run & Evaluation (FR-004) -----------------------------------------------------


def test_create_and_get_run(conn: sqlite3.Connection):
    run_id = repo.create_run(conn)
    run = repo.get_run(conn, run_id)
    assert run is not None
    assert run["id"] == run_id
    assert run["created_at"]  # 기본값이 채워짐


def test_create_evaluation_success(conn: sqlite3.Connection):
    """FR-004 AC-3: 호환 조합 평가 성공."""
    model_id = _make_model(conn)
    dataset_id = _make_dataset(conn)
    run_id = repo.create_run(conn)
    evaluation_id = repo.create_evaluation(
        conn,
        run_id=run_id,
        model_id=model_id,
        dataset_id=dataset_id,
        metric="accuracy",
        value=0.833,
        status="success",
    )
    evaluations = repo.list_evaluations_by_run(conn, run_id)
    assert len(evaluations) == 1
    assert evaluations[0]["id"] == evaluation_id
    assert evaluations[0]["status"] == "success"
    assert evaluations[0]["value"] == 0.833


def test_create_evaluation_run_groups_multiple_combinations(conn: sqlite3.Connection):
    """FR-004 AC-2: Run 1건에 조합 3건 -> Evaluation 3건, 모두 동일 run_id 로 귀속."""
    run_id = repo.create_run(conn)
    for i in range(3):
        model_id = _make_model(conn, name=f"m{i}")
        dataset_id = _make_dataset(conn, name=f"d{i}")
        repo.create_evaluation(
            conn,
            run_id=run_id,
            model_id=model_id,
            dataset_id=dataset_id,
            metric="accuracy",
            value=0.5,
            status="success",
        )
    evaluations = repo.list_evaluations_by_run(conn, run_id)
    assert len(evaluations) == 3
    assert all(e["run_id"] == run_id for e in evaluations)


def test_create_evaluation_skipped_incompatible_keeps_record_with_null_value(
    conn: sqlite3.Connection,
):
    """ADR-003/D-04: 비호환 조합도 레코드를 남기되 value=NULL, status=skipped_incompatible."""
    model_id = _make_model(conn, problem_type="regression")
    dataset_id = _make_dataset(conn)
    run_id = repo.create_run(conn)
    repo.create_evaluation(
        conn,
        run_id=run_id,
        model_id=model_id,
        dataset_id=dataset_id,
        metric="accuracy",
        value=None,
        status="skipped_incompatible",
    )
    evaluations = repo.list_evaluations_by_run(conn, run_id)
    assert evaluations[0]["status"] == "skipped_incompatible"
    assert evaluations[0]["value"] is None


def test_create_evaluation_error_status_keeps_record(conn: sqlite3.Connection):
    """FR-004 AC-4: 계산 중 예외가 나도 Evaluation 레코드는 status=error 로 남는다."""
    model_id = _make_model(conn)
    dataset_id = _make_dataset(conn)
    run_id = repo.create_run(conn)
    repo.create_evaluation(
        conn,
        run_id=run_id,
        model_id=model_id,
        dataset_id=dataset_id,
        metric="accuracy",
        value=None,
        status="error",
    )
    evaluations = repo.list_evaluations_by_run(conn, run_id)
    assert evaluations[0]["status"] == "error"
    assert evaluations[0]["value"] is None


def test_create_evaluation_missing_run_raises_not_found(conn: sqlite3.Connection):
    model_id = _make_model(conn)
    dataset_id = _make_dataset(conn)
    with pytest.raises(repo.NotFoundError):
        repo.create_evaluation(
            conn,
            run_id="nonexistent",
            model_id=model_id,
            dataset_id=dataset_id,
            metric="accuracy",
            value=1.0,
        )


def test_create_evaluation_invalid_metric_rejected_by_check_constraint(
    conn: sqlite3.Connection,
):
    """evaluation.metric CHECK 제약(accuracy/f1/rmse) 은 DDL(dba) 소유 — 쿼리 함수가 임의로
    우회하지 않고 그대로 sqlite3.IntegrityError 를 전파하는지 확인."""
    model_id = _make_model(conn)
    dataset_id = _make_dataset(conn)
    run_id = repo.create_run(conn)
    with pytest.raises(sqlite3.IntegrityError):
        repo.create_evaluation(
            conn,
            run_id=run_id,
            model_id=model_id,
            dataset_id=dataset_id,
            metric="not_a_real_metric",
            value=1.0,
        )


# --- FK 강제 (T-029, LTM I-03) -----------------------------------------------------


def test_get_connection_enables_foreign_keys_pragma(conn: sqlite3.Connection):
    """커넥션을 열 때마다 `PRAGMA foreign_keys = ON` 이 실제로 설정됐는지 확인한다."""
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_foreign_keys_pragma_rejects_raw_link_insert_with_missing_model(
    conn: sqlite3.Connection,
):
    """model_dataset_link.model_id 가 존재하지 않는 model 을 참조하면 DB 레벨에서 거부된다.

    `repo.create_link` 의 애플리케이션 레벨 사전 검사(NotFoundError)를 우회해 raw SQL 로 직접
    INSERT 해도 PRAGMA foreign_keys=ON 덕분에 FK 위반으로 막히는지 확인 — 애플리케이션 레벨
    검사와 독립적인 DB 레벨 2차 방어선(D-17 과 상호보완, 중복이 아님)."""
    dataset_id = _make_dataset(conn)
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY constraint failed"):
        conn.execute(
            "INSERT INTO model_dataset_link (model_id, dataset_id) VALUES (?, ?)",
            ("nonexistent-model", dataset_id),
        )


def test_foreign_keys_pragma_rejects_raw_link_insert_with_missing_dataset(
    conn: sqlite3.Connection,
):
    model_id = _make_model(conn)
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY constraint failed"):
        conn.execute(
            "INSERT INTO model_dataset_link (model_id, dataset_id) VALUES (?, ?)",
            (model_id, "nonexistent-dataset"),
        )


def test_foreign_keys_pragma_rejects_raw_evaluation_insert_with_missing_run(
    conn: sqlite3.Connection,
):
    model_id = _make_model(conn)
    dataset_id = _make_dataset(conn)
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY constraint failed"):
        conn.execute(
            "INSERT INTO evaluation (id, run_id, model_id, dataset_id, metric, value, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "eval-1",
                "nonexistent-run",
                model_id,
                dataset_id,
                "accuracy",
                0.5,
                "success",
            ),
        )


def test_foreign_keys_pragma_rejects_raw_evaluation_insert_with_missing_model(
    conn: sqlite3.Connection,
):
    run_id = repo.create_run(conn)
    dataset_id = _make_dataset(conn)
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY constraint failed"):
        conn.execute(
            "INSERT INTO evaluation (id, run_id, model_id, dataset_id, metric, value, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "eval-2",
                run_id,
                "nonexistent-model",
                dataset_id,
                "accuracy",
                0.5,
                "success",
            ),
        )


def test_foreign_keys_pragma_rejects_raw_evaluation_insert_with_missing_dataset(
    conn: sqlite3.Connection,
):
    run_id = repo.create_run(conn)
    model_id = _make_model(conn)
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY constraint failed"):
        conn.execute(
            "INSERT INTO evaluation (id, run_id, model_id, dataset_id, metric, value, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "eval-3",
                run_id,
                model_id,
                "nonexistent-dataset",
                "accuracy",
                0.5,
                "success",
            ),
        )


# --- 재시작 복구 (QS-2, FR-004 AC-6) ------------------------------------------------


def test_get_connection_persists_data_across_reconnect(tmp_path: Path):
    """파일 기반 SQLite 는 커넥션을 닫고 새로 열어도 기존 Run/Evaluation 레코드가 그대로
    조회된다 — AC-6(재시작 후 데이터 보존)의 저장소 계층 단위 검증. 서버 프로세스 재시작
    자체의 E2E 검증은 qa 수동 체크리스트 범위(LTM I-04)."""
    db_path = tmp_path / "ml_miniops_test.db"

    first_conn = repo.get_connection(str(db_path))
    model_id = _make_model(first_conn)
    dataset_id = _make_dataset(first_conn)
    run_id = repo.create_run(first_conn)
    repo.create_evaluation(
        first_conn,
        run_id=run_id,
        model_id=model_id,
        dataset_id=dataset_id,
        metric="rmse",
        value=0.088,
        status="success",
    )
    first_conn.close()

    second_conn = repo.get_connection(str(db_path))
    try:
        assert repo.get_run(second_conn, run_id) is not None
        evaluations = repo.list_evaluations_by_run(second_conn, run_id)
        assert len(evaluations) == 1
        assert evaluations[0]["value"] == 0.088
    finally:
        second_conn.close()
