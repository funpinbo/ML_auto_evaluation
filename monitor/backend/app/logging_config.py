"""콘솔 로그 설정 `setup_logging()` (02 §7, 20 §6, ops 소유).

규칙 (문구 규칙 상세: `workspace/project/ops/logging.md`):
- 포맷 `%(asctime)s %(levelname)s %(message)s`, stderr 한 줄. ERROR = 패널을 못 그림,
  WARNING = 파일 누락·형식 오류(파일 종류·건수만), INFO = 시작·소스 해석 결과(찾음/못 찾음).
- 대화 본문·파일 경로·sessionId/requestId·토큰을 남기지 않는다. 호출하는 쪽이 지키는 것이 1차 방어이고,
  이 모듈의 포매터는 2차 방어로 경로·ID·키 모양 문자열을 가리고, 예외는 traceback 대신 예외 타입만 적는다
  (traceback 에는 설치 경로 = 사용자 홈이 들어간다).
- uvicorn access log 는 끈다(결정): 요청 줄에는 경로·쿼리 문자열이 그대로 들어간다. 요청 단위 관측이
  필요하면 경로 없이 상태 코드만 남기는 방식을 따로 만든다. `uvicorn.error`(시작·종료 메시지)는 root 로 보낸다.
- 여러 번 불러도 핸들러는 하나다(멱등).
"""

from __future__ import annotations

import logging
import re
import sys
from typing import IO

LOG_FORMAT = "%(asctime)s %(levelname)s %(message)s"
REDACTED = "<redacted>"
_HANDLER_FLAG = "_aidlc_monitor_handler"

# 2차 방어용 패턴. 순서대로 적용한다.
_PATTERNS: tuple[re.Pattern[str], ...] = (
    # API 키·토큰 모양 (sk-ant-..., Bearer ...)
    re.compile(r"\bsk-[A-Za-z0-9_-]{8,}"),
    re.compile(r"(?i)\bbearer\s+\S+"),
    # Windows 절대 경로·UNC 경로
    re.compile(r"\b[A-Za-z]:[\\/][^\s'\"<>|]*"),
    re.compile(r"\\\\[^\s'\"<>|]+"),
    # 홈 상대 경로
    re.compile(r"~[\\/][^\s'\"]*"),
    # POSIX 절대 경로 (구분자 2개 이상). URL 의 `//` 와 `scheme:/` 는 건드리지 않는다
    re.compile(r"(?<![\w.:/~-])/[^\s/'\"]+/[^\s'\"]*"),
    # UUID (sessionId·uuid), Claude 요청·메시지 ID
    re.compile(
        r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
    ),
    re.compile(r"\b(?:req|msg|toolu)_[A-Za-z0-9]{6,}"),
)


def redact(text: str) -> str:
    """경로·ID·키 모양 문자열을 가리고 줄바꿈을 공백으로 바꿔 한 줄로 만든다."""
    for pattern in _PATTERNS:
        text = pattern.sub(REDACTED, text)
    return " ".join(text.splitlines())


class SafeFormatter(logging.Formatter):
    """메시지를 가리고, traceback·stack 대신 예외 타입만 붙인다. 원본 레코드는 바꾸지 않는다."""

    def __init__(self) -> None:
        super().__init__(LOG_FORMAT)

    def format(self, record: logging.LogRecord) -> str:
        try:
            message = record.getMessage()
        except Exception as exc:  # noqa: BLE001 — 잘못된 %-인자도 로그 한 줄로 끝낸다
            message = f"로그 메시지 형식 오류: {type(exc).__name__}"
        clean = logging.makeLogRecord(record.__dict__)
        clean.msg = redact(message)
        clean.args = None
        clean.exc_info = None
        clean.exc_text = None
        clean.stack_info = None
        text = super().format(clean)
        if record.exc_info and record.exc_info[0] is not None:
            text += f" ({record.exc_info[0].__name__})"
        return text


def _is_ours(handler: logging.Handler) -> bool:
    return bool(getattr(handler, _HANDLER_FLAG, False))


def setup_logging(
    level: int = logging.INFO, stream: IO[str] | None = None
) -> logging.Handler:
    """root 에 콘솔 핸들러 하나를 둔다. `stream` 은 테스트용(기본 stderr)."""
    root = logging.getLogger()
    for handler in list(root.handlers):
        if _is_ours(handler):
            root.removeHandler(handler)
            handler.close()
    handler = logging.StreamHandler(stream if stream is not None else sys.stderr)
    handler.setFormatter(SafeFormatter())
    setattr(handler, _HANDLER_FLAG, True)
    root.addHandler(handler)
    root.setLevel(level)

    # uvicorn: 자체 핸들러를 걷어 root 로 보낸다. access log 는 끈다.
    for name in ("uvicorn", "uvicorn.error"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True
    access = logging.getLogger("uvicorn.access")
    access.handlers.clear()
    access.propagate = False
    access.disabled = True
    # 요청 URL 을 INFO 로 남기는 클라이언트 라이브러리 (테스트·런처 경로)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    return handler
