from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from xau_engine.config.models import SessionWindow


@dataclass(frozen=True)
class SessionMatch:
    """The causal session assignment for one UTC candle timestamp."""

    matched: bool
    session_name: str | None = None
    session_start: datetime | None = None
    session_end: datetime | None = None


def _parse_local_time(value: str) -> time:
    try:
        parsed = time.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"invalid session time: {value!r}") from error
    if parsed.tzinfo is not None:
        raise ValueError("session times must not include a timezone")
    return parsed


def _utc_timestamp(timestamp: datetime) -> datetime:
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("session resolution requires a timezone-aware timestamp")
    return timestamp.astimezone(UTC)


def _localize(local_value: datetime, timezone_name: str) -> datetime:
    try:
        zone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as error:
        raise ValueError(f"unknown session timezone: {timezone_name!r}") from error

    # fold=0 is a deterministic choice for an ambiguous fall-back boundary.
    candidate = local_value.replace(tzinfo=zone, fold=0)
    round_trip = candidate.astimezone(UTC).astimezone(zone).replace(tzinfo=None)
    if round_trip != local_value:
        raise ValueError(f"session boundary is nonexistent in timezone {timezone_name!r}: {local_value}")
    return candidate.astimezone(UTC)


def _window_bounds(timestamp: datetime, window: SessionWindow) -> tuple[datetime, datetime]:
    local_timestamp = timestamp.astimezone(ZoneInfo(window.timezone))
    start_time = _parse_local_time(window.start)
    end_time = _parse_local_time(window.end)
    crosses_midnight = end_time < start_time
    start_date = local_timestamp.date()
    if crosses_midnight and local_timestamp.timetz().replace(tzinfo=None) < start_time:
        start_date -= timedelta(days=1)

    local_start = datetime.combine(start_date, start_time)
    end_date = start_date + timedelta(days=1 if crosses_midnight else 0)
    local_end = datetime.combine(end_date, end_time)
    return _localize(local_start, window.timezone), _localize(local_end, window.timezone)


def resolve_session(timestamp: datetime, windows: list[SessionWindow] | tuple[SessionWindow, ...]) -> SessionMatch:
    """Resolve a UTC-aware candle timestamp against enabled configured windows.

    Windows are evaluated in configuration order. Their end boundary is exclusive,
    and the first matching window wins when configured windows overlap.
    """
    utc_timestamp = _utc_timestamp(timestamp)
    for window in windows:
        if not window.enabled:
            continue
        session_start, session_end = _window_bounds(utc_timestamp, window)
        if session_start <= utc_timestamp < session_end:
            return SessionMatch(True, window.name, session_start, session_end)
    return SessionMatch(False)