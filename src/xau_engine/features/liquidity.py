from __future__ import annotations

from bisect import bisect_left, insort
from collections.abc import Iterable

import pandas as pd


def _prepare_frame(frame: pd.DataFrame) -> pd.DataFrame:
    prepared = frame.copy()
    required = ["timestamp", "high", "low", "close"]
    missing = [column for column in required if column not in prepared.columns]
    if missing:
        raise ValueError(f"frame must include columns: {', '.join(missing)}")
    prepared["timestamp"] = pd.to_datetime(prepared["timestamp"], errors="coerce", utc=True)
    for column in ["high", "low", "close"]:
        prepared[column] = pd.to_numeric(prepared[column], errors="coerce")
    return prepared.dropna(subset=required).sort_values("timestamp").reset_index(drop=True)


def _validate_ticks(tick_size: float, tolerance_ticks: float, penetration_ticks: float = 0) -> None:
    if tick_size <= 0:
        raise ValueError("tick_size must be > 0")
    if tolerance_ticks < 0 or penetration_ticks < 0:
        raise ValueError("tick thresholds must be >= 0")


def _swing_groups(
    swing_events: Iterable[dict[str, object]],
    event_type: str,
    tick_size: float,
    tolerance_ticks: float,
) -> list[list[dict[str, object]]]:
    events = [event for event in swing_events if event.get("event_type") == event_type]
    events.sort(key=lambda event: pd.Timestamp(event["confirmation_timestamp"]))
    groups: list[list[dict[str, object]]] = []
    tolerance = tolerance_ticks * tick_size
    for event in events:
        if event.get("causal") is False:
            raise ValueError("liquidity detection requires causal swing events")
        price = float(event["price"])
        matching_group = next(
            (
                group
                for group in groups
                if abs(price - float(group[0]["price"])) <= tolerance + tick_size * 1e-9
            ),
            None,
        )
        if matching_group is None:
            groups.append([event])
        else:
            matching_group.append(event)
    return groups


def _pool_event(
    group: list[dict[str, object]],
    liquidity_type: str,
    event_type: str,
    timeframe: str,
) -> dict[str, object]:
    source = group[-1]
    confirmation = pd.Timestamp(source["confirmation_timestamp"])
    return {
        "timestamp": confirmation,
        "timeframe": timeframe,
        "liquidity_type": liquidity_type,
        "level_price": float(group[0]["price"]),
        "source_event": event_type if len(group) == 1 else f"{event_type}_pair",
        "causal": True,
        "confirmation_timestamp": confirmation,
        "event_type": "liquidity_equal_high" if liquidity_type == "equal_high" else "liquidity_equal_low" if liquidity_type == "equal_low" else None,
    }


def detect_liquidity_pools(
    swing_events: Iterable[dict[str, object]],
    *,
    timeframe: str,
    tick_size: float,
    equal_level_tolerance_ticks: float = 1,
) -> list[dict[str, object]]:
    """Build causal pools from confirmed swing events.

    Only supplied, confirmed swing highs and lows are eligible. A singleton confirmed
    swing is a prior_swing_* pool; two or more same-side swings within the tick
    tolerance form one equal_* pool. Arbitrary candle highs and lows are excluded.
    """
    _validate_ticks(tick_size, equal_level_tolerance_ticks)
    pools: list[dict[str, object]] = []
    for event_type, prior_type, equal_type in (
        ("swing_high", "prior_swing_high", "equal_high"),
        ("swing_low", "prior_swing_low", "equal_low"),
    ):
        for group in _swing_groups(swing_events, event_type, tick_size, equal_level_tolerance_ticks):
            if len(group) >= 2:
                pools.append(_pool_event(group, equal_type, event_type, timeframe))
            else:
                event = group[0]
                confirmation = pd.Timestamp(event["confirmation_timestamp"])
                pools.append(
                    {
                        "timestamp": pd.Timestamp(event["timestamp"]),
                        "timeframe": timeframe,
                        "liquidity_type": prior_type,
                        "level_price": float(event["price"]),
                        "source_event": event_type,
                        "causal": True,
                        "confirmation_timestamp": confirmation,
                        "event_type": None,
                    }
                )
    return sorted(pools, key=lambda event: (event["confirmation_timestamp"], event["liquidity_type"]))


def _reclaim_rule(rule: str, close: float, level: float, bullish: bool) -> bool:
    normalized = rule.strip().lower()
    if normalized not in {"close_back_inside", "close_back_above_below", "close"}:
        raise ValueError("reclaim_rule must be 'close_back_inside'")
    return close > level if bullish else close < level


def detect_liquidity_sweeps(
    frame: pd.DataFrame,
    pools: Iterable[dict[str, object]],
    *,
    timeframe: str,
    tick_size: float,
    sweep_penetration_ticks: float = 1,
    sweep_k_bars: int = 5,
    reclaim_rule: str = "close_back_inside",
) -> list[dict[str, object]]:
    """Detect causal sweeps after pool confirmation and subsequent reclaim."""
    _validate_ticks(tick_size, 0, sweep_penetration_ticks)
    if sweep_k_bars < 1:
        raise ValueError("sweep_k_bars must be >= 1")
    prepared = _prepare_frame(frame)
    sweeps: list[dict[str, object]] = []
    ordered_pools = sorted(pools, key=lambda event: pd.Timestamp(event["confirmation_timestamp"]))
    for bullish in (True, False):
        pending = [
            pool
            for pool in ordered_pools
            if str(pool["liquidity_type"]).endswith("low" if bullish else "high")
        ]
        active: dict[int, dict[str, object]] = {}
        active_keys: list[int] = []
        next_pool = 0
        for index, row in prepared.iterrows():
            timestamp = pd.Timestamp(row["timestamp"])
            while next_pool < len(pending) and pd.Timestamp(pending[next_pool]["confirmation_timestamp"]) < timestamp:
                pool = pending[next_pool]
                level_key = round(float(pool["level_price"]) / tick_size)
                if level_key not in active:
                    active[level_key] = pool
                    insort(active_keys, level_key)
                next_pool += 1

            threshold_key = round((float(row["low" if bullish else "high"]) + (sweep_penetration_ticks * tick_size if bullish else -sweep_penetration_ticks * tick_size)) / tick_size)
            candidate_start = bisect_left(active_keys, threshold_key)
            candidate_keys = active_keys[candidate_start:] if bullish else active_keys[:candidate_start + 1]
            for level_key in candidate_keys.copy():
                pool = active[level_key]
                level = float(pool["level_price"])
                penetration = float(row["low" if bullish else "high"])
                penetrated = penetration <= level - sweep_penetration_ticks * tick_size if bullish else penetration >= level + sweep_penetration_ticks * tick_size
                if not penetrated:
                    continue
                reclaim_stop = min(len(prepared), index + sweep_k_bars + 1)
                reclaim_index = next(
                    (reclaim for reclaim in range(index + 1, reclaim_stop) if _reclaim_rule(reclaim_rule, float(prepared.iloc[reclaim]["close"]), level, bullish)),
                    None,
                )
                if reclaim_index is None:
                    active_keys.remove(level_key)
                    del active[level_key]
                    continue
                reclaim_timestamp = pd.Timestamp(prepared.iloc[reclaim_index]["timestamp"])
                sweeps.append(
                    {
                        "timestamp": reclaim_timestamp,
                        "timeframe": timeframe,
                        "liquidity_type": "sweep_bullish" if bullish else "sweep_bearish",
                        "level_price": level,
                        "source_event": pool["source_event"],
                        "causal": True,
                        "confirmation_timestamp": reclaim_timestamp,
                        "event_type": "liquidity_sweep_bullish" if bullish else "liquidity_sweep_bearish",
                    }
                )
                active_keys.remove(level_key)
                del active[level_key]
    return sorted(sweeps, key=lambda event: (event["confirmation_timestamp"], event["event_type"]))


def detect_liquidity_events(
    frame: pd.DataFrame,
    swing_events: Iterable[dict[str, object]],
    *,
    timeframe: str,
    tick_size: float,
    equal_level_tolerance_ticks: float = 1,
    sweep_penetration_ticks: float = 1,
    sweep_k_bars: int = 5,
    reclaim_rule: str = "close_back_inside",
) -> list[dict[str, object]]:
    """Return causal pools and sweeps, ordered by when each became knowable."""
    pools = detect_liquidity_pools(
        swing_events,
        timeframe=timeframe,
        tick_size=tick_size,
        equal_level_tolerance_ticks=equal_level_tolerance_ticks,
    )
    events = [pool for pool in pools if pool["event_type"] is not None]
    events.extend(
        detect_liquidity_sweeps(
            frame,
            pools,
            timeframe=timeframe,
            tick_size=tick_size,
            sweep_penetration_ticks=sweep_penetration_ticks,
            sweep_k_bars=sweep_k_bars,
            reclaim_rule=reclaim_rule,
        )
    )
    return sorted(events, key=lambda event: (event["confirmation_timestamp"], event["event_type"]))


__all__ = ["detect_liquidity_events", "detect_liquidity_pools", "detect_liquidity_sweeps"]