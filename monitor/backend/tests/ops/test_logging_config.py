"""`app.logging_config.setup_logging()` — 02 §7, 20 §6 (본문·경로·ID 금지, access log 끔)."""

from __future__ import annotations

import io
import logging
import re

import pytest
from backend_support import make_client, make_settings
from fixtures import markers

from app import logging_config
from app import main as app_main
from app.logging_config import REDACTED, redact, setup_logging
from app.main import create_app

LINE = re.compile(
    r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} (DEBUG|INFO|WARNING|ERROR|CRITICAL) \S.*$"
)

pytestmark = pytest.mark.usefixtures("restore_logging")


def _ours() -> list[logging.Handler]:
    return [h for h in logging.getLogger().handlers if logging_config._is_ours(h)]


def test_format_time_level_message() -> None:
    stream = io.StringIO()
    setup_logging(stream=stream)
    logging.getLogger("aidlc_monitor.test").warning("tasks 파일 형식 오류 %d건", 2)
    lines = stream.getvalue().splitlines()
    assert len(lines) == 1
    assert LINE.match(lines[0]), "로그 줄 형식"
    assert lines[0].endswith("WARNING tasks 파일 형식 오류 2건")


def test_idempotent_single_handler() -> None:
    stream = io.StringIO()
    setup_logging(stream=io.StringIO())
    setup_logging(stream=stream)
    assert len(_ours()) == 1
    logging.getLogger("x").info("한 번")
    assert stream.getvalue().count("한 번") == 1


def test_main_setup_logging_delegates_to_ops() -> None:
    """T-005 연결 지점: `app.main.setup_logging()` 이 ops 구현을 부른다."""
    app_main.setup_logging()
    assert len(_ours()) == 1
    assert logging.getLogger("uvicorn.access").disabled


def test_uvicorn_access_log_disabled() -> None:
    stream = io.StringIO()
    setup_logging(stream=stream)
    access = logging.getLogger("uvicorn.access")
    access.info(
        '127.0.0.1:5000 - "GET /api/v1/usage?token=%s HTTP/1.1" 200', markers.SESSION
    )
    logging.getLogger("uvicorn.error").info("Uvicorn running on http://127.0.0.1:8765")
    out = stream.getvalue()
    assert markers.SESSION not in out
    assert "GET " not in out
    assert "http://127.0.0.1:8765" in out  # 시작 안내(URL)는 가리지 않는다
    assert access.disabled and not access.propagate and not access.handlers
    assert logging.getLogger("uvicorn.error").propagate


@pytest.mark.parametrize(
    "value",
    [
        f"/home/someone/.claude/projects/-home-someone-{markers.DIR_NAME}/a.jsonl",
        f"C:\\Users\\someone\\{markers.PATH}\\x.json",
        f"~/.claude/{markers.PATH}",
        f"\\\\server\\share\\{markers.PATH}",
        "123e4567-e89b-12d3-a456-426614174000",
        f"req_{markers.REQUEST_ID}",
        "msg_01AbCdEfGhIj",
        "sk-ant-api03-abcdefghijklmnop",
        "Bearer abc.def.ghi",
    ],
)
def test_redact_paths_ids_keys(value: str) -> None:
    out = redact(f"읽기 실패: {value} 끝")
    assert value not in out
    assert REDACTED in out
    assert out.startswith("읽기 실패: ") and out.endswith(" 끝")


def test_redact_keeps_plain_text_and_urls() -> None:
    text = "pipeline 패널 오류: KeyError http://127.0.0.1:8765 3건 N/A 10/23"
    assert redact(text) == text


def test_newlines_collapsed_to_one_line() -> None:
    stream = io.StringIO()
    setup_logging(stream=stream)
    logging.getLogger("x").warning("첫 줄\n2026-01-01 00:00:00,000 ERROR 위조된 줄")
    assert len(stream.getvalue().splitlines()) == 1


def test_exception_logs_type_only_no_traceback(tmp_path) -> None:
    stream = io.StringIO()
    setup_logging(stream=stream)
    secret = tmp_path / markers.PATH
    try:
        open(secret, encoding="utf-8")  # noqa: SIM115 — 일부러 실패
    except FileNotFoundError:
        logging.getLogger("x").exception("소스 읽기 실패")
    out = stream.getvalue()
    assert "Traceback" not in out
    assert "(FileNotFoundError)" in out
    assert str(tmp_path) not in out
    markers.assert_no_markers(out, where="exception log")


def test_bad_format_args_do_not_raise() -> None:
    record = logging.LogRecord(
        "x", logging.WARNING, __file__, 1, "인자 %d 개", ("문자",), None
    )
    out = logging_config.SafeFormatter().format(record)
    assert out.endswith("WARNING 로그 메시지 형식 오류: TypeError")


def test_app_logs_have_no_paths_or_markers(
    broken_workspace, claude_home_factory, tmp_path
) -> None:
    """깨진 workspace + 표식이 든 CLAUDE_HOME 으로 전 엔드포인트를 호출해도 로그에 경로·표식이 없다."""
    home = claude_home_factory(broken_workspace.root)
    stream = io.StringIO()
    setup_logging(stream=stream)
    from backend_support import install_engine

    install_engine(broken_workspace.root)
    app = create_app(make_settings(broken_workspace.root, claude_home=home.home))
    secret = f"{tmp_path}/{markers.PATH}/{markers.SESSION}"

    def boom() -> object:
        raise OSError(f"cannot read {secret}")

    class Warmup:
        def progress(self) -> object:
            raise RuntimeError(secret)

    app.state.services.pipeline.read = boom  # 패널 ERROR 로그 경로
    app.state.warmup = Warmup()  # health WARN 로그 경로
    client = make_client(app)
    for path in (
        "/api/v1/health",
        "/api/v1/pipeline",
        "/api/v1/plan",
        "/api/v1/tasks",
        "/api/v1/memory",
        f"/api/v1/{markers.PATH}?q={markers.SESSION}",
    ):
        client.get(path)
    client.get("/api/v1/health", headers={"host": f"evil-{markers.EXTRA}"})
    out = stream.getvalue()
    forbidden = (*home.forbidden_strings(), str(broken_workspace.root), str(tmp_path))
    assert " ERROR pipeline 패널 오류: OSError" in out  # 빈 로그로 통과하지 않게
    assert " WARNING 데우기 진행률을 읽지 못했습니다: RuntimeError" in out
    markers.assert_no_markers(out, extra=forbidden, where="app logs")
    for line in out.splitlines():
        assert LINE.match(line), "로그 줄 형식"
