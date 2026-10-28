"""app/eval/repository.py — 데이터 접근 계층 (SQLite, 표준 `sqlite3`, ORM 없음).

소유권 (workspace/teams/dba/charter.md §2, §10):
  - 이 파일 상단의 스키마 DDL 블록(``SCHEMA_DDL`` 상수, ``init_schema``)은 **dba 팀 소유**다.
  - 아래 "쿼리 함수" 영역의 실제 SELECT/INSERT/UPDATE 구현은 **backend 팀 소유** (T-009, deps: T-003/T-005)이며
    dba 는 이 영역을 수정하지 않는다.

ERD 출처: workspace/project/30-data-analysis.md §5.1 (04§2 원안 + §5.2 제안 필드 그대로 확정).
마이그레이션 정책: 별도 마이그레이션 프레임워크 없음(1일 프로젝트, user/02§1 "선호" 수준 준수).
  스키마를 변경할 때는 이 ``SCHEMA_DDL`` 문자열을 직접 고치고, 변경 전/후 DDL 과 되돌리는 방법
  (예: 신규 컬럼이면 ``ALTER TABLE ... DROP COLUMN`` 또는 테이블 재생성 스크립트)을
  workspace/memory/short-term.md 작업 로그 + workspace/teams/dba/charter.md §3 산출물 설명에 남긴다.
  현재는 최초 스키마 생성이므로 되돌리기 = 테이블 전체 DROP (운영 데이터 없음 전제, 1인 로컬 SQLite).

동시성: WAL 모드 등 락 최적화는 도입하지 않음 — NFR-004(동시 사용자 1명)로 리스크가 매우 낮아
과설계(03 원칙 1)로 판단함. 필요해지면 그때 ``PRAGMA journal_mode=WAL`` 도입을 재검토한다.

(model, dataset) 재업로드 정책: **확정** — 항상 신규 레코드(새 UUID)를 INSERT 하며, 기존
레코드를 매칭해 UPDATE 하는 로직은 두지 않는다(ADR-004, workspace/memory/long-term.md D-15).
`model_dataset_link` 는 (model_id, dataset_id) 복합 PK 로 "링크" 중복 삽입만 차단한다(변경 없음).
아래 쿼리 함수(`create_model`/`create_dataset`)는 이 정책을 그대로 구현한다 — 동일한
name/path 로 여러 번 호출해도 매번 새 id 의 레코드가 추가된다.
"""

import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

# --- 스키마 DDL (dba 소유 — CREATE TABLE / CREATE INDEX 만) ------------------------
# ERD: workspace/project/30-data-analysis.md §5.1
#   MODEL(id, name, path, framework, problem_type, problem_type_source)
#   DATASET(id, name, path)
#   MODEL_DATASET_LINK(model_id FK, dataset_id FK)  — N:M 연결 (FR-001)
#   RUN(id, created_at)
#   EVALUATION(id, run_id FK, model_id FK, dataset_id FK, metric, value, status)
# model.problem_type / problem_type_source, evaluation.status 는 30§5.2 제안을 그대로 반영
# (D-03/D-04, workspace/memory/long-term.md).

SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS model (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    path TEXT NOT NULL,
    framework TEXT NOT NULL CHECK (framework IN ('pytorch', 'sklearn')),
    problem_type TEXT NOT NULL CHECK (problem_type IN ('classification', 'regression')),
    problem_type_source TEXT NOT NULL CHECK (problem_type_source IN ('user_declared', 'inferred'))
        DEFAULT 'user_declared'
);

CREATE TABLE IF NOT EXISTS dataset (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    path TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS model_dataset_link (
    model_id TEXT NOT NULL REFERENCES model(id),
    dataset_id TEXT NOT NULL REFERENCES dataset(id),
    PRIMARY KEY (model_id, dataset_id)
);

CREATE TABLE IF NOT EXISTS run (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evaluation (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES run(id),
    model_id TEXT NOT NULL REFERENCES model(id),
    dataset_id TEXT NOT NULL REFERENCES dataset(id),
    metric TEXT NOT NULL CHECK (metric IN ('accuracy', 'f1', 'rmse')),
    value REAL,
    status TEXT NOT NULL CHECK (status IN ('success', 'skipped_incompatible', 'error'))
        DEFAULT 'success'
);

-- 인덱스 (KPI-02: Run 당 완료/입력 모델 수 집계용, 30§7·workspace/teams/dba/charter.md §5).
-- KPI-02 분자/분모 집계는 run_id 로 그룹핑 후 status 로 필터링한다(D-04) -> (run_id, status) 복합 인덱스.
CREATE INDEX IF NOT EXISTS idx_evaluation_run_status ON evaluation(run_id, status);
-- 특정 모델이 참여한 모든 평가 조회(모델 삭제/이력 조회 등)를 위한 model_id 인덱스.
CREATE INDEX IF NOT EXISTS idx_evaluation_model ON evaluation(model_id);
-- model_dataset_link 의 PK(model_id, dataset_id) 복합 인덱스는 model_id 선두 조회만 커버하므로,
-- "이 데이터셋을 쓰는 모델 목록" 역방향 조회를 위해 dataset_id 단독 인덱스를 별도로 둔다.
CREATE INDEX IF NOT EXISTS idx_model_dataset_link_dataset ON model_dataset_link(dataset_id);
"""


def init_schema(conn: sqlite3.Connection) -> None:
    """스키마(테이블+인덱스)를 생성한다. 이미 존재하면 아무 동작도 하지 않는다(``IF NOT EXISTS``).

    이 함수는 DDL 실행만 담당한다(dba 소유). CRUD 쿼리 함수는 backend 가
    T-009(Repository 모듈 구현)에서 이 파일 하단에 추가한다.
    """
    conn.executescript(SCHEMA_DDL)


# --- 쿼리 함수 (backend 소유 — T-009 에서 구현, deps: T-003/T-005) -------------------
# dba 는 이 영역의 함수 본문을 작성하지 않는다 (workspace/teams/dba/charter.md §2 "하지 않음").

# 기본 DB 파일 경로 (20§4: 로컬 파일 저장소 = workspace/data/). 단위 테스트는 ":memory:" 를
# 직접 넘겨 이 기본값과 분리된 상태로 검증한다(테스트가 실제 파일을 건드리지 않음, 02§5).
DEFAULT_DB_PATH = "workspace/data/ml_miniops.db"


class RepositoryError(Exception):
    """Repository 계층에서 발생하는 오류의 공통 베이스. 프레임워크(FastAPI)에 의존하지 않는다 —
    API 라우터(T-010/T-011/T-013/T-015)가 이 예외를 잡아 HTTPException(4xx)으로 변환한다."""


class NotFoundError(RepositoryError):
    """FK 로 참조하는 대상 레코드(model/dataset/run)가 존재하지 않을 때 발생한다.

    SQLite 의 `PRAGMA foreign_keys = ON` 설정(T-029, LTM I-03)과는 독립적으로, 참조 무결성을
    애플리케이션 레벨에서 먼저 검증해 FR-001 AC-5("미업로드 대상 연결 시도 시 4xx") 등의
    동작을 PRAGMA 설정 여부와 상관없이 보장한다.
    """


def get_connection(db_path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """SQLite 커넥션을 열고 스키마를 보장한 뒤 반환한다.

    `db_path=":memory:"` 를 넘기면 디스크에 파일을 만들지 않는 인메모리 DB 를 사용한다(단위 테스트용).
    그 외에는 상위 디렉토리(`workspace/data/`)가 없으면 생성한다 — 02§11 "사용자 업로드 데이터
    삭제 금지" 와는 무관하게, 디렉토리 생성만 수행하고 기존 파일은 건드리지 않는다.
    """
    if db_path != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    # check_same_thread=False: FastAPI(Starlette)는 동기 의존성/엔드포인트를 스레드풀에서
    # 실행하므로(T-010, app/api/models.py `get_db`), 커넥션을 연 스레드와 실제 쿼리를 실행하는
    # 스레드가 달라질 수 있다. NFR-004(동시 사용자 1명, 동시성 제어 생략)로 실제 동시 접근
    # 경쟁은 없다고 전제하므로 락 등 추가 동기화 없이 이 플래그만으로 충분하다(03 원칙 1).
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # T-029 (LTM I-03): SQLite 는 연결마다 이 PRAGMA 를 실행해야 SCHEMA_DDL 의 `REFERENCES`
    # 제약이 실제로 강제된다 — 기본값은 OFF 라 설정하지 않으면 FK 위반이 조용히 통과한다.
    # 애플리케이션 레벨 검사(create_link/create_evaluation 의 NotFoundError, D-17)와 상호보완적인
    # DB 레벨 2차 방어선이며, 커넥션을 새로 열 때마다(get_connection 호출마다) 다시 설정해야 한다.
    conn.execute("PRAGMA foreign_keys = ON")
    init_schema(conn)
    return conn


def _row_to_dict(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row is not None else None


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


# --- Model -------------------------------------------------------------------------


def create_model(
    conn: sqlite3.Connection,
    *,
    name: str,
    path: str,
    framework: str,
    problem_type: str,
    problem_type_source: str = "user_declared",
) -> str:
    """Model 레코드를 생성한다. (model, dataset) 재업로드 정책(ADR-004, D-15)에 따라 항상
    새 UUID 로 신규 레코드를 INSERT 한다 — 기존 name/path 매칭 후 UPDATE 하는 경로는 없다."""
    model_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO model (id, name, path, framework, problem_type, problem_type_source) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (model_id, name, path, framework, problem_type, problem_type_source),
    )
    conn.commit()
    return model_id


def get_model(conn: sqlite3.Connection, model_id: str) -> dict | None:
    row = conn.execute("SELECT * FROM model WHERE id = ?", (model_id,)).fetchone()
    return _row_to_dict(row)


def list_models(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT * FROM model ORDER BY id").fetchall()
    return [dict(row) for row in rows]


# --- Dataset -----------------------------------------------------------------------


def create_dataset(conn: sqlite3.Connection, *, name: str, path: str) -> str:
    """Dataset 레코드를 생성한다. Model 과 동일하게 항상 신규 레코드를 INSERT 한다(ADR-004, D-15)."""
    dataset_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO dataset (id, name, path) VALUES (?, ?, ?)",
        (dataset_id, name, path),
    )
    conn.commit()
    return dataset_id


def get_dataset(conn: sqlite3.Connection, dataset_id: str) -> dict | None:
    row = conn.execute("SELECT * FROM dataset WHERE id = ?", (dataset_id,)).fetchone()
    return _row_to_dict(row)


def list_datasets(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT * FROM dataset ORDER BY id").fetchall()
    return [dict(row) for row in rows]


# --- Model-Dataset Link (FR-001, N:M) -----------------------------------------------


def create_link(conn: sqlite3.Connection, *, model_id: str, dataset_id: str) -> None:
    """Link(model_id, dataset_id) 1건을 생성한다 (FR-001 AC-1/AC-2/AC-3).

    - 존재하지 않는 model_id/dataset_id 면 `NotFoundError` 를 올린다(FR-001 AC-5, 4xx 매핑은
      호출자인 API 라우터 책임).
    - 동일 조합이 이미 있으면 `model_dataset_link` 의 복합 PK 제약으로 `sqlite3.IntegrityError`
      가 그대로 전파된다 — 중복 연결 허용 여부는 아직 결정되지 않았으므로(stories/FR-001.md
      Out of scope) 이 함수가 임의로 흡수/무시하지 않는다.
    """
    if get_model(conn, model_id) is None:
        raise NotFoundError(f"model not found: {model_id}")
    if get_dataset(conn, dataset_id) is None:
        raise NotFoundError(f"dataset not found: {dataset_id}")
    conn.execute(
        "INSERT INTO model_dataset_link (model_id, dataset_id) VALUES (?, ?)",
        (model_id, dataset_id),
    )
    conn.commit()


def list_links(conn: sqlite3.Connection) -> list[dict]:
    """등록된 모든 Link 를 (model_id, dataset_id) 쌍으로 빠짐없이 반환한다(FR-001 AC-4)."""
    rows = conn.execute(
        "SELECT model_id, dataset_id FROM model_dataset_link ORDER BY model_id, dataset_id"
    ).fetchall()
    return [dict(row) for row in rows]


# --- Run (FR-004) -------------------------------------------------------------------


def create_run(conn: sqlite3.Connection, *, created_at: str | None = None) -> str:
    """Run 레코드 1건을 생성한다. `created_at` 을 넘기지 않으면 UTC ISO-8601 현재 시각을 쓴다."""
    run_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO run (id, created_at) VALUES (?, ?)",
        (run_id, created_at or _utc_now_iso()),
    )
    conn.commit()
    return run_id


def get_run(conn: sqlite3.Connection, run_id: str) -> dict | None:
    row = conn.execute("SELECT * FROM run WHERE id = ?", (run_id,)).fetchone()
    return _row_to_dict(row)


# --- Evaluation (FR-004) -------------------------------------------------------------


def create_evaluation(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    model_id: str,
    dataset_id: str,
    metric: str,
    value: float | None,
    status: str = "success",
) -> str:
    """Evaluation 레코드 1건을 생성한다 (FR-004 AC-1/AC-2/AC-3/AC-4).

    비호환(skipped_incompatible) 또는 실패(error) 조합도 `value=NULL` 로 레코드를 남긴다
    (ADR-003, D-04 — KPI-02 집계가 레코드 자체는 누락시키지 않도록 함, LTM §2 패턴).
    run_id/model_id/dataset_id 가 존재하지 않으면 `NotFoundError` 를 올린다.
    """
    if get_run(conn, run_id) is None:
        raise NotFoundError(f"run not found: {run_id}")
    if get_model(conn, model_id) is None:
        raise NotFoundError(f"model not found: {model_id}")
    if get_dataset(conn, dataset_id) is None:
        raise NotFoundError(f"dataset not found: {dataset_id}")
    evaluation_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO evaluation (id, run_id, model_id, dataset_id, metric, value, status) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (evaluation_id, run_id, model_id, dataset_id, metric, value, status),
    )
    conn.commit()
    return evaluation_id


def list_evaluations_by_run(conn: sqlite3.Connection, run_id: str) -> list[dict]:
    """특정 Run 에 속한 모든 Evaluation 을 반환한다(FR-004 AC-2 "run_id 로 동일 Run 에 귀속",
    AC-5 `POST /runs` 응답 조립에 재사용 가능)."""
    rows = conn.execute(
        "SELECT * FROM evaluation WHERE run_id = ? ORDER BY id", (run_id,)
    ).fetchall()
    return [dict(row) for row in rows]
