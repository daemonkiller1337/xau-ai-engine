from __future__ import annotations

from bisect import bisect_right
from collections.abc import Iterable

import pandas as pd


def _prepare_frame(frame: pd.DataFrame) -> pd.DataFrame:
    required = ["timestamp", "high", "low"]
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"frame must include columns: {', '.join(missing)}")
    prepared = frame.copy()
    prepared["timestamp"] = pd.to_datetime(prepared["timestamp"], errors="coerce", utc=True)
    for column in ["high", "low"]:
        prepared[column] = pd.to_numeric(prepared[column], errors="coerce")
    return prepared.dropna(subset=required).sort_values("timestamp").reset_index(drop=True)


def _validate_fvg_parameters(tick_size: float, minimum_gap_ticks: float) -> None:
    if tick_size <= 0:
        raise ValueError("tick_size must be > 0")
    if minimum_gap_ticks < 0:
        raise ValueError("minimum_gap_ticks must be >= 0")


def detect_fvg(
    frame: pd.DataFrame,
    *,
    timeframe: str,
    tick_size: float = 0.01,
    minimum_gap_ticks: float = 1,
) -> list[dict[str, object]]:
    """Detect causal three-candle fair value gaps.

    Candle ``i`` is the confirmation candle. Only candles through ``i`` are used,
    so both the gap and confirmation timestamp are known at candle ``i`` close.
    """
    _validate_fvg_parameters(tick_size, minimum_gap_ticks)
    prepared = _prepare_frame(frame)
    events: list[dict[str, object]] = []
    minimum_gap = minimum_gap_ticks * tick_size
    for index in range(2, len(prepared)):
        first_high = float(prepared.iloc[index - 2]["high"])
        first_low = float(prepared.iloc[index - 2]["low"])
        current_high = float(prepared.iloc[index]["high"])
        current_low = float(prepared.iloc[index]["low"])
        bullish_gap = current_low - first_high
        bearish_gap = first_low - current_high
        if bullish_gap >= minimum_gap and bullish_gap > 0:
            lower_price, upper_price, direction = first_high, current_low, "bullish"
        elif bearish_gap >= minimum_gap and bearish_gap > 0:
            lower_price, upper_price, direction = current_high, first_low, "bearish"
        else:
            continue
        timestamp = pd.Timestamp(prepared.iloc[index]["timestamp"])
        events.append(
            {
                "timestamp": timestamp,
                "timeframe": timeframe,
                "direction": direction,
                "lower_price": lower_price,
                "upper_price": upper_price,
                "gap_size_ticks": (upper_price - lower_price) / tick_size,
                "source_candle_timestamp": timestamp,
                "causal": True,
                "confirmation_timestamp": timestamp,
            }
        )
    return events


def detect_first_setup_candidates(
    frame: pd.DataFrame,
    sweeps: Iterable[dict[str, object]],
    displacements: Iterable[dict[str, object]],
    *,
    timeframe: str,
    next_n_bars: int = 3,
    tick_size: float = 0.01,
    minimum_gap_ticks: float = 1,
    fvg_events: Iterable[dict[str, object]] | None = None,
) -> list[dict[str, object]]:
    """Compose causal sweep -> displacement -> associated FVG candidates."""
    if next_n_bars < 1:
        raise ValueError("next_n_bars must be >= 1")
    prepared = _prepare_frame(frame)
    persisted_fvgs = (
        list(fvg_events)
        if fvg_events is not None
        else detect_fvg(
            prepared,
            timeframe=timeframe,
            tick_size=tick_size,
            minimum_gap_ticks=minimum_gap_ticks,
        )
    )
    timestamps = prepared["timestamp"].tolist()
    timestamp_indexes = {timestamp: index for index, timestamp in enumerate(timestamps)}
    displacement_by_direction: dict[str, list[tuple[int, dict[str, object]]]] = {"bullish": [], "bearish": []}
    for event in displacements:
        if event.get("causal") is False:
            raise ValueError("candidate detection requires causal displacements")
        event_index = timestamp_indexes.get(pd.Timestamp(event["timestamp"]))
        direction = "bullish" if str(event.get("event_type", "")).endswith("bullish") else "bearish"
        if event_index is not None:
            displacement_by_direction[direction].append((event_index, event))
    for events in displacement_by_direction.values():
        events.sort(key=lambda item: item[0])
    fvg_by_direction: dict[str, list[tuple[int, dict[str, object]]]] = {"bullish": [], "bearish": []}
    for event in persisted_fvgs:
        event_index = timestamp_indexes[pd.Timestamp(event["source_candle_timestamp"])]
        fvg_by_direction[str(event["direction"])].append((event_index, event))
    displacement_indexes = {
        direction: [item[0] for item in events]
        for direction, events in displacement_by_direction.items()
    }
    fvg_indexes = {
        direction: [item[0] for item in events]
        for direction, events in fvg_by_direction.items()
    }
    candidates: list[dict[str, object]] = []
    for sweep in sorted(sweeps, key=lambda event: pd.Timestamp(event["confirmation_timestamp"])):
        if sweep.get("causal") is False:
            raise ValueError("candidate detection requires causal sweeps")
        direction = "bullish" if str(sweep.get("event_type", "")).endswith("bullish") else "bearish"
        sweep_index = timestamp_indexes.get(pd.Timestamp(sweep["confirmation_timestamp"]))
        if sweep_index is None:
            continue
        displacement_options = displacement_by_direction[direction]
        displacement_start = bisect_right(displacement_indexes[direction], sweep_index)
        if displacement_start >= len(displacement_options):
            continue
        displacement_index, matching_displacement = displacement_options[displacement_start]
        if displacement_index > sweep_index + next_n_bars:
            continue
        fvg_options = fvg_by_direction[direction]
        fvg_start = bisect_right(fvg_indexes[direction], displacement_index - 1)
        if fvg_start >= len(fvg_options):
            continue
        fvg_index, matching_fvg = fvg_options[fvg_start]
        if fvg_index > displacement_index + next_n_bars:
            continue
        candidates.append(
            {
                "timeframe": timeframe,
                "direction": direction,
                "sweep_timestamp": pd.Timestamp(sweep["confirmation_timestamp"]),
                "liquidity_level": float(sweep["level_price"]),
                "displacement_timestamp": pd.Timestamp(matching_displacement["timestamp"]),
                "fvg_timestamp": pd.Timestamp(matching_fvg["timestamp"]),
                "fvg_lower_price": float(matching_fvg["lower_price"]),
                "fvg_upper_price": float(matching_fvg["upper_price"]),
                "causal_confirmation_timestamp": pd.Timestamp(matching_fvg["confirmation_timestamp"]),
            }
        )
    return sorted(candidates, key=lambda event: event["causal_confirmation_timestamp"])


__all__ = ["detect_first_setup_candidates", "detect_fvg"]