from __future__ import annotations

from collections.abc import Sequence

import pandas as pd

from .timeframes import _normalize_timeframe


def _as_utc_series(frame: pd.DataFrame) -> pd.DataFrame:
    prepared = frame.copy()
    if prepared.empty:
        return prepared
    if "timestamp" not in prepared.columns:
        raise ValueError("frame must include a timestamp column")
    prepared["timestamp"] = pd.to_datetime(prepared["timestamp"], errors="coerce", utc=True)
    prepared = prepared.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
    if prepared.empty:
        return prepared
    for column in ["high", "low"]:
        if column not in prepared.columns:
            raise ValueError(f"frame must include a '{column}' column")
        prepared[column] = pd.to_numeric(prepared[column], errors="coerce")
    prepared = prepared.dropna(subset=["high", "low"]).reset_index(drop=True)
    return prepared


def _candidate_positions(frame: pd.DataFrame, kind: str, left_bars: int, right_bars: int, *, causal: bool) -> list[int]:
    values = frame[kind].to_numpy(dtype=float)
    positions: list[int] = []
    if causal:
        start = left_bars
        stop = max(start, len(values) - right_bars)
        for idx in range(start, stop):
            candidate = values[idx]
            left_values = values[max(0, idx - left_bars) : idx]
            right_values = values[idx + 1 : idx + right_bars + 1]
            if left_values.size and right_values.size:
                if kind == "high":
                    if candidate >= left_values.max() and candidate >= right_values.max():
                        positions.append(idx)
                else:
                    if candidate <= left_values.min() and candidate <= right_values.min():
                        positions.append(idx)
            elif left_values.size:
                if kind == "high":
                    if candidate >= left_values.max():
                        positions.append(idx)
                else:
                    if candidate <= left_values.min():
                        positions.append(idx)
            elif right_values.size:
                if kind == "high":
                    if candidate >= right_values.max():
                        positions.append(idx)
                else:
                    if candidate <= right_values.min():
                        positions.append(idx)
            else:
                positions.append(idx)
    else:
        start = left_bars
        stop = len(values)
        for idx in range(start, stop):
            candidate = values[idx]
            left_values = values[max(0, idx - left_bars) : idx]
            right_values = values[idx + 1 :]
            if left_values.size and right_values.size:
                if kind == "high":
                    if candidate >= left_values.max() and candidate >= right_values.max():
                        positions.append(idx)
                else:
                    if candidate <= left_values.min() and candidate <= right_values.min():
                        positions.append(idx)
            elif left_values.size:
                if kind == "high":
                    if candidate >= left_values.max():
                        positions.append(idx)
                else:
                    if candidate <= left_values.min():
                        positions.append(idx)
            elif right_values.size:
                if kind == "high":
                    if candidate >= right_values.max():
                        positions.append(idx)
                else:
                    if candidate <= right_values.min():
                        positions.append(idx)
            else:
                positions.append(idx)
    return positions


def _deduplicate_plateaus(frame: pd.DataFrame, kind: str, positions: Sequence[int]) -> list[int]:
    if not positions:
        return []
    deduped: list[int] = []
    for idx in positions:
        if not deduped:
            deduped.append(idx)
            continue
        previous = deduped[-1]
        if previous + 1 == idx and frame.iloc[previous][kind] == frame.iloc[idx][kind]:
            deduped[-1] = idx
        else:
            deduped.append(idx)
    return deduped


def _build_swing_event(frame: pd.DataFrame, index: int, event_type: str, *, timeframe: str, causal: bool, source: str, confirmation_index: int | None = None) -> dict[str, object]:
    timestamp = pd.Timestamp(frame.iloc[index]["timestamp"])
    confirmation_ts = timestamp if confirmation_index is None else pd.Timestamp(frame.iloc[confirmation_index]["timestamp"])
    return {
        "timestamp": timestamp,
        "timeframe": timeframe,
        "event_type": event_type,
        "price": float(frame.iloc[index]["high" if event_type == "swing_high" else "low"]),
        "confirmation_timestamp": confirmation_ts,
        "causal": causal,
        "source": source,
    }


def detect_swing_points(
    frame: pd.DataFrame,
    timeframe: str | int,
    swing_left_bars: int = 2,
    swing_right_bars: int = 2,
    confirmation_mode: str = "CAUSAL",
    *,
    allow_lookahead: bool = False,
) -> list[dict[str, object]]:
    """Detect causal or perfect swing highs and lows from a price series.

    The CAUSAL mode only confirms a swing after the required right-side information is
    available at or before the confirmation timestamp. The PERFECT mode uses future data
    beyond the confirmation window and must be explicitly allowed.
    """
    if swing_left_bars < 1 or swing_right_bars < 1:
        raise ValueError("swing_left_bars and swing_right_bars must be >= 1")

    normalized_mode = str(confirmation_mode).strip().upper()
    if normalized_mode not in {"CAUSAL", "PERFECT"}:
        raise ValueError("confirmation_mode must be 'CAUSAL' or 'PERFECT'")
    if normalized_mode == "PERFECT" and not allow_lookahead:
        raise ValueError("PERFECT swing detection requires allow_lookahead=true")

    prepared = _as_utc_series(frame)
    if prepared.empty:
        return []

    _, _ = _normalize_timeframe(timeframe)
    timeframe_label = str(timeframe).strip().upper().replace(" ", "")
    if timeframe_label not in {"M5", "M15", "H1", "H4"}:
        timeframe_label = _normalize_timeframe(timeframe)[0]

    causal = normalized_mode == "CAUSAL"
    source = "CAUSAL" if causal else "PERFECT_LOOKAHEAD"

    events: list[dict[str, object]] = []
    for kind, event_type in (("high", "swing_high"), ("low", "swing_low")):
        candidate_positions = _candidate_positions(prepared, kind, swing_left_bars, swing_right_bars, causal=causal)
        deduped = _deduplicate_plateaus(prepared, kind, candidate_positions)
        for idx in deduped:
            if causal:
                max_conf = min(len(prepared) - 1, idx + swing_right_bars)
                if max_conf <= idx:
                    continue
            else:
                max_conf = idx
            events.append(
                _build_swing_event(
                    prepared,
                    idx,
                    event_type,
                    timeframe=timeframe_label,
                    causal=causal,
                    source=source,
                    confirmation_index=max_conf,
                )
            )

    events.sort(key=lambda item: (pd.Timestamp(item["timestamp"]), item["event_type"]))
    return events


__all__ = ["detect_swing_points"]
