from __future__ import annotations

import pandas as pd
import pytest

from xau_engine.research.outcomes import backtest_candidates


def _frame(rows: list[tuple[float, float, float, float, int]]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01T00:00:00Z", periods=len(rows), freq="15min"),
            "open": [row[0] for row in rows],
            "high": [row[1] for row in rows],
            "low": [row[2] for row in rows],
            "close": [row[3] for row in rows],
            "spread": [row[4] for row in rows],
        }
    )


def _candidate(direction: str = "bullish") -> dict[str, object]:
    return {
        "direction": direction,
        "sweep_timestamp": pd.Timestamp("2024-01-01T00:15:00Z"),
        "causal_confirmation_timestamp": pd.Timestamp("2024-01-01T00:15:00Z"),
        "liquidity_level": 99.0 if direction == "bullish" else 101.0,
    }


def test_long_tp_and_r_calculation() -> None:
    frame = _frame([(100, 101, 99, 100, 0), (100, 101, 99.0, 100, 0), (100, 103, 99.5, 102, 0), (102, 102, 102, 102, 0)])
    results, summary = backtest_candidates(frame, [_candidate()], tp_multiple=2, max_hold_bars=2)

    assert results[0]["outcome"] == "win"
    assert results[0]["r_multiple"] == 2
    assert summary["wins"] == 1


def test_long_sl_and_short_tp_sl() -> None:
    long_frame = _frame([(100, 101, 99, 100, 0), (100, 101, 99, 100, 0), (100, 100, 98, 98.5, 0)])
    short_frame = _frame([(100, 101, 99, 100, 0), (100, 101, 99, 100, 0), (100, 98, 97, 98, 0)])

    long_results, _ = backtest_candidates(long_frame, [_candidate()], tp_multiple=1)
    short_results, _ = backtest_candidates(short_frame, [_candidate("bearish")], tp_multiple=1)

    assert long_results[0]["outcome"] == "loss"
    assert short_results[0]["outcome"] == "win"


def test_expiry_and_same_bar_is_conservative_loss() -> None:
    expiry = _frame([(100, 101, 99, 100, 0), (100, 100.5, 99.0, 100, 0), (100, 100.5, 99.5, 100, 0)])
    ambiguous = _frame([(100, 101, 99, 100, 0), (100, 101, 99, 100, 0), (100, 102, 98, 100, 0)])

    expired, _ = backtest_candidates(expiry, [_candidate()], tp_multiple=1, max_hold_bars=2)
    same_bar, _ = backtest_candidates(ambiguous, [_candidate()], tp_multiple=1)

    assert expired[0]["outcome"] == "expired"
    assert same_bar[0]["outcome"] == "loss"
    assert same_bar[0]["same_bar_ambiguity"] is True


def test_spread_slippage_mfe_mae_and_drawdown() -> None:
    frame = _frame([(100, 101, 99, 100, 10), (100, 101, 99, 100, 10), (100, 102, 100.0, 101, 10)])
    results, summary = backtest_candidates(frame, [_candidate()], tp_multiple=1, tick_size=0.01, slippage_ticks=10)

    assert results[0]["entry_price"] == pytest.approx(100.2)
    assert results[0]["mfe_r"] > 0
    assert results[0]["mae_r"] > 0
    assert summary["max_drawdown_r"] == 0


def test_entry_is_after_confirmation_and_results_are_chronological() -> None:
    frame = _frame([(100, 101, 99, 100, 0)] * 4)
    candidates = [_candidate()]
    results, _ = backtest_candidates(frame, candidates, tp_multiple=1)

    assert results[0]["entry_timestamp"] > candidates[0]["causal_confirmation_timestamp"]
    assert results[0]["entry_timestamp"] <= results[0]["exit_timestamp"]