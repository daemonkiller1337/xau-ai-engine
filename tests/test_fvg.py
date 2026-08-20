from __future__ import annotations

import pandas as pd
import pytest

from xau_engine.features.fvg import detect_first_setup_candidates, detect_fvg


def _frame(high: list[float], low: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01T00:00:00Z", periods=len(high), freq="min"),
            "high": high,
            "low": low,
        }
    )


def test_detects_bullish_fvg_at_third_candle_close() -> None:
    events = detect_fvg(_frame([100, 105, 104], [99, 101, 102]), timeframe="M5", tick_size=0.01, minimum_gap_ticks=100)

    assert len(events) == 1
    assert events[0]["direction"] == "bullish"
    assert events[0]["lower_price"] == 100.0
    assert events[0]["upper_price"] == 102.0
    assert events[0]["gap_size_ticks"] == pytest.approx(200)
    assert events[0]["timestamp"] == pd.Timestamp("2024-01-01T00:02:00Z")
    assert events[0]["source_candle_timestamp"] == events[0]["confirmation_timestamp"]
    assert events[0]["causal"] is True


def test_detects_bearish_fvg_at_third_candle_close() -> None:
    events = detect_fvg(_frame([101, 102, 99], [100, 98, 97]), timeframe="M15", tick_size=0.01, minimum_gap_ticks=100)

    assert len(events) == 1
    assert events[0]["direction"] == "bearish"
    assert events[0]["lower_price"] == 99.0
    assert events[0]["upper_price"] == 100.0
    assert events[0]["gap_size_ticks"] == pytest.approx(100)


def test_minimum_gap_threshold_and_no_fvg_case() -> None:
    frame = _frame([100, 105, 101], [99, 101, 100.5])

    assert detect_fvg(frame, timeframe="M5", tick_size=0.01, minimum_gap_ticks=50)
    assert not detect_fvg(frame, timeframe="M5", tick_size=0.01, minimum_gap_ticks=51)
    assert not detect_fvg(_frame([100, 101, 101], [99, 99.5, 99.5]), timeframe="M5")


def test_future_bar_mutation_does_not_change_prior_fvg() -> None:
    frame = _frame([100, 105, 104, 104], [99, 101, 102, 103])
    changed = frame.copy()
    changed.loc[3, ["high", "low"]] = [1000, 1]

    first = detect_fvg(frame, timeframe="M5", minimum_gap_ticks=1)
    second = detect_fvg(changed, timeframe="M5", minimum_gap_ticks=1)
    assert first[0] == second[0]


def test_candidate_requires_same_direction_chain_and_is_causal() -> None:
    frame = _frame([100, 105, 104, 106, 107], [99, 101, 102, 103, 105])
    sweeps = [
        {
            "event_type": "liquidity_sweep_bullish",
            "confirmation_timestamp": pd.Timestamp("2024-01-01T00:00:00Z"),
            "level_price": 99.5,
            "causal": True,
        }
    ]
    displacements = [
        {
            "event_type": "displacement_bullish",
            "timestamp": pd.Timestamp("2024-01-01T00:01:00Z"),
            "causal": True,
        }
    ]

    candidates = detect_first_setup_candidates(
        frame,
        sweeps,
        displacements,
        timeframe="M5",
        next_n_bars=2,
        tick_size=0.01,
        minimum_gap_ticks=100,
    )

    assert len(candidates) == 1
    assert candidates[0]["direction"] == "bullish"
    assert candidates[0]["sweep_timestamp"] == pd.Timestamp("2024-01-01T00:00:00Z")
    assert candidates[0]["displacement_timestamp"] == pd.Timestamp("2024-01-01T00:01:00Z")
    assert candidates[0]["fvg_timestamp"] == pd.Timestamp("2024-01-01T00:02:00Z")
    assert candidates[0]["causal_confirmation_timestamp"] == candidates[0]["fvg_timestamp"]


def test_candidate_requires_displacement_within_n_bars() -> None:
    frame = _frame([100, 101, 101, 105, 104], [99, 99, 99, 103, 103])
    sweeps = [{"event_type": "liquidity_sweep_bullish", "confirmation_timestamp": frame.loc[0, "timestamp"], "level_price": 99, "causal": True}]
    displacements = [{"event_type": "displacement_bullish", "timestamp": frame.loc[3, "timestamp"], "causal": True}]

    assert not detect_first_setup_candidates(frame, sweeps, displacements, timeframe="M5", next_n_bars=2)


def test_non_causal_sweep_is_rejected() -> None:
    frame = _frame([100, 105, 104], [99, 101, 102])
    sweep = [{"event_type": "liquidity_sweep_bullish", "confirmation_timestamp": frame.loc[0, "timestamp"], "level_price": 99, "causal": False}]
    with pytest.raises(ValueError, match="causal"):
        detect_first_setup_candidates(frame, sweep, [], timeframe="M5")