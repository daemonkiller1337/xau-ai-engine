from __future__ import annotations

from collections.abc import Iterable
from statistics import median

import pandas as pd


def _prepare_frame(frame: pd.DataFrame) -> pd.DataFrame:
    required = ["timestamp", "open", "high", "low", "close"]
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"frame must include columns: {', '.join(missing)}")
    prepared = frame.copy()
    prepared["timestamp"] = pd.to_datetime(prepared["timestamp"], errors="coerce", utc=True)
    for column in ["open", "high", "low", "close"]:
        prepared[column] = pd.to_numeric(prepared[column], errors="coerce")
    if "spread" in prepared.columns:
        prepared["spread"] = pd.to_numeric(prepared["spread"], errors="coerce").fillna(0)
    return prepared.dropna(subset=required).sort_values("timestamp").reset_index(drop=True)


def _max_drawdown(values: list[float]) -> float:
    peak = 0.0
    drawdown = 0.0
    running = 0.0
    for value in values:
        running += value
        peak = max(peak, running)
        drawdown = max(drawdown, peak - running)
    return drawdown


def _max_consecutive(values: list[bool], target: bool) -> int:
    best = current = 0
    for value in values:
        current = current + 1 if value is target else 0
        best = max(best, current)
    return best


def _summary(results: list[dict[str, object]], tp_multiple: float) -> dict[str, object]:
    returns = [float(result["r_multiple"]) for result in results]
    wins = [result["outcome"] == "win" for result in results]
    gross_profit = sum(value for value in returns if value > 0)
    gross_loss = abs(sum(value for value in returns if value < 0))
    return {
        "tp_multiple": tp_multiple,
        "total_trades": len(results),
        "wins": sum(result["outcome"] == "win" for result in results),
        "losses": sum(result["outcome"] == "loss" for result in results),
        "expired": sum(result["outcome"] == "expired" for result in results),
        "win_rate": sum(wins) / len(results) if results else 0.0,
        "average_r": sum(returns) / len(returns) if returns else 0.0,
        "median_r": median(returns) if returns else 0.0,
        "expectancy_r": sum(returns) / len(returns) if returns else 0.0,
        "profit_factor": gross_profit / gross_loss if gross_loss else None,
        "total_r": sum(returns),
        "max_drawdown_r": _max_drawdown(returns),
        "max_consecutive_wins": _max_consecutive(wins, True),
        "max_consecutive_losses": _max_consecutive(wins, False),
        "average_mfe_r": sum(float(result["mfe_r"]) for result in results) / len(results) if results else 0.0,
        "median_mfe_r": median(float(result["mfe_r"]) for result in results) if results else 0.0,
        "average_mae_r": sum(float(result["mae_r"]) for result in results) / len(results) if results else 0.0,
        "median_mae_r": median(float(result["mae_r"]) for result in results) if results else 0.0,
        "same_bar_ambiguity_count": sum(bool(result["same_bar_ambiguity"]) for result in results),
    }


def backtest_candidates(
    frame: pd.DataFrame,
    candidates: Iterable[dict[str, object]],
    *,
    tp_multiple: float,
    tick_size: float = 0.01,
    slippage_ticks: float = 0.0,
    max_hold_bars: int = 20,
    spread_column: str = "spread",
    spread_in_ticks: bool = True,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Evaluate existing causal candidates with deterministic OHLC outcomes.

    Entry is the first bar after candidate confirmation. Spread and slippage are
    adverse entry costs; spread values are ticks by default. When SL and TP share
    a candle, the conservative SL outcome is selected.
    """
    if tp_multiple <= 0 or tick_size <= 0 or slippage_ticks < 0 or max_hold_bars < 1:
        raise ValueError("tp_multiple and tick_size must be > 0; costs and hold must be valid")
    prepared = _prepare_frame(frame)
    if spread_column not in prepared.columns:
        if spread_column == "spread":
            prepared[spread_column] = 0.0
        else:
            raise ValueError(f"frame must include '{spread_column}'")
    timestamp_indexes = {pd.Timestamp(value): index for index, value in enumerate(prepared["timestamp"])}
    results: list[dict[str, object]] = []
    for candidate in sorted(candidates, key=lambda event: pd.Timestamp(event["causal_confirmation_timestamp"])):
        confirmation = pd.Timestamp(candidate["causal_confirmation_timestamp"])
        entry_index = next((index for index, value in enumerate(prepared["timestamp"]) if value > confirmation), None)
        sweep_index = timestamp_indexes.get(pd.Timestamp(candidate["sweep_timestamp"]))
        if entry_index is None or sweep_index is None:
            continue
        direction = str(candidate["direction"])
        bullish = direction == "bullish"
        spread_value = float(prepared.iloc[entry_index][spread_column])
        spread_price = spread_value * tick_size if spread_in_ticks else spread_value
        slippage_price = slippage_ticks * tick_size
        raw_entry = float(prepared.iloc[entry_index]["open"])
        entry = raw_entry + spread_price + slippage_price if bullish else raw_entry - spread_price - slippage_price
        stop = float(prepared.iloc[sweep_index]["low" if bullish else "high"])
        risk = entry - stop if bullish else stop - entry
        if risk <= 0:
            continue
        target = entry + tp_multiple * risk if bullish else entry - tp_multiple * risk
        final_index = min(len(prepared) - 1, entry_index + max_hold_bars - 1)
        outcome = "expired"
        exit_index = final_index
        exit_price = float(prepared.iloc[final_index]["close"])
        same_bar_ambiguity = False
        mfe_price = 0.0
        mae_price = 0.0
        for index in range(entry_index, final_index + 1):
            high = float(prepared.iloc[index]["high"])
            low = float(prepared.iloc[index]["low"])
            if bullish:
                mfe_price = max(mfe_price, high - entry)
                mae_price = max(mae_price, entry - low)
                hit_stop, hit_target = low <= stop, high >= target
            else:
                mfe_price = max(mfe_price, entry - low)
                mae_price = max(mae_price, high - entry)
                hit_stop, hit_target = high >= stop, low <= target
            if hit_stop and hit_target:
                outcome, exit_index, exit_price, same_bar_ambiguity = "loss", index, stop, True
                break
            if hit_stop:
                outcome, exit_index, exit_price = "loss", index, stop
                break
            if hit_target:
                outcome, exit_index, exit_price = "win", index, target
                break
        r_multiple = (exit_price - entry) / risk if bullish else (entry - exit_price) / risk
        results.append(
            {
                "direction": direction,
                "candidate_confirmation_timestamp": confirmation,
                "entry_timestamp": pd.Timestamp(prepared.iloc[entry_index]["timestamp"]),
                "exit_timestamp": pd.Timestamp(prepared.iloc[exit_index]["timestamp"]),
                "entry_price": entry,
                "stop_price": stop,
                "target_price": target,
                "risk_price": risk,
                "outcome": outcome,
                "r_multiple": r_multiple,
                "mfe_r": mfe_price / risk,
                "mae_r": mae_price / risk,
                "same_bar_ambiguity": same_bar_ambiguity,
            }
        )
    return results, _summary(results, tp_multiple)


__all__ = ["backtest_candidates"]