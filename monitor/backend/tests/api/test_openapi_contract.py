"""OpenAPI 명세 동기화 (ADR-011 §7, 02 §6) — `workspace/project/contracts/openapi.json` 은 export 로만."""

from __future__ import annotations

import importlib.util
import json

from backend_support import BACKEND_DIR, REPO_ROOT

SPEC_PATH = REPO_ROOT / "workspace" / "project" / "contracts" / "openapi.json"


def _export_module():
    path = BACKEND_DIR / "scripts" / "export_openapi.py"
    spec = importlib.util.spec_from_file_location("export_openapi_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_committed_spec_matches_code() -> None:
    assert SPEC_PATH.read_text(encoding="utf-8") == _export_module().render(), (
        "openapi.json 이 코드와 다르다 — export_openapi.py 와 openapi_docs.py render 를 다시 실행"
    )


def test_spec_paths_error_enum_and_no_static() -> None:
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    assert spec["openapi"].startswith("3.")
    paths = set(spec["paths"])
    assert {
        "/api/v1/pipeline",
        "/api/v1/plan",
        "/api/v1/tasks",
        "/api/v1/memory",
    } <= paths
    assert all(p.startswith("/api/v1/") for p in paths)
    enum = set(spec["components"]["schemas"]["ErrorCode"]["enum"])
    assert enum == {
        "VALIDATION_ERROR", "NOT_FOUND", "METHOD_NOT_ALLOWED", "BAD_HOST", "FORBIDDEN_ORIGIN",
        "NO_ACTIVE_LOOP", "TOO_MANY_STREAMS", "CONTROL_WRITE_FAILED", "INTERNAL_ERROR",
    }  # fmt: skip
    assert "HTTPValidationError" not in spec["components"]["schemas"]
    tasks_params = {
        p["name"] for p in spec["paths"]["/api/v1/tasks"]["get"]["parameters"]
    }
    assert tasks_params == {"team", "status", "phase"}
    assert spec["servers"][0]["url"].startswith("http://127.0.0.1:")
