from __future__ import annotations

import pandas as pd
import pytest

from xau_engine.features.market_structure import detect_swing_points


@pytest.fixture
def simple_high_frame() -> pd.DataFrame:
    timestamps = pd.date_range("2024-01-01T00:00:00Z", periods=9, freq="1min")
    prices = [99, 98, 97, 96, 100, 95, 94, 93, 92]
    return pd.DataFrame({"timestamp": timestamps, "high": prices, "low": [p - 1 for p in prices]})


@pytest.fixture
def simple_low_frame() -> pd.DataFrame:
    timestamps = pd.date_range("2024-01-01T00:00:00Z", periods=9, freq="1min")
    prices = [101, 102, 100, 97, 96, 99, 104, 103, 105]
    return pd.DataFrame({"timestamp": timestamps, "high": [p + 2 for p in prices], "low": prices})


def test_detects_normal_swing_high(simple_high_frame: pd.DataFrame) -> None:
    events = detect_swing_points(simple_high_frame, timeframe="M5", swing_left_bars=2, swing_right_bars=2)

    assert len(events) == 1
    assert events[0]["event_type"] == "swing_high"
    assert events[0]["price"] == 100.0
    assert events[0]["causal"] is True
    assert events[0]["timestamp"] == pd.Timestamp("2024-01-01T00:04:00Z")
    assert events[0]["confirmation_timestamp"] == pd.Timestamp("2024-01-01T00:06:00Z")


def test_detects_normal_swing_low(simple_low_frame: pd.DataFrame) -> None:
    events = detect_swing_points(simple_low_frame, timeframe="M15", swing_left_bars=2, swing_right_bars=2)

    assert len(events) == 1
    assert events[0]["event_type"] == "swing_low"
    assert events[0]["price"] == 96.0
    assert events[0]["causal"] is True
    assert events[0]["timestamp"] == pd.Timestamp("2024-01-01T00:04:00Z")
    assert events[0]["confirmation_timestamp"] == pd.Timestamp("2024-01-01T00:06:00Z")


def test_causal_confirmation_timing_uses_information_available_at_confirmation() -> None:
    timestamps = pd.date_range("2024-01-01T00:00:00Z", periods=8, freq="1min")
    highs = [100, 101, 102, 103, 105, 104, 103, 102]
    lows = [99, 100, 101, 102, 104, 103, 102, 101]
    frame = pd.DataFrame({"timestamp": timestamps, "high": highs, "low": lows})

    events = detect_swing_points(frame, timeframe="M5", swing_left_bars=2, swing_right_bars=2, confirmation_mode="CAUSAL")

    assert len(events) == 1
    assert events[0]["timestamp"] == pd.Timestamp("2024-01-01T00:04:00Z")
    assert events[0]["confirmation_timestamp"] == pd.Timestamp("2024-01-01T00:06:00Z")
    assert events[0]["causal"] is True


def test_perfect_mode_requires_explicit_allow_lookahead() -> None:
    timestamps = pd.date_range("2024-01-01T00:00:00Z", periods=9, freq="1min")
    highs = [100, 101, 102, 103, 105, 104, 103, 102, 101]
    frame = pd.DataFrame({"timestamp": timestamps, "high": highs, "low": [v - 2 for v in highs]})

    with pytest.raises(ValueError, match="allow_lookahead"):
        detect_swing_points(frame, timeframe="H1", swing_left_bars=2, swing_right_bars=2, confirmation_mode="PERFECT")

    events = detect_swing_points(
        frame,
        timeframe="H1",
        swing_left_bars=2,
        swing_right_bars=2,
        confirmation_mode="PERFECT",
        allow_lookahead=True,
    )
    assert events[0]["causal"] is False
    assert events[0]["source"] == "PERFECT_LOOKAHEAD"


def test_changing_swing_parameters_changes_detection_deterministically() -> None:
    timestamps = pd.date_range("2024-01-01T00:00:00Z", periods=15, freq="1min")
    highs = [100, 101, 97, 98, 99, 105, 103, 104, 106, 101, 100, 99, 98, 97, 96]
    frame = pd.DataFrame({"timestamp": timestamps, "high": highs, "low": [v - 1 for v in highs]})

    narrow = detect_swing_points(frame, timeframe="M5", swing_left_bars=2, swing_right_bars=2)
    wide = detect_swing_points(frame, timeframe="M5", swing_left_bars=3, swing_right_bars=3)

    assert narrow != wide
    assert [event["price"] for event in narrow] == [96.0, 105.0, 106.0]
    assert [event["price"] for event in wide] == [106.0]


def test_equal_highs_and_lows_do_not_create_duplicate_swing_events() -> None:
    timestamps = pd.date_range("2024-01-01T00:00:00Z", periods=10, freq="1min")
    highs = [99, 100, 102, 102, 102, 101, 100, 99, 98, 97]
    lows = [98, 99, 101, 101, 101, 100, 99, 98, 97, 96]
    frame = pd.DataFrame({"timestamp": timestamps, "high": highs, "low": lows})

    events = detect_swing_points(frame, timeframe="M5", swing_left_bars=2, swing_right_bars=2)

    assert [event["event_type"] for event in events] == ["swing_high"]
    assert [event["price"] for event in events] == [102.0]


def test_events_are_chronologically_ordered() -> None:
    timestamps = pd.date_range("2024-01-01T00:00:00Z", periods=12, freq="1min")
    highs = [100, 101, 99, 98, 97, 105, 96, 95, 98, 104, 103, 102]
    lows = [95, 96, 94, 93, 92, 100, 91, 90, 93, 99, 98, 97]
    frame = pd.DataFrame({"timestamp": timestamps, "high": highs, "low": lows})

    events = detect_swing_points(frame, timeframe="H1", swing_left_bars=2, swing_right_bars=2)

    timestamps_seen = [event["timestamp"] for event in events]
    assert timestamps_seen == sorted(timestamps_seen)
