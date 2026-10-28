"""
30-data-analysis.md 부속 스크립트.

전제: workspace/data/ 에 실제 DS-01(CSV)/DS-02(모델 스크립트) 샘플이 없으므로
(2026-10-26 기준 확인됨) 실제 데이터 프로파일링은 수행하지 않는다.

이 스크립트는 "데이터가 없을 때도 검증 가능한 부분" 즉
04-data-definition.md §2 의 예상 엔티티·관계 및 00-interpretation.md §3.2 #10
(지표-문제유형 호환성 미정 과제)에 대한 **데이터 모델 제안의 동작을 합성(synthetic)
픽스처로 검증**하기 위한 것이다. 실제 업로드 데이터의 통계치가 아니라,
스키마/로직이 논리적으로 성립하는지(제약조건 위반 없이 생성·조회되는지,
호환성 필터가 의도대로 동작하는지)를 표준 라이브러리 sqlite3 로 확인한다.

출력: summary.json (이 디렉터리에 생성) — 30-data-analysis.md 가 인용하는 수치의 근거.
"""
import json
import logging
import pathlib
import sqlite3

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("schema_validation")

DDL = """
CREATE TABLE model (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    path TEXT NOT NULL,
    framework TEXT NOT NULL CHECK (framework IN ('pytorch', 'sklearn')),
    problem_type TEXT NOT NULL CHECK (problem_type IN ('classification', 'regression')),
    problem_type_source TEXT NOT NULL CHECK (problem_type_source IN ('user_declared', 'inferred')) DEFAULT 'user_declared'
);

CREATE TABLE dataset (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    path TEXT NOT NULL
);

CREATE TABLE model_dataset_link (
    model_id TEXT NOT NULL REFERENCES model(id),
    dataset_id TEXT NOT NULL REFERENCES dataset(id),
    PRIMARY KEY (model_id, dataset_id)
);

CREATE TABLE run (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL
);

CREATE TABLE evaluation (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES run(id),
    model_id TEXT NOT NULL REFERENCES model(id),
    dataset_id TEXT NOT NULL REFERENCES dataset(id),
    metric TEXT NOT NULL CHECK (metric IN ('accuracy', 'f1', 'rmse')),
    value REAL,
    status TEXT NOT NULL CHECK (status IN ('success', 'skipped_incompatible', 'error')) DEFAULT 'success'
);
"""

# 00-interpretation.md §3.2 #10 설계 과제에 대한 제안: 문제유형별 허용 지표 매핑.
METRIC_COMPATIBILITY = {
    "classification": {"accuracy", "f1"},
    "regression": {"rmse"},
}

# 합성 픽스처: 실제 업로드 데이터가 아니라 스키마 검증용 가상 샘플.
SYNTHETIC_MODELS = [
    {"id": "m1", "name": "demo_logreg", "path": "fixtures/m1.py", "framework": "sklearn", "problem_type": "classification"},
    {"id": "m2", "name": "demo_linreg", "path": "fixtures/m2.py", "framework": "sklearn", "problem_type": "regression"},
]
SYNTHETIC_DATASETS = [
    {"id": "d1", "name": "demo_classification_csv", "path": "fixtures/d1.csv"},
    {"id": "d2", "name": "demo_regression_csv", "path": "fixtures/d2.csv"},
]
# (model_id, dataset_id, metric) 후보 조합 — 사용자가 Run 클릭 시 선택했다고 가정.
SYNTHETIC_RUN_REQUESTS = [
    ("m1", "d1", "accuracy"),   # 호환 (classification + accuracy)
    ("m1", "d1", "f1"),         # 호환 (classification + f1)
    ("m1", "d1", "rmse"),       # 비호환 (classification + rmse) -> skipped
    ("m2", "d2", "rmse"),       # 호환 (regression + rmse)
    ("m2", "d2", "accuracy"),   # 비호환 (regression + accuracy) -> skipped
]


def build_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(DDL)


def seed_fixtures(conn: sqlite3.Connection) -> None:
    conn.executemany(
        "INSERT INTO model (id, name, path, framework, problem_type) VALUES (?, ?, ?, ?, ?)",
        [(m["id"], m["name"], m["path"], m["framework"], m["problem_type"]) for m in SYNTHETIC_MODELS],
    )
    conn.executemany(
        "INSERT INTO dataset (id, name, path) VALUES (?, ?, ?)",
        [(d["id"], d["name"], d["path"]) for d in SYNTHETIC_DATASETS],
    )
    conn.execute("INSERT INTO run (id, created_at) VALUES ('r1', '2026-10-26T00:00:00')")


def run_evaluations(conn: sqlite3.Connection):
    model_by_id = {m["id"]: m for m in SYNTHETIC_MODELS}
    results = {"success": 0, "skipped_incompatible": 0}
    for idx, (model_id, dataset_id, metric) in enumerate(SYNTHETIC_RUN_REQUESTS, start=1):
        problem_type = model_by_id[model_id]["problem_type"]
        compatible = metric in METRIC_COMPATIBILITY[problem_type]
        status = "success" if compatible else "skipped_incompatible"
        # 합성 평가값: 호환되는 경우만 더미 값 기록 (실제 평가 로직은 20 아키텍처 단계 과제)
        value = 0.9 if compatible else None
        conn.execute(
            "INSERT INTO evaluation (id, run_id, model_id, dataset_id, metric, value, status) "
            "VALUES (?, 'r1', ?, ?, ?, ?, ?)",
            (f"e{idx}", model_id, dataset_id, metric, value, status),
        )
        if not compatible:
            log.warning(
                "metric '%s' incompatible with model '%s' problem_type '%s' -> skipped (FR-003 compatibility gate)",
                metric, model_id, problem_type,
            )
        results[status] += 1
    conn.commit()
    return results


def main():
    conn = sqlite3.connect(":memory:")
    try:
        build_schema(conn)
        schema_ok = True
    except sqlite3.Error as e:
        schema_ok = False
        log.error("schema creation failed: %s", e)
        raise

    seed_fixtures(conn)
    results = run_evaluations(conn)

    total_combinations_tested = len(SYNTHETIC_RUN_REQUESTS)
    summary = {
        "note": "실제 업로드 데이터 없음 — 합성 픽스처로 스키마/호환성 로직만 검증",
        "schema_created": schema_ok,
        "total_combinations_tested": total_combinations_tested,
        "success_count": results["success"],
        "skipped_incompatible_count": results["skipped_incompatible"],
        "metric_compatibility_map": {k: sorted(v) for k, v in METRIC_COMPATIBILITY.items()},
    }

    out_path = pathlib.Path(__file__).parent / "summary.json"
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("summary written to %s", out_path)
    log.info(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
