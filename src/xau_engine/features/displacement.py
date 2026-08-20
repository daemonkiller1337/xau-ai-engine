from __future__ import annotations

import pandas as pd


def _prepare_frame(frame: pd.DataFrame, volume_column: str) -> pd.DataFrame:
    required = ["timestamp", "open", "high", "low", "close"]
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"frame must include columns: {', '.join(missing)}")
    prepared = frame.copy()
    prepared["timestamp"] = pd.to_datetime(prepared["timestamp"], errors="coerce", utc=True)
    for column in ["open", "high", "low", "close"]:
        prepared[column] = pd.to_numeric(prepared[column], errors="coerce")
    if volume_column in prepared.columns:
        prepared[volume_column] = pd.to_numeric(prepared[volume_column], errors="coerce")
    return prepared.dropna(subset=required).sort_values("timestamp").reset_index(drop=True)


def _validate_parameters(
    atr_period: int,
    min_body_atr_multiple: float,
    min_range_atr_multiple: float,
    tick_size: float,
    min_body_ticks: float,
    min_range_ticks: float,
    close_location_requirement: float | None,
    volume_confirmation: bool,
    volume_column: str,
    min_volume_multiple: float,
) -> None:
    if atr_period < 1:
        raise ValueError("atr_period must be >= 1")
    if min_body_atr_multiple < 0 or min_range_atr_multiple < 0:
        raise ValueError("ATR multiples must be >= 0")
    if tick_size <= 0:
        raise ValueError("tick_size must be > 0")
    if min_body_ticks < 0 or min_range_ticks < 0:
        raise ValueError("tick thresholds must be >= 0")
    if close_location_requirement is not None and not 0 <= close_location_requirement <= 1:
        raise ValueError("close_location_requirement must be between 0 and 1")
    if volume_confirmation and min_volume_multiple < 0:
        raise ValueError("min_volume_multiple must be >= 0")
    if volume_confirmation and not volume_column:
        raise ValueError("volume_column is required when volume_confirmation=true")


def _true_range(prepared: pd.DataFrame) -> pd.Series:
    previous_close = prepared["close"].shift(1)
    return pd.concat(
        [
            prepared["high"] - prepared["low"],
            (prepared["high"] - previous_close).abs(),
            (prepared["low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)


def detect_displacement(
    frame: pd.DataFrame,
    *,
    timeframe: str,
    atr_period: int = 14,
    min_body_atr_multiple: float = 1.0,
    min_range_atr_multiple: float = 1.5,
    tick_size: float = 0.01,
    min_body_ticks: float = 0,
    min_range_ticks: float = 0,
    close_location_requirement: float | None = None,
    volume_confirmation: bool = False,
    volume_column: str = "tick_volume",
    min_volume_multiple: float = 1.0,
) -> list[dict[str, object]]:
    """Detect bullish and bearish displacement using only data known at bar close.

    ATR is a rolling mean of true range including the current completed candle. The
    first ``atr_period - 1`` candles have no ATR and cannot produce events.
    """
    _validate_parameters(
        atr_period,
        min_body_atr_multiple,
        min_range_atr_multiple,
        tick_size,
        min_body_ticks,
        min_range_ticks,
        close_location_requirement,
        volume_confirmation,
        volume_column,
        min_volume_multiple,
    )
    prepared = _prepare_frame(frame, volume_column)
    if volume_confirmation and volume_column not in prepared.columns:
        raise ValueError(f"frame must include '{volume_column}' for volume confirmation")
    if prepared.empty:
        return []

    prepared["range"] = prepared["high"] - prepared["low"]
    prepared["body"] = (prepared["close"] - prepared["open"]).abs()
    prepared["atr"] = _true_range(prepared).rolling(atr_period, min_periods=atr_period).mean()
    if volume_confirmation:
        prepared["volume_average"] = prepared[volume_column].rolling(
            atr_period, min_periods=atr_period
        ).mean()

    events: list[dict[str, object]] = []
    for _, row in prepared.iterrows():
        atr = row["atr"]
        if pd.isna(atr) or atr <= 0:
            continue
        body = float(row["body"])
        price_range = float(row["range"])
        body_multiple = body / float(atr)
        range_multiple = price_range / float(atr)
        if body_multiple < min_body_atr_multiple or range_multiple < min_range_atr_multiple:
            continue
        if body < min_body_ticks * tick_size or price_range < min_range_ticks * tick_size:
            continue

        bullish = float(row["close"]) > float(row["open"])
        if float(row["close"]) == float(row["open"]):
            continue
        close_location = (
            (float(row["close"]) - float(row["low"])) / price_range if bullish else (float(row["high"]) - float(row["close"])) / price_range
        ) if price_range > 0 else 0.0
        if close_location_requirement is not None and close_location < close_location_requirement:
            continue
        if volume_confirmation:
            average_volume = row["volume_average"]
            if pd.isna(average_volume) or float(row[volume_column]) < float(average_volume) * min_volume_multiple:
                continue

        timestamp = pd.Timestamp(row["timestamp"])
        events.append(
            {
                "timestamp": timestamp,
                "timeframe": timeframe,
                "event_type": "displacement_bullish" if bullish else "displacement_bearish",
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "body": body,
                "range": price_range,
                "ATR": float(atr),
                "body_atr_multiple": body_multiple,
                "range_atr_multiple": range_multiple,
                "causal": True,
                "confirmation_timestamp": timestamp,
            }
        )
    return events


__all__ = ["detect_displacement"]