from __future__ import annotations

import pandas as pd

from xau_engine.features import aggregate_timeframe, build_multitimeframe_bars


def test_aggregate_timeframe_builds_completed_5m_bar_from_m1_data() -> None:
    df = pd.DataFrame(
        [
            {
                "timestamp": "2024-01-01T00:00:00Z",
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.5,
                "tick_volume": 10,
                "real_volume": 25,
                "spread": 5,
                "symbol": "XAUUSD",
            },
            {
                "timestamp": "2024-01-01T00:01:00Z",
                "open": 100.5,
                "high": 102.0,
                "low": 100.0,
                "close": 101.2,
                "tick_volume": 12,
                "real_volume": 26,
                "spread": 8,
                "symbol": "XAUUSD",
            },
            {
                "timestamp": "2024-01-01T00:02:00Z",
                "open": 101.2,
                "high": 101.7,
                "low": 100.8,
                "close": 100.9,
                "tick_volume": 15,
                "real_volume": 27,
                "spread": 6,
                "symbol": "XAUUSD",
            },
            {
                "timestamp": "2024-01-01T00:03:00Z",
                "open": 100.9,
                "high": 101.8,
                "low": 100.2,
                "close": 101.5,
                "tick_volume": 18,
                "real_volume": 28,
                "spread": 10,
                "symbol": "XAUUSD",
            },
            {
                "timestamp": "2024-01-01T00:04:00Z",
                "open": 101.5,
                "high": 102.2,
                "low": 101.0,
                "close": 101.9,
                "tick_volume": 20,
                "real_volume": 29,
                "spread": 7,
                "symbol": "XAUUSD",
            },
        ]
    )

    result = aggregate_timeframe(df, 5)

    assert len(result) == 1
    assert result.iloc[0]["timestamp"] == pd.Timestamp("2024-01-01T00:00:00Z")
    assert result.iloc[0]["open"] == 100.0
    assert result.iloc[0]["high"] == 102.2
    assert result.iloc[0]["low"] == 99.0
    assert result.iloc[0]["close"] == 101.9
    assert result.iloc[0]["tick_volume"] == 75
    assert result.iloc[0]["real_volume"] == 135
    assert result.iloc[0]["spread"] == 10


def test_aggregate_timeframe_excludes_missing_or_incomplete_buckets() -> None:
    df = pd.DataFrame(
        [
            {"timestamp": "2024-01-01T00:00:00Z", "open": 100.0, "high": 101.0, "low": 99.8, "close": 100.4, "tick_volume": 5, "real_volume": 10, "spread": 3, "symbol": "XAUUSD"},
            {"timestamp": "2024-01-01T00:01:00Z", "open": 100.4, "high": 101.2, "low": 100.1, "close": 100.8, "tick_volume": 6, "real_volume": 11, "spread": 4, "symbol": "XAUUSD"},
            {"timestamp": "2024-01-01T00:02:00Z", "open": 100.8, "high": 101.6, "low": 100.5, "close": 101.1, "tick_volume": 7, "real_volume": 12, "spread": 5, "symbol": "XAUUSD"},
            {"timestamp": "2024-01-01T00:05:00Z", "open": 101.1, "high": 101.9, "low": 100.9, "close": 101.4, "tick_volume": 9, "real_volume": 13, "spread": 6, "symbol": "XAUUSD"},
            {"timestamp": "2024-01-01T00:06:00Z", "open": 101.4, "high": 102.0, "low": 101.0, "close": 101.6, "tick_volume": 10, "real_volume": 14, "spread": 7, "symbol": "XAUUSD"},
            {"timestamp": "2024-01-01T00:07:00Z", "open": 101.6, "high": 102.1, "low": 101.3, "close": 101.8, "tick_volume": 11, "real_volume": 15, "spread": 8, "symbol": "XAUUSD"},
            {"timestamp": "2024-01-01T00:08:00Z", "open": 101.8, "high": 102.2, "low": 101.5, "close": 102.0, "tick_volume": 12, "real_volume": 16, "spread": 9, "symbol": "XAUUSD"},
            {"timestamp": "2024-01-01T00:09:00Z", "open": 102.0, "high": 102.3, "low": 101.7, "close": 102.1, "tick_volume": 13, "real_volume": 17, "spread": 10, "symbol": "XAUUSD"},
        ]
    )

    result = aggregate_timeframe(df, 5)
    assert len(result) == 1
    assert result.iloc[0]["timestamp"] == pd.Timestamp("2024-01-01T00:05:00Z")
    assert result.iloc[0]["tick_volume"] == 55


def test_aggregate_timeframe_is_utc_and_no_look_ahead() -> None:
    df = pd.DataFrame(
        [
            {"timestamp": "2024-01-01T00:00:00+02:00", "open": 100.0, "high": 100.5, "low": 99.5, "close": 100.2, "tick_volume": 5, "real_volume": 10, "spread": 4, "symbol": "XAUUSD"},
            {"timestamp": "2024-01-01T00:01:00+02:00", "open": 100.2, "high": 101.0, "low": 99.8, "close": 100.9, "tick_volume": 7, "real_volume": 11, "spread": 5, "symbol": "XAUUSD"},
            {"timestamp": "2024-01-01T00:02:00+02:00", "open": 100.9, "high": 101.4, "low": 100.1, "close": 101.0, "tick_volume": 8, "real_volume": 12, "spread": 7, "symbol": "XAUUSD"},
            {"timestamp": "2024-01-01T00:03:00+02:00", "open": 101.0, "high": 101.6, "low": 100.4, "close": 101.3, "tick_volume": 9, "real_volume": 13, "spread": 8, "symbol": "XAUUSD"},
            {"timestamp": "2024-01-01T00:04:00+02:00", "open": 101.3, "high": 101.8, "low": 100.9, "close": 101.5, "tick_volume": 10, "real_volume": 14, "spread": 9, "symbol": "XAUUSD"},
            {"timestamp": "2024-01-01T00:05:00+02:00", "open": 101.5, "high": 102.0, "low": 101.2, "close": 101.9, "tick_volume": 11, "real_volume": 15, "spread": 10, "symbol": "XAUUSD"},
        ]
    )

    result = aggregate_timeframe(df, 5)
    assert len(result) == 1
    assert result.iloc[0]["timestamp"] == pd.Timestamp("2023-12-31T22:00:00Z")
    assert result.iloc[0]["close"] == 101.5
    assert result.iloc[0]["tick_volume"] == 39


def test_multitimeframe_builder_produces_expected_complete_frames() -> None:
    timestamps = pd.date_range("2024-01-01T00:00:00Z", periods=240, freq="1min")
    rows = []
    for idx, ts in enumerate(timestamps):
        open_price = 100.0 + idx * 0.1
        close_price = open_price + 0.8
        high_price = max(open_price, close_price) + 0.5
        low_price = min(open_price, close_price) - 0.5
        rows.append(
            {
                "timestamp": ts.isoformat().replace("+00:00", "Z"),
                "open": float(open_price),
                "high": float(high_price),
                "low": float(low_price),
                "close": float(close_price),
                "tick_volume": 10 + idx,
                "real_volume": 100 + idx * 3,
                "spread": 2 + (idx % 5),
                "symbol": "XAUUSD",
            }
        )

    frames = build_multitimeframe_bars(pd.DataFrame(rows))

    assert set(frames) == {"M5", "M15", "H1", "H4"}
    assert len(frames["M5"]) == 48
    assert len(frames["M15"]) == 16
    assert len(frames["H1"]) == 4
    assert len(frames["H4"]) == 1
    assert frames["M5"].iloc[0]["tick_volume"] == 10 + 11 + 12 + 13 + 14
    assert frames["M5"].iloc[0]["spread"] == 6
    assert frames["M15"].iloc[0]["close"] == 100.0 + 14 * 0.1 + 0.8
    assert frames["H1"].iloc[0]["timestamp"] == pd.Timestamp("2024-01-01T00:00:00Z")
    assert frames["H4"].iloc[0]["timestamp"] == pd.Timestamp("2024-01-01T00:00:00Z")


def test_aggregate_timeframe_accepts_utc_timestamp_column() -> None:
    df = pd.DataFrame(
        [
            {"utc_timestamp": "2024-01-01T00:00:00+00:00", "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5, "tick_volume": 4, "real_volume": 100, "spread": 2, "symbol": "XAUUSD"},
            {"utc_timestamp": "2024-01-01T00:01:00+00:00", "open": 100.5, "high": 101.5, "low": 100.0, "close": 101.0, "tick_volume": 3, "real_volume": 101, "spread": 4, "symbol": "XAUUSD"},
            {"utc_timestamp": "2024-01-01T00:02:00+00:00", "open": 101.0, "high": 102.0, "low": 100.5, "close": 101.3, "tick_volume": 5, "real_volume": 102, "spread": 6, "symbol": "XAUUSD"},
            {"utc_timestamp": "2024-01-01T00:03:00+00:00", "open": 101.3, "high": 102.3, "low": 101.0, "close": 102.0, "tick_volume": 7, "real_volume": 103, "spread": 8, "symbol": "XAUUSD"},
            {"utc_timestamp": "2024-01-01T00:04:00+00:00", "open": 102.0, "high": 102.5, "low": 101.5, "close": 102.2, "tick_volume": 8, "real_volume": 104, "spread": 9, "symbol": "XAUUSD"},
        ]
    )

    result = aggregate_timeframe(df, 5)

    assert result.iloc[0]["timestamp"] == pd.Timestamp("2024-01-01T00:00:00Z")
    assert result.iloc[0]["tick_volume"] == 27
    assert result.iloc[0]["real_volume"] == 510
    assert result.iloc[0]["spread"] == 9
