from __future__ import annotations

import pandas as pd
import pytest

from xau_engine.features.displacement import detect_displacement


def _frame(opens: list[float], highs: list[float], lows: list[float], closes: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01T00:00:00Z", periods=len(opens), freq="min"),
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "tick_volume": [100] * len(opens),
        }
    )


def test_detects_bullish_and_bearish_displacement() -> None:
    frame = _frame(
        [100, 100, 100, 100, 100, 105],
        [101, 101, 101, 101, 101, 110],
        [99, 99, 99, 99, 99, 99],
        [100, 100, 100, 100, 100, 109],
    )
    frame.loc[5, "open"] = 109
    frame.loc[5, "close"] = 101

    bearish = detect_displacement(frame, timeframe="M5", atr_period=3, min_body_atr_multiple=1.5, min_range_atr_multiple=1.5)
    assert len(bearish) == 1
    assert bearish[0]["event_type"] == "displacement_bearish"
    assert bearish[0]["causal"] is True
    assert bearish[0]["confirmation_timestamp"] == bearish[0]["timestamp"]

    bullish_frame = frame.copy()
    bullish_frame.loc[5, "open"] = 101
    bullish_frame.loc[5, "close"] = 109
    bullish = detect_displacement(bullish_frame, timeframe="M5", atr_period=3, min_body_atr_multiple=1.5, min_range_atr_multiple=1.5)
    assert bullish[0]["event_type"] == "displacement_bullish"


def test_body_and_range_thresholds_are_independent() -> None:
    frame = _frame([100, 100, 100, 100], [101, 101, 101, 103], [99, 99, 99, 99], [100, 100, 100, 102.9])

    assert detect_displacement(frame, timeframe="M5", atr_period=3, min_body_atr_multiple=0.9, min_range_atr_multiple=0)
    assert not detect_displacement(frame, timeframe="M5", atr_period=3, min_body_atr_multiple=0, min_range_atr_multiple=3)


def test_atr_is_causal_and_warmup_is_explicit() -> None:
    frame = _frame([100, 100, 100, 100], [102, 103, 104, 105], [98, 98, 98, 98], [100, 100, 100, 100])
    events = detect_displacement(frame, timeframe="M15", atr_period=3, min_body_atr_multiple=0, min_range_atr_multiple=0)

    assert all(event["timestamp"] >= pd.Timestamp("2024-01-01T00:02:00Z") for event in events)
    assert events == []


def test_atr_value_matches_true_range_rolling_mean() -> None:
    frame = _frame([100, 101, 102], [102, 104, 105], [99, 100, 101], [101, 102, 104])
    events = detect_displacement(frame, timeframe="H1", atr_period=2, min_body_atr_multiple=0, min_range_atr_multiple=0)

    assert events[0]["ATR"] == pytest.approx(3.5)


def test_close_location_filter_and_volume_confirmation() -> None:
    frame = _frame([100, 100, 100, 100], [101, 101, 101, 105], [99, 99, 99, 99], [100, 100, 100, 101])
    frame["tick_volume"] = [100, 100, 100, 50]

    assert not detect_displacement(
        frame, timeframe="M5", atr_period=3, min_body_atr_multiple=0, min_range_atr_multiple=0,
        close_location_requirement=0.9,
    )
    assert not detect_displacement(
        frame, timeframe="M5", atr_period=3, min_body_atr_multiple=0, min_range_atr_multiple=0,
        volume_confirmation=True,
    )


def test_tick_thresholds_are_absolute_not_percentage_based() -> None:
    frame = _frame([100, 100, 100, 100], [101, 101, 101, 102], [99, 99, 99, 99], [100, 100, 100, 101.5])

    one_tick = detect_displacement(
        frame, timeframe="M5", atr_period=3, min_body_atr_multiple=0, min_range_atr_multiple=0,
        tick_size=0.01, min_body_ticks=100,
    )
    two_hundred_ticks = detect_displacement(
        frame, timeframe="M5", atr_period=3, min_body_atr_multiple=0, min_range_atr_multiple=0,
        tick_size=0.01, min_body_ticks=200,
    )
    assert one_tick and not two_hundred_ticks


def test_future_bar_changes_do_not_change_prior_event() -> None:
    frame = _frame([100, 100, 100, 100, 100], [101, 101, 101, 105, 101], [99, 99, 99, 99, 99], [100, 100, 100, 104, 100])
    changed = frame.copy()
    changed.loc[4, ["high", "low", "close"]] = [1000, 1, 500]
    params = {"timeframe": "M5", "atr_period": 3, "min_body_atr_multiple": 1, "min_range_atr_multiple": 1}

    first = detect_displacement(frame, **params)
    second = detect_displacement(changed, **params)
    assert first[0] == second[0]


def test_invalid_parameters_are_rejected() -> None:
    frame = _frame([100], [101], [99], [100])
    with pytest.raises(ValueError, match="atr_period"):
        detect_displacement(frame, timeframe="M5", atr_period=0)