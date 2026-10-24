"""사용량 패널 조립 — 수집기 버킷 + 상태 스냅샷 (FR-004, ADR-002 §5·§7, ADR-003 §4).

- 버킷 합산만 한다(파싱 없음). 집계 단위는 UTC 1시간 버킷이다 — day 버킷은 `tz_offset_min` 으로 로컬 날짜에
  묶고, 5시간 구간은 구간과 겹치는 시간 버킷을 더한다.
- 소스 문제는 HTTP 200 + `meta.status` (NFR-002). 경고 문구는 고정 문자열(경로·이름 없음).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import UTC, datetime, timedelta, timezone

from app.models.envelope import SourceError, SourceErrorCode
from app.models.health import UsageWarming
from app.models.usage import (
    LimitWindow,
    SnapshotInfo,
    TokenSeries,
    TokenTotals,
    TokenWindow,
    UsageBucket,
    UsageGroup,
    UsageRange,
    UsageSummaryData,
    UsageTimeseriesData,
)
from app.services.panel import SOURCE_MESSAGES, Panel, iso_utc
from app.services.statusline_reader import Snapshot, StatuslineReader, Window
from app.services.usage.collector import UsageCollector, UsageView

RANGE_HOURS: dict[str, int] = {"5h": 5, "24h": 24, "7d": 168, "30d": 720}
FIVE_HOURS = 5 * 3600

NOTICE_NO_LIMITS = "한도 정보 없음 — Pro/Max 구독의 CLI 세션에서 첫 응답 이후 표시"
NOTICE_NO_SNAPSHOT = NOTICE_NO_LIMITS + " (CLI 세션에서 실행하면 한도가 표시됩니다)"
NOTICE_BROKEN = "한도 정보를 읽을 수 없음"
MSG_NO_PROJECT = "이 프로젝트의 Claude Code 기록을 찾을 수 없음"
MSG_EMPTY_RANGE = "선택한 기간에 기록 없음"
MSG_NO_USAGE = "사용 기록이 없습니다"
MSG_STALE = "{minutes}분 전 기준 — 최신 값이 아닐 수 있음"

Cell = tuple[int, int, int, int, int]


def totals(cells: Iterable[Cell]) -> TokenTotals:
    acc = [0, 0, 0, 0, 0]
    for cell in cells:
        for i in range(5):
            acc[i] += cell[i]
    denom = acc[1] + acc[3] + acc[4]
    return TokenTotals(
        responses=acc[0],
        input_tokens=acc[1],
        output_tokens=acc[2],
        cache_creation_input_tokens=acc[3],
        cache_read_input_tokens=acc[4],
        cache_hit_rate=round(acc[4] / denom, 6) if denom else None,
    )


def local_day(epoch_sec: float, tz_offset_min: int) -> int:
    return int((epoch_sec + tz_offset_min * 60) // 86400)


def _iso_local(day: int, tz_offset_min: int) -> str:
    tz = timezone(timedelta(minutes=tz_offset_min))
    utc_midnight = datetime.fromtimestamp(day * 86400 - tz_offset_min * 60, UTC)
    return utc_midnight.astimezone(tz).isoformat(timespec="seconds")


def _warming(view: UsageView) -> UsageWarming:
    state = (
        view.state if view.state in ("not_started", "warming", "done") else "unknown"
    )
    return UsageWarming(state=state, progress=view.progress)  # type: ignore[arg-type]


def _limit(window: Window | None, now: datetime) -> LimitWindow | None:
    if window is None:
        return None
    resets = window.resets_at
    return LimitWindow(
        used_percentage=window.used_percentage,
        resets_at=resets,
        resets_at_iso=iso_utc(datetime.fromtimestamp(resets, UTC))
        if resets is not None
        else None,
        reset_passed=(resets < now.timestamp()) if resets is not None else None,
    )


def _snapshot_info(snap: Snapshot, now: datetime) -> SnapshotInfo:
    stale = snap.state == "ok" and snap.stale(now)
    code: SourceErrorCode | None = {
        "missing": SourceErrorCode.SOURCE_MISSING,
        "broken": SourceErrorCode.SOURCE_PARSE_ERROR,
        "unreadable": SourceErrorCode.SOURCE_UNREADABLE,
    }.get(snap.state)
    if stale:
        code = SourceErrorCode.SNAPSHOT_STALE
    return SnapshotInfo(
        state=snap.state,
        captured_at=iso_utc(snap.captured_at) if snap.captured_at else None,
        age_sec=snap.age_sec(now),
        stale=stale,
        code=code,
    )


class UsageService:
    def __init__(
        self,
        collector: UsageCollector,
        reader: StatuslineReader,
        clock: Callable[[], datetime],
    ) -> None:
        self.collector = collector
        self.reader = reader
        self.clock = clock

    def _view(self) -> UsageView:
        self.collector.ensure_fresh()
        return self.collector.view()

    @staticmethod
    def _set_error(panel: Panel, code: SourceErrorCode, message: str) -> None:
        if panel.error is None:
            panel.error = SourceError(code=code, message=message)

    # ------------------------------------------------------------------ /usage/summary
    def summary(self, tz_offset_min: int = 0) -> Panel:
        panel = Panel()
        now = self.clock()
        now_ts = now.timestamp()
        view = self._view()
        snap = self.reader.read()
        if snap.mtime is not None:
            panel._mtime = snap.mtime
        info = _snapshot_info(snap, now)

        has_limits = snap.state == "ok" and snap.rate_limits_present
        five = _limit(snap.five_hour, now) if has_limits else None
        seven = _limit(snap.seven_day, now) if has_limits else None
        available = any(
            w is not None and w.used_percentage is not None for w in (five, seven)
        )
        notice: str | None = None
        if snap.state == "missing":
            notice = NOTICE_NO_SNAPSHOT
        elif snap.state in ("broken", "unreadable"):
            notice = NOTICE_BROKEN
            panel.warn(NOTICE_BROKEN)
        elif not available:
            notice = NOTICE_NO_LIMITS

        if not view.project_found:
            panel.warn(MSG_NO_PROJECT)
            self._set_error(
                panel, SourceErrorCode.PROJECT_DIR_NOT_FOUND, MSG_NO_PROJECT
            )
        if snap.state in ("broken", "unreadable") and info.code is not None:
            self._set_error(panel, info.code, NOTICE_BROKEN)
        if info.stale and info.age_sec is not None:
            message = MSG_STALE.format(minutes=info.age_sec // 60)
            panel.warn(message)
            self._set_error(panel, SourceErrorCode.SNAPSHOT_STALE, message)

        cells = view.buckets
        today = local_day(now_ts, tz_offset_min)
        today_start = today * 86400 - tz_offset_min * 60
        today_totals = totals(
            v
            for (hour, _m, _s), v in cells.items()
            if local_day(hour * 3600, tz_offset_min) == today
        )
        resets = snap.five_hour.resets_at if has_limits and snap.five_hour else None
        if resets is not None and resets > now_ts:
            start_ts, estimated = float(resets - FIVE_HOURS), False
        else:
            start_ts, estimated = now_ts - FIVE_HOURS, True
        five_totals = totals(
            v
            for (hour, _m, _s), v in cells.items()
            if (hour + 1) * 3600 > start_ts and hour * 3600 <= now_ts
        )
        panel.data = UsageSummaryData(
            scope="project",
            limits_available=available,
            limits_notice=notice,
            five_hour=five,
            seven_day=seven,
            snapshot=info,
            session_cost_usd=snap.total_cost_usd,
            session_duration_ms=snap.total_duration_ms,
            context_used_percentage=snap.context_used_percentage,
            model_id=snap.model_id,
            project_dir_found=view.project_found,
            tokens_code=None
            if view.project_found
            else SourceErrorCode.PROJECT_DIR_NOT_FOUND,
            today=TokenWindow(
                start=iso_utc(datetime.fromtimestamp(today_start, UTC)),
                end=iso_utc(now),
                estimated=False,
                totals=today_totals,
            ),
            five_hour_tokens=TokenWindow(
                start=iso_utc(datetime.fromtimestamp(start_ts, UTC)),
                end=iso_utc(now),
                estimated=estimated,
                totals=five_totals,
            ),
            skipped_lines=view.skipped_lines,
            warming=_warming(view),
        )
        if view.state == "warming":
            panel.status = "warming"
        elif not view.project_found and snap.state == "missing":
            panel.status = "empty"
            panel.warn(MSG_NO_USAGE)
        return panel

    # ------------------------------------------------------------------ /usage/timeseries
    def timeseries(
        self,
        range_: UsageRange = "24h",
        bucket: UsageBucket | None = None,
        group: UsageGroup = "model",
        tz_offset_min: int = 0,
    ) -> Panel:
        panel = Panel()
        now = self.clock()
        now_ts = now.timestamp()
        view = self._view()
        resolved: UsageBucket = bucket or ("day" if range_ == "30d" else "hour")
        hours = RANGE_HOURS[range_]
        end_hour = int(now_ts) // 3600

        if resolved == "hour":
            slots = list(range(end_hour - hours + 1, end_hour + 1))
            labels = [iso_utc(datetime.fromtimestamp(h * 3600, UTC)) for h in slots]
            start_ts, end_ts = slots[0] * 3600, (end_hour + 1) * 3600

            def slot_of(hour: int) -> int | None:
                return hour if slots[0] <= hour <= end_hour else None

        else:
            days = max(1, -(-hours // 24))
            today = local_day(now_ts, tz_offset_min)
            slots = list(range(today - days + 1, today + 1))
            labels = [_iso_local(d, tz_offset_min) for d in slots]
            start_ts = slots[0] * 86400 - tz_offset_min * 60
            end_ts = (today + 1) * 86400 - tz_offset_min * 60

            def slot_of(hour: int) -> int | None:
                day = local_day(hour * 3600, tz_offset_min)
                return day if slots[0] <= day <= today else None

        index = {s: i for i, s in enumerate(slots)}
        series: dict[str, list[list[int]]] = {}
        picked: list[Cell] = []
        for (hour, model, sidechain), cell in view.buckets.items():
            slot = slot_of(hour)
            if slot is None:
                continue
            key = (
                model
                if group == "model"
                else ("subagent" if sidechain else "main")
                if group == "sidechain"
                else "all"
            )
            cols = series.setdefault(key, [[0] * len(slots) for _ in range(5)])
            i = index[slot]
            for c in range(5):
                cols[c][i] += cell[c]
            picked.append(cell)

        panel.data = UsageTimeseriesData(
            scope="project",
            range=range_,
            bucket=resolved,
            group=group,
            tz_offset_min=tz_offset_min,
            start=iso_utc(datetime.fromtimestamp(start_ts, UTC)),
            end=iso_utc(datetime.fromtimestamp(end_ts, UTC)),
            buckets=labels,
            series=[
                TokenSeries(
                    key=key,
                    responses=cols[0],
                    input_tokens=cols[1],
                    output_tokens=cols[2],
                    cache_creation_input_tokens=cols[3],
                    cache_read_input_tokens=cols[4],
                )
                for key, cols in sorted(series.items())
            ],
            totals=totals(picked),
            project_dir_found=view.project_found,
            warming=_warming(view),
        )
        if not view.project_found:
            panel.empty(MSG_NO_PROJECT)
            panel.error = SourceError(
                code=SourceErrorCode.PROJECT_DIR_NOT_FOUND,
                message=SOURCE_MESSAGES[SourceErrorCode.PROJECT_DIR_NOT_FOUND],
            )
        elif view.state == "warming":
            panel.status = "warming"
        elif not picked:
            panel.empty(MSG_EMPTY_RANGE)
        return panel
