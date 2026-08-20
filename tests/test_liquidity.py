from __future__ import annotations

import pandas as pd
import pytest

from xau_engine.features.liquidity import (
    detect_liquidity_pools,
    detect_liquidity_sweeps,
)


def _swing(event_type: str, price: float, minute: int, confirmation_minute: int | None = None) -> dict[str, object]:
    timestamp = pd.Timestamp(f"2024-01-01T00:{minute:02d}:00Z")
    confirmation = pd.Timestamp(f"2024-01-01T00:{(confirmation_minute or minute):02d}:00Z")
    return {
        "timestamp": timestamp,
        "event_type": event_type,
        "price": price,
        "confirmation_timestamp": confirmation,
        "causal": True,
    }


def _frame(high: list[float], low: list[float], close: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01T00:00:00Z", periods=len(high), freq="min"),
            "high": high,
            "low": low,
            "close": close,
        }
    )


def test_equal_highs_and_lows_use_tick_tolerance_and_suppress_duplicates() -> None:
    events = [
        _swing("swing_high", 100.00, 1),
        _swing("swing_high", 100.01, 3),
        _swing("swing_high", 100.005, 5),
        _swing("swing_low", 99.00, 2),
        _swing("swing_low", 98.99, 4),
    ]

    pools = detect_liquidity_pools(events, timeframe="M5", tick_size=0.01, equal_level_tolerance_ticks=1)

    assert {pool["liquidity_type"] for pool in pools} == {"equal_high", "equal_low"}
    high_pool = next(pool for pool in pools if pool["liquidity_type"] == "equal_high")
    assert high_pool["event_type"] == "liquidity_equal_high"
    assert high_pool["level_price"] == 100.0


def test_levels_outside_tick_tolerance_remain_prior_pools() -> None:
    events = [_swing("swing_high", 100.00, 1), _swing("swing_high", 100.02, 3)]

    pools = detect_liquidity_pools(events, timeframe="M5", tick_size=0.01, equal_level_tolerance_ticks=1)

    assert [pool["liquidity_type"] for pool in pools] == ["prior_swing_high", "prior_swing_high"]


def test_bullish_sweep_requires_penetration_and_reclaim() -> None:
    pool = detect_liquidity_pools(
        [_swing("swing_low", 100.00, 1)], timeframe="M5", tick_size=0.01, equal_level_tolerance_ticks=1
    )
    frame = _frame([101, 101, 101, 101], [99.9, 99.0, 99.5, 100.2], [100.5, 99.5, 100.1, 100.2])

    sweeps = detect_liquidity_sweeps(
        frame,
        pool,
        timeframe="M5",
        tick_size=0.01,
        sweep_penetration_ticks=50,
        sweep_k_bars=2,
    )

    assert len(sweeps) == 1
    assert sweeps[0]["event_type"] == "liquidity_sweep_bullish"
    assert sweeps[0]["confirmation_timestamp"] == pd.Timestamp("2024-01-01T00:03:00Z")
    assert sweeps[0]["causal"] is True


def test_bearish_sweep_requires_penetration_and_reclaim() -> None:
    pool = detect_liquidity_pools(
        [_swing("swing_high", 100.00, 1)], timeframe="M15", tick_size=0.01, equal_level_tolerance_ticks=1
    )
    frame = _frame([100.1, 101.0, 100.5, 99.8], [99, 99, 99, 99], [99.5, 100.5, 99.9, 99.8])

    sweeps = detect_liquidity_sweeps(
        frame, pool, timeframe="M15", tick_size=0.01, sweep_penetration_ticks=50, sweep_k_bars=2
    )

    assert len(sweeps) == 1
    assert sweeps[0]["event_type"] == "liquidity_sweep_bearish"
    assert sweeps[0]["confirmation_timestamp"] == pd.Timestamp("2024-01-01T00:03:00Z")


def test_penetration_threshold_and_reclaim_requirement_prevent_false_sweeps() -> None:
    pool = detect_liquidity_pools(
        [_swing("swing_low", 100.00, 1)], timeframe="M5", tick_size=0.01, equal_level_tolerance_ticks=1
    )
    no_penetration = _frame([101, 101, 101], [99.9, 99.6, 100.2], [100.5, 99.8, 100.2])
    no_reclaim = _frame([101, 101, 101], [99.9, 99.0, 99.5], [100.5, 99.5, 99.8])

    assert not detect_liquidity_sweeps(
        no_penetration, pool, timeframe="M5", tick_size=0.01, sweep_penetration_ticks=50, sweep_k_bars=2
    )
    assert not detect_liquidity_sweeps(
        no_reclaim, pool, timeframe="M5", tick_size=0.01, sweep_penetration_ticks=50, sweep_k_bars=1
    )


def test_sweep_k_bars_is_causal_and_limits_reclaim_window() -> None:
    pool = detect_liquidity_pools(
        [_swing("swing_low", 100.00, 1)], timeframe="M5", tick_size=0.01, equal_level_tolerance_ticks=1
    )
    frame = _frame([101] * 5, [99.9, 99.0, 99.5, 100.1, 100.2], [100.5, 99.5, 99.7, 99.8, 100.2])

    assert not detect_liquidity_sweeps(
        frame, pool, timeframe="M5", tick_size=0.01, sweep_penetration_ticks=50, sweep_k_bars=1
    )
    sweeps = detect_liquidity_sweeps(
        frame, pool, timeframe="M5", tick_size=0.01, sweep_penetration_ticks=50, sweep_k_bars=3
    )
    assert sweeps[0]["timestamp"] == pd.Timestamp("2024-01-01T00:04:00Z")


def test_non_causal_swing_events_are_rejected() -> None:
    with pytest.raises(ValueError, match="causal"):
        detect_liquidity_pools(
            [{**_swing("swing_high", 100, 1), "causal": False}],
            timeframe="H1",
            tick_size=0.01,
        )