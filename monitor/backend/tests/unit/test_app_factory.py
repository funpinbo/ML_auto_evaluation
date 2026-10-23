"""앱 팩토리 훅: `uvicorn app.main:app` 지연 생성, ops 모듈(T-006) 선택 연결."""

from __future__ import annotations

import sys
import types

import pytest
from backend_support import TEST_PORT

import app.main as main_module


def test_lazy_module_app_reads_env(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setenv("AIDLC_ROOT", str(tmp_path))
    monkeypatch.setenv("AIDLC_MONITOR_PORT", str(TEST_PORT))
    monkeypatch.setattr(main_module, "setup_logging", lambda: None)
    monkeypatch.delitem(main_module.__dict__, "app", raising=False)
    instance = main_module.app
    assert instance.settings.port == TEST_PORT
    assert instance.settings.aidlc_root == tmp_path
    monkeypatch.delitem(main_module.__dict__, "app")
    with pytest.raises(AttributeError):
        main_module.__getattr__("nope")


def test_optional_ops_modules_are_wired(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    from fastapi import APIRouter

    called = []
    fake_logging = types.ModuleType("app.logging_config")
    fake_logging.setup_logging = lambda: called.append("logging")
    fake_health = types.ModuleType("app.api.health")
    router = APIRouter()

    @router.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    fake_health.router = router
    monkeypatch.setitem(sys.modules, "app.logging_config", fake_logging)
    monkeypatch.setitem(sys.modules, "app.api.health", fake_health)
    main_module.setup_logging()
    assert called == ["logging"]
    from app.config import Settings

    app = main_module.create_app(
        Settings(
            port=TEST_PORT, aidlc_root=tmp_path, claude_home=tmp_path, dist_dir=tmp_path
        )
    )
    from backend_support import make_client

    assert make_client(app).get("/api/v1/health").json() == {"status": "ok"}


def test_setup_logging_fallback_without_ops_module() -> None:
    assert main_module._optional_module("app.no_such_module_for_test") is None
    main_module.setup_logging()  # ops 모듈이 없으면 기본 설정 — 예외 없음


# ---------------------------------------------------------------- I-24 하드닝
def test_fastapi_telemetry_explicitly_disabled(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """사용자 환경의 OTEL·자동 구성 변수와 무관하게 네이티브 텔레메트리가 꺼져 있다."""
    from backend_support import make_settings

    monkeypatch.setenv("FASTAPI_OTEL_AUTO_CONFIGURE", "true")
    monkeypatch.setenv("OTEL_TRACES_EXPORTER", "otlp")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://127.0.0.1:9")
    app = main_module.create_app(make_settings(tmp_path))
    config = app._telemetry
    for key in ("tracing", "metrics", "logs", "operation_spans", "auto_configure"):
        assert config[key] is False, key  # type: ignore[literal-required]
    assert app._native_telemetry.enabled() is False


def test_uvicorn_runs_without_server_header(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.__main__ as entry

    captured: dict[str, object] = {}
    monkeypatch.setattr(entry, "setup_logging", lambda: None)
    monkeypatch.setattr(entry.uvicorn, "run", lambda app, **kw: captured.update(kw))
    monkeypatch.setenv("AIDLC_MONITOR_PORT", str(TEST_PORT))
    assert entry.main([]) == 0
    assert captured["server_header"] is False
    assert captured["access_log"] is False
    assert captured["host"] == "127.0.0.1" and captured["port"] == TEST_PORT


def test_asgi_receive_disconnect_is_short() -> None:
    import backend_support

    assert backend_support.RECEIVE_DISCONNECT_SEC <= 0.1
