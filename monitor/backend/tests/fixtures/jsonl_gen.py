"""가짜 Claude Code JSONL 생성기 (30 EDA `bench_synthetic.py` 이식).

원본은 "실제 기록의 줄 길이 분포"를 읽어 모양을 흉내 냈지만, 여기서는 실제 기록을 전혀 읽지 않고
seed 로 결정적으로 만든다 (CON-06, 02 §5). 같은 인자 -> 같은 바이트.

30 EDA 에서 가져온 특성:
- 같은 requestId 가 여러 줄(응답 1개가 최대 7줄) -> 중복 제거 대상
- `"usage":` 문자열은 있지만 `message.usage` 가 없는 줄(거짓 양성)
- 서브에이전트 기록은 `<세션>/subagents/agent-*.jsonl`
- 한 줄 최대 약 236 KB, timestamp 는 UTC `Z`

생성기는 기대값(`JsonlManifest`)도 함께 계산한다. 수집기 테스트는 이 기대값과 비교한다.
기대값 규칙은 ADR-002 §4: requestId 단위 last-wins, requestId 없는 줄은 각각 1건.
"""

from __future__ import annotations

import json
import os
import random
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

from . import markers

FIXED_NOW = datetime(2026, 10, 23, 9, 0, 0, tzinfo=UTC)
DEFAULT_SEED = 20261023

MODELS = ("claude-fake-opus", "claude-fake-sonnet")
TOKEN_KEYS = (
    "input_tokens",
    "output_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
)
GIANT_LINE_BYTES = 236_000  # 30 EDA 실측 최대 줄 길이

_AUTO = object()  # request_id 인자 미지정 표시 (None 은 'requestId 없음')

BucketKey = tuple[
    str, str, bool
]  # (UTC 시각 'YYYY-MM-DDTHH:00:00Z', 모델, isSidechain)


@dataclass
class UsageTotals:
    responses: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0

    def add(self, usage: dict[str, int]) -> None:
        self.responses += 1
        for key in TOKEN_KEYS:
            setattr(self, key, getattr(self, key) + usage[key])


@dataclass
class JsonlManifest:
    """생성 결과와 기대값. `expected_buckets` 가 수집기 집계의 정답이다."""

    project_dir: Path
    files: list[Path] = field(default_factory=list)
    expired_files: list[Path] = field(
        default_factory=list
    )  # mtime 30일 초과 -> 수집 제외
    truncated_files: list[Path] = field(default_factory=list)  # 마지막 줄에 개행 없음
    counts: Counter[str] = field(default_factory=Counter)
    bytes_written: int = 0
    _by_request: dict[str, tuple[BucketKey, dict[str, int]]] = field(
        default_factory=dict
    )
    _anonymous: list[tuple[BucketKey, dict[str, int]]] = field(default_factory=list)

    def record_response(
        self, request_id: str | None, key: BucketKey, usage: dict[str, int]
    ) -> None:
        if request_id is None:
            self._anonymous.append((key, usage))
        else:
            self._by_request[request_id] = (key, usage)  # last-wins

    @property
    def unique_responses(self) -> int:
        return len(self._by_request) + len(self._anonymous)

    @property
    def expected_buckets(self) -> dict[BucketKey, UsageTotals]:
        buckets: dict[BucketKey, UsageTotals] = {}
        for key, usage in [*self._by_request.values(), *self._anonymous]:
            buckets.setdefault(key, UsageTotals()).add(usage)
        return buckets

    @property
    def expected_totals(self) -> UsageTotals:
        total = UsageTotals()
        for t in self.expected_buckets.values():
            total.responses += t.responses
            for key in TOKEN_KEYS:
                setattr(total, key, getattr(total, key) + getattr(t, key))
        return total


def _dump(obj: object) -> bytes:
    return json.dumps(obj, ensure_ascii=False).encode("utf-8")


def _iso(ts: datetime, ms: int = 0) -> str:
    return ts.strftime("%Y-%m-%dT%H:%M:%S.") + f"{ms:03d}Z"


def _hour_key(ts: datetime, model: str, sidechain: bool) -> BucketKey:
    return (ts.strftime("%Y-%m-%dT%H:00:00Z"), model, sidechain)


class _Generator:
    def __init__(
        self, project_dir: Path, seed: int, end: datetime, body_pad: int
    ) -> None:
        self.rng = random.Random(seed)
        self.end = end
        self.body_pad = body_pad
        self.manifest = JsonlManifest(project_dir=project_dir)
        self._request_seq = 0
        self._line_seq = 0

    # ---- 난수 (random.Random 의 randrange/getrandbits 만 쓴다: 버전 간 안정적)
    def new_session_id(self) -> str:
        return str(uuid.UUID(int=self.rng.getrandbits(128), version=4))

    def usage(self) -> dict[str, int]:
        r = self.rng
        return {
            "input_tokens": 1 + r.randrange(8),
            "output_tokens": 20 + r.randrange(900),
            "cache_creation_input_tokens": r.randrange(2000),
            "cache_read_input_tokens": 1000 + r.randrange(60000),
        }

    def request_id(self) -> str:
        self._request_seq += 1
        return f"req_{markers.REQUEST_ID}_{self._request_seq:08d}"

    # ---- 줄 만들기
    def _envelope(self, kind: str, ts: datetime, session: str, sidechain: bool) -> dict:
        self._line_seq += 1
        n = self._line_seq
        return {
            "type": kind,
            "timestamp": _iso(ts, self.rng.randrange(1000)),
            "sessionId": f"{markers.SESSION}-{session}",
            "uuid": f"{markers.UUID}-{n:08d}",
            "parentUuid": f"{markers.UUID}-{n - 1:08d}",
            "cwd": f"/home/{markers.CWD}/project",
            "gitBranch": "main",
            "version": "0.0.0-fake",
            "userType": "external",
            "isSidechain": sidechain,
            "extraNote": f"{markers.EXTRA}-{n}",  # 허용 목록 밖의 임의 키
        }

    def _content(self, pad: int | None = None) -> list[dict]:
        pad = self.body_pad if pad is None else pad
        text = (
            f"{markers.BODY} fake conversation text at {markers.PATH}/secret.txt "
            # JSON 직렬화되면 \" 로 이스케이프되어 줄 바이트에 `"usage":` 가 생기지 않는다
            'mentions "usage": in prose. ' + "x" * pad
        )
        return [
            {"type": "text", "text": text},
            {
                "type": "tool_use",
                "name": "Read",
                "input": {"file_path": f"/{markers.TOOL}/in.txt"},
            },
        ]

    def user_line(self, ts: datetime, session: str, sidechain: bool = False) -> dict:
        line = self._envelope("user", ts, session, sidechain)
        line["message"] = {"role": "user", "content": self._content()}
        return line

    def false_positive_line(
        self, ts: datetime, session: str, sidechain: bool = False
    ) -> dict:
        """`"usage":` 키는 있지만 `message.usage` 는 없는 줄 (도구 결과, 30 EDA 11.7%)."""
        line = self.user_line(ts, session, sidechain)
        line["toolUseResult"] = {
            "output": f"{markers.TOOL} result",
            "usage": {
                "input_tokens": markers.FALSE_POSITIVE_TOKENS,
                "output_tokens": markers.FALSE_POSITIVE_TOKENS,
            },
        }
        return line

    def assistant_line(
        self,
        ts: datetime,
        session: str,
        sidechain: bool,
        *,
        request_id: str | None,
        model: str,
        usage: object,
        pad: int | None = None,
    ) -> dict:
        line = self._envelope("assistant", ts, session, sidechain)
        if request_id is not None:
            line["requestId"] = request_id
        line["message"] = {
            "id": f"msg_{markers.UUID}",
            "role": "assistant",
            "model": model,
            "content": self._content(pad),
            "usage": usage,
        }
        return line


class _FileBuffer:
    """한 파일에 쓸 줄을 모으며 manifest 의 줄 통계를 갱신한다."""

    def __init__(self, gen: _Generator, path: Path) -> None:
        self.gen, self.path = gen, path
        self.chunks: list[bytes] = []
        self.last_ts = gen.end

    def raw(self, data: bytes, category: str) -> None:
        self.chunks.append(data)
        self.gen.manifest.counts["lines_total"] += 1
        self.gen.manifest.counts[category] += 1

    def obj(self, obj: dict, category: str, ts: datetime | None = None) -> None:
        self.raw(_dump(obj), category)
        if ts is not None:
            self.last_ts = ts

    def response(
        self,
        ts: datetime,
        session: str,
        sidechain: bool,
        *,
        duplicate_ratio: float = 0.0,
        request_id: str | None | object = _AUTO,
        usage: dict[str, int] | None = None,
        pad: int | None = None,
    ) -> None:
        """응답 1개 = 줄 1~7개(같은 requestId, 같은 usage). 앞에 사용자 줄을 붙인다."""
        gen = self.gen
        rid = gen.request_id() if request_id is _AUTO else request_id
        usage = usage or gen.usage()
        model = MODELS[gen.rng.randrange(len(MODELS))]
        self.obj(gen.user_line(ts, session, sidechain), "no_usage_lines")
        if gen.rng.randrange(8) == 0:
            self.obj(
                gen.false_positive_line(ts, session, sidechain),
                "usage_string_only_lines",
            )
        copies = 1
        if gen.rng.randrange(1000) < int(duplicate_ratio * 1000):
            copies += 1 + gen.rng.randrange(6)
        for _ in range(copies):
            line = gen.assistant_line(
                ts,
                session,
                sidechain,
                request_id=rid,
                model=model,
                usage=usage,
                pad=pad,
            )
            self.obj(line, "usage_lines", ts)
        gen.manifest.counts["duplicate_lines"] += copies - 1 if rid is not None else 0
        if rid is None:
            gen.manifest.counts["no_request_id_lines"] += copies
            for _ in range(copies):
                gen.manifest.record_response(
                    None, _hour_key(ts, model, sidechain), usage
                )
        else:
            gen.manifest.record_response(rid, _hour_key(ts, model, sidechain), usage)

    def flush(
        self, *, mtime: datetime | None = None, trailing_newline: bool = True
    ) -> Path:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = b"\n".join(self.chunks)
        if self.chunks and trailing_newline:
            data += b"\n"
        self.path.write_bytes(data)
        stamp = (mtime or self.last_ts).timestamp()
        os.utime(self.path, (stamp, stamp))
        self.gen.manifest.bytes_written += len(data)
        return self.path


def _write_edge_cases(gen: _Generator, project_dir: Path) -> None:
    """수집기가 견뎌야 하는 입력. 각 줄의 처리 결과는 manifest 에 반영한다."""
    session = gen.new_session_id()
    ts = gen.end - timedelta(hours=2)
    buf = _FileBuffer(gen, project_dir / f"edge-{session}.jsonl")

    buf.obj(gen.user_line(ts, session), "no_usage_lines")  # usage 없는 줄
    buf.obj(
        gen.false_positive_line(ts, session), "usage_string_only_lines"
    )  # 키만 `usage`
    buf.raw(b"", "no_usage_lines")  # 빈 줄
    # message.usage 가 dict 가 아님 -> 버리고 건수만 (P-04)
    buf.obj(
        gen.assistant_line(
            ts,
            session,
            False,
            request_id=gen.request_id(),
            model=MODELS[0],
            usage="n/a",
        ),
        "invalid_usage_lines",
    )
    # 깨진 JSON 두 종류. 사전 필터는 통과하므로 json.loads 가 실패해야 한다 (T-08: 줄 내용이 로그에 남으면 안 됨)
    buf.raw(
        b'{"timestamp": "'
        + _iso(ts).encode()
        + b'", "message": {"usage": {"input_tokens": ',
        "broken_lines",
    )
    buf.raw(
        b'\xff\xfe {"usage": ' + markers.BODY.encode(), "broken_lines"
    )  # UTF-8 아님
    # requestId 없음: 중복 제거 없이 1건 (WARN 건수만)
    buf.response(ts, session, False, request_id=None)
    # last-wins: 같은 requestId, 값이 다른 두 줄 -> 뒤의 값만 집계
    rid = gen.request_id()
    first, second = gen.usage(), gen.usage()
    buf.response(ts, session, False, request_id=rid, usage=first)
    buf.response(
        ts + timedelta(seconds=1), session, False, request_id=rid, usage=second
    )
    gen.manifest.counts["duplicate_lines"] += (
        1  # 두 번째 호출이 첫 값을 덮어쓴다 (last-wins)
    )
    # 한 줄 약 236 KB (30 EDA 최대)
    buf.response(ts, session, False, pad=GIANT_LINE_BYTES)
    gen.manifest.files.append(buf.flush(mtime=ts))

    # 잘린 마지막 줄: 완전한 줄 1개 + 개행 없는 조각. 조각은 처리하지 않고 다음 주기로 미룬다 (ADR-002 §2)
    session = gen.new_session_id()
    buf = _FileBuffer(gen, project_dir / f"truncated-tail-{session}.jsonl")
    buf.response(ts, session, False)
    buf.chunks.append(
        b'{"type": "assistant", "message": {"usage": {"input_tokens": 5, "x": "'
        + markers.BODY.encode()
    )
    gen.manifest.counts["truncated_tail_lines"] += 1
    gen.manifest.truncated_files.append(buf.flush(mtime=ts, trailing_newline=False))
    gen.manifest.files.append(buf.path)

    # mtime 30일 초과 파일은 건너뛴다 (집계 기대값에서 제외하려고 manifest 기록 없이 따로 쓴다)
    session = gen.new_session_id()
    old = gen.end - timedelta(days=40)
    expired = _FileBuffer(gen, project_dir / f"expired-{session}.jsonl")
    snapshot = (
        gen.manifest._by_request.copy(),
        list(gen.manifest._anonymous),
        Counter(gen.manifest.counts),
    )
    expired.response(old, session, False)
    gen.manifest._by_request, gen.manifest._anonymous, gen.manifest.counts = (
        snapshot  # 기대값에서 제외
    )
    gen.manifest.expired_files.append(expired.flush(mtime=old))


def write_project_jsonl(
    project_dir: Path,
    *,
    seed: int = DEFAULT_SEED,
    end: datetime = FIXED_NOW,
    days: int = 30,
    responses_per_day: int = 12,
    duplicate_ratio: float = 0.45,
    subagent_every: int = 3,
    agents_per_session: int = 2,
    responses_per_agent: int = 4,
    body_pad: int = 0,
    edge_cases: bool = True,
) -> JsonlManifest:
    """`project_dir`(= `<CLAUDE_HOME>/projects/<enc>`) 아래에 날짜별 세션 JSONL 을 만든다.

    - 하루 1세션 파일, `subagent_every` 일마다 `<세션>/subagents/agent-*.jsonl` 추가
    - `body_pad`: 줄마다 붙이는 본문 채움 바이트. 성능 fixture 는 이 값으로 크기를 키운다
      (30일 329~658 MB 재현은 test-strategy.md §5 의 perf 절차 참고)
    - `edge_cases`: 깨진 줄·거짓 양성·잘린 줄·거대 줄·만료 파일 포함
    """
    gen = _Generator(project_dir, seed, end, body_pad)
    project_dir.mkdir(parents=True, exist_ok=True)
    for d in range(days - 1, -1, -1):  # 오래된 날부터
        day_start = (end - timedelta(days=d)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        span = min(86400, int((end - day_start).total_seconds()) - 1)
        session = gen.new_session_id()
        buf = _FileBuffer(gen, project_dir / f"{session}.jsonl")
        for k in range(responses_per_day):
            buf.response(
                day_start + timedelta(seconds=span * k // max(responses_per_day, 1)),
                session,
                False,
                duplicate_ratio=duplicate_ratio,
            )
        gen.manifest.files.append(buf.flush())
        if subagent_every and d % subagent_every == 0:
            for _ in range(agents_per_session):
                agent = _FileBuffer(
                    gen,
                    project_dir
                    / session
                    / "subagents"
                    / f"agent-{gen.rng.getrandbits(28):07x}.jsonl",
                )
                for k in range(responses_per_agent):
                    agent.response(
                        day_start
                        + timedelta(
                            seconds=span * (k + 1) // (responses_per_agent + 1)
                        ),
                        session,
                        True,
                        duplicate_ratio=duplicate_ratio,
                    )
                gen.manifest.files.append(agent.flush())
    if edge_cases:
        _write_edge_cases(gen, project_dir)
    return gen.manifest
