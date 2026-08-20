from __future__ import annotations

from pathlib import Path

import pandas as pd

TIMEFRAME_MINUTES = {
    "M5": 5,
    "M15": 15,
    "H1": 60,
    "H4": 240,
}


def _normalize_timeframe(value: str | int) -> tuple[str, int]:
    if isinstance(value, int):
        if value <= 0:
            raise ValueError("timeframe minutes must be positive")
        return f"M{value}", value

    key = str(value).strip().upper().replace(" ", "")
    if key in TIMEFRAME_MINUTES:
        return key, TIMEFRAME_MINUTES[key]

    if key.endswith("M") and key[:-1].isdigit():
        minutes = int(key[:-1])
        if minutes > 0:
            return f"M{minutes}", minutes

    if key.endswith("H") and key[:-1].isdigit():
        hours = int(key[:-1])
        if hours > 0:
            return f"H{hours}", hours * 60

    raise ValueError(f"unsupported timeframe: {value!r}")


def _prepare_bars(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()

    prepared = frame.copy()
    timestamp_column = "utc_timestamp" if "utc_timestamp" in prepared.columns else "timestamp"
    prepared[timestamp_column] = pd.to_datetime(prepared[timestamp_column], errors="coerce", utc=True)
    prepared = prepared.dropna(subset=[timestamp_column]).sort_values(timestamp_column).reset_index(drop=True)

    if prepared.empty:
        return prepared

    if "symbol" not in prepared.columns:
        prepared["symbol"] = "XAUUSD"
    if "source" not in prepared.columns:
        prepared["source"] = "XM_MT5"

    prepared["open"] = pd.to_numeric(prepared["open"], errors="coerce")
    prepared["high"] = pd.to_numeric(prepared["high"], errors="coerce")
    prepared["low"] = pd.to_numeric(prepared["low"], errors="coerce")
    prepared["close"] = pd.to_numeric(prepared["close"], errors="coerce")
    prepared["tick_volume"] = pd.to_numeric(prepared["tick_volume"], errors="coerce").fillna(0).astype(int)
    prepared["real_volume"] = pd.to_numeric(prepared["real_volume"], errors="coerce").fillna(0).astype(int)
    prepared["spread"] = pd.to_numeric(prepared["spread"], errors="coerce").fillna(0).astype(int)

    prepared = prepared.rename(columns={timestamp_column: "timestamp"})
    return prepared


def _complete_bucket_timestamps(bucket_start: pd.Timestamp, minutes: int) -> pd.DatetimeIndex:
    bucket_end = bucket_start + pd.Timedelta(minutes=minutes) - pd.Timedelta(minutes=1)
    return pd.date_range(start=bucket_start, end=bucket_end, freq="1min", tz="UTC")


def aggregate_timeframe(frame: pd.DataFrame, timeframe: str | int) -> pd.DataFrame:
    """Aggregate canonical 1-minute UTC bars into larger time buckets.

    Only fully completed bars are emitted. The aggregation is causal, UTC-aligned, and
    strictly uses observed M1 data without forward-filling or fabricating missing minutes.
    The spread is represented by the maximum spread within the completed interval.
    """
    prepared = _prepare_bars(frame)
    if prepared.empty:
        return pd.DataFrame(
            columns=["timestamp", "open", "high", "low", "close", "tick_volume", "real_volume", "spread", "symbol", "source"]
        )

    _, minutes = _normalize_timeframe(timeframe)
    prepared = prepared.drop_duplicates(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
    prepared["_bucket"] = prepared["timestamp"].dt.floor(f"{minutes}min")

    rows: list[dict[str, object]] = []
    for bucket_start, group in prepared.groupby("_bucket", sort=True):
        expected = _complete_bucket_timestamps(bucket_start, minutes)
        actual = pd.DatetimeIndex(group["timestamp"].dt.floor("min").drop_duplicates().sort_values())
        if not actual.equals(expected):
            continue

        rows.append(
            {
                "timestamp": bucket_start,
                "open": float(group["open"].iloc[0]),
                "high": float(group["high"].max()),
                "low": float(group["low"].min()),
                "close": float(group["close"].iloc[-1]),
                "tick_volume": int(group["tick_volume"].sum()),
                "real_volume": int(group["real_volume"].sum()),
                "spread": int(group["spread"].max()),
                "symbol": str(group["symbol"].iloc[0]),
                "source": str(group["source"].iloc[0]),
            }
        )

    result = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "tick_volume", "real_volume", "spread", "symbol", "source"])
    if result.empty:
        return result
    return result.sort_values("timestamp").reset_index(drop=True)


def build_multitimeframe_bars(frame: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Build 5m, 15m, 1H, and 4H bar frames from canonical 1-minute UTC bars."""
    prepared = _prepare_bars(frame)
    if prepared.empty:
        return {name: pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "tick_volume", "real_volume", "spread", "symbol", "source"]) for name in TIMEFRAME_MINUTES}

    frames = {name: aggregate_timeframe(prepared, minutes) for name, minutes in TIMEFRAME_MINUTES.items()}
    return {name: frames[name] for name in ("M5", "M15", "H1", "H4")}


def generate_multitimeframe_parquets(
    input_path: str | Path = "data/clean/GOLD_M1_XM.parquet",
    output_dir: str | Path = "data/clean",
) -> dict[str, Path]:
    """Generate the complete M5/M15/H1/H4 parquet artifacts for the canonical XM M1 dataset."""
    data = pd.read_parquet(input_path)
    frames = build_multitimeframe_bars(data)
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    written: dict[str, Path] = {}
    for name, frame in frames.items():
        target = output_root / f"GOLD_{name}_XM.parquet"
        frame.to_parquet(target, index=False)
        written[name] = target

    return written


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate completed 5m/15m/1H/4H UTC candles from the canonical XM M1 parquet dataset.")
    parser.add_argument("--input", type=Path, default=Path("data/clean/GOLD_M1_XM.parquet"), help="Path to canonical M1 parquet input")
    parser.add_argument("--output-dir", type=Path, default=Path("data/clean"), help="Directory for output parquet files")
    args = parser.parse_args()

    result = generate_multitimeframe_parquets(args.input, args.output_dir)
    for name, path in result.items():
        print(f"{name}: {path}")
