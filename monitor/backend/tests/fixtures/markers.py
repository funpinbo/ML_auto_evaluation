"""본문 표식 문자열 (privacy.md §7, NFR-003 / QS-06).

fixture 가 만드는 모든 민감 값에 고유 표식을 심고, 응답·로그·집계 구조 어디에도
표식이 나타나지 않는지 `assert_no_markers` 로 검사한다.

표식은 영숫자만 쓴다. Claude Code 가 프로젝트 경로를 `[^A-Za-z0-9]` -> `-` 로 바꿔
디렉터리 이름을 만들기 때문에, 밑줄이 있으면 경로 인코딩 fixture 에서 표식이 깨진다.
"""

from __future__ import annotations

BODY = "QAMARKBODY7f3a91"  # message.content 본문
TOOL = "QAMARKTOOL2b84c0"  # tool_use 입력 / tool_result 출력
PATH = "QAMARKPATH51d9e7"  # 본문 안의 파일 경로
CWD = "QAMARKCWD0c6a4f"  # 줄의 cwd 필드
SESSION = "QAMARKSESS93e1b2"  # sessionId
UUID = "QAMARKUUID6d70a8"  # uuid / parentUuid
REQUEST_ID = "QAMARKREQ48f2d5"  # requestId (집계 구조에는 중복 제거 키로만 존재)
EXTRA = "QAMARKEXTRA1a9c3e"  # 허용 목록에 없는 임의 키의 값
DIR_NAME = "QAMARKDIR8e5b60"  # claude-status 의 transcript_dir_name 안
SETTINGS = "QAMARKSETT37c2f9"  # settings.json statusLine 명령 문자열
CREDENTIAL = "QAMARKCRED0f4d18"  # 열면 안 되는 가짜 자격 증명 파일 내용
ESCAPE = "QAMARKESC65b3a7"  # symlink 로 가리키는 `~/.claude` 밖 파일 내용

ALL_MARKERS: tuple[str, ...] = (
    BODY,
    TOOL,
    PATH,
    CWD,
    SESSION,
    UUID,
    REQUEST_ID,
    EXTRA,
    DIR_NAME,
    SETTINGS,
    CREDENTIAL,
    ESCAPE,
)

# 허용 필드 밖에서 오는 "사용량처럼 보이는" 숫자. 집계에 섞이면 곧바로 드러난다 (P-03).
FALSE_POSITIVE_TOKENS = 777_777


def find_markers(*texts: str | bytes, extra: tuple[str, ...] = ()) -> list[str]:
    """주어진 텍스트들에서 발견된 표식(중복 제거, 정의 순서)을 돌려준다."""
    haystack = "\n".join(
        t.decode("utf-8", "replace") if isinstance(t, bytes) else t for t in texts
    )
    return [m for m in (*ALL_MARKERS, *extra) if m in haystack]


def assert_no_markers(
    *texts: str | bytes, extra: tuple[str, ...] = (), where: str = ""
) -> None:
    """표식이 하나라도 있으면 실패한다. 실패 메시지에는 표식 종류만 적고 주변 내용은 적지 않는다."""
    found = find_markers(*texts, extra=extra)
    assert not found, f"본문 표식 노출{f' ({where})' if where else ''}: {found}"
