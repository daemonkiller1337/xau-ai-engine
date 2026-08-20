from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from xau_engine.config import SessionConfig, SessionWindow
from xau_engine.features.sessions import resolve_session


def window(**overrides: object) -> SessionWindow:
    values: dict[str, object] = {
        "name": "test",
        "start": "09:00",
        "end": "10:00",
        "timezone": "UTC",
        "enabled": True,
    }
    values.update(overrides)
    return SessionWindow.model_validate(values)


def test_timestamp_inside_window_returns_utc_boundaries() -> None:
    result = resolve_session(datetime(2025, 1, 2, 9, 30, tzinfo=UTC), [window()])

    assert result.matched is True
    assert result.session_name == "test"
    assert result.session_start == datetime(2025, 1, 2, 9, tzinfo=UTC)
    assert result.session_end == datetime(2025, 1, 2, 10, tzinfo=UTC)


def test_timestamp_outside_window_does_not_match() -> None:
    result = resolve_session(datetime(2025, 1, 2, 10, 1, tzinfo=UTC), [window()])

    assert result == resolve_session(datetime(2025, 1, 2, 10, 1, tzinfo=UTC), [])
    assert result.matched is False
    assert result.session_name is None


def test_start_is_inclusive_and_end_is_exclusive() -> None:
    start = resolve_session(datetime(2025, 1, 2, 9, tzinfo=UTC), [window()])
    end = resolve_session(datetime(2025, 1, 2, 10, tzinfo=UTC), [window()])

    assert start.matched is True
    assert end.matched is False


def test_window_crossing_midnight_uses_previous_local_date_after_midnight() -> None:
    overnight = window(name="overnight", start="22:00", end="02:00")
    result = resolve_session(datetime(2025, 1, 3, 1, 30, tzinfo=UTC), [overnight])

    assert result.matched is True
    assert result.session_start == datetime(2025, 1, 2, 22, tzinfo=UTC)
    assert result.session_end == datetime(2025, 1, 3, 2, tzinfo=UTC)


def test_timezone_conversion_and_utc_normalization() -> None:
    new_york = window(name="new-york", start="09:30", end="10:30", timezone="America/New_York")
    timestamp = datetime(2025, 1, 2, 14, 45, tzinfo=UTC)
    result = resolve_session(timestamp, [new_york])

    assert result.matched is True
    assert result.session_start == datetime(2025, 1, 2, 14, 30, tzinfo=UTC)
    assert result.session_end == datetime(2025, 1, 2, 15, 30, tzinfo=UTC)
    assert result.session_start.tzinfo == UTC


def test_dst_changes_utc_boundaries_without_changing_local_window() -> None:
    new_york = window(name="new-york", start="09:30", end="10:30", timezone="America/New_York")
    winter = resolve_session(datetime(2025, 1, 2, 14, 45, tzinfo=UTC), [new_york])
    summer = resolve_session(datetime(2025, 7, 2, 13, 45, tzinfo=UTC), [new_york])

    assert winter.session_start == datetime(2025, 1, 2, 14, 30, tzinfo=UTC)
    assert summer.session_start == datetime(2025, 7, 2, 13, 30, tzinfo=UTC)
    assert winter.session_start < winter.session_end
    assert summer.session_start < summer.session_end


def test_disabled_window_is_ignored() -> None:
    result = resolve_session(
        datetime(2025, 1, 2, 9, 30, tzinfo=UTC), [window(enabled=False)]
    )

    assert result.matched is False


def test_naive_timestamp_is_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        resolve_session(datetime(2025, 1, 2, 9, 30), [window()])  # noqa: DTZ001


@pytest.mark.parametrize(
    "values",
    [
        {"name": "", "start": "09:00", "end": "10:00", "timezone": "UTC"},
        {"name": "bad", "start": "09:00", "end": "09:00", "timezone": "UTC"},
        {"name": "bad", "start": "09:00", "end": "10:00", "timezone": "Mars/Olympus"},
        {"name": "bad", "start": "not-a-time", "end": "10:00", "timezone": "UTC"},
    ],
)
def test_invalid_window_configuration_is_rejected(values: dict[str, str]) -> None:
    with pytest.raises(ValidationError):
        SessionWindow.model_validate(values)


def test_session_names_must_be_unique() -> None:
    with pytest.raises(ValidationError, match="unique"):
        SessionConfig(
            windows=[window(name="same"), window(name="same", start="11:00", end="12:00")]
        )


def test_resolution_is_chronological_and_first_configured_match_wins() -> None:
    first = window(name="first", start="09:00", end="11:00")
    second = window(name="second", start="10:00", end="12:00")
    result = resolve_session(datetime(2025, 1, 2, 10, 30, tzinfo=UTC), [first, second])

    assert result.session_name == "first"
    assert result.session_start < result.session_end
