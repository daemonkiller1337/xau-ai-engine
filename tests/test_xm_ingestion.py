from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from xau_engine.data.ingest import convert_broker_time_to_utc, detect_gaps, parse_xm_csv
from xau_engine.data.models import MarketBar


@pytest.fixture
def valid_csv(tmp_path: Path) -> Path:
    csv_path = tmp_path / "valid.csv"
    csv_path.write_text(
        """<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\t<VOL>\t<SPREAD>
2023.05.09\t01:00:00\t2020.84\t2020.95\t2020.63\t2020.82\t27\t0\t5
2023.05.09\t01:01:00\t2020.75\t2020.89\t2020.73\t2020.87\t30\t0\t4
2023.05.09\t01:02:00\t2020.86\t2021.09\t2020.86\t2021.06\t27\t0\t4
""",
        encoding="utf-8",
    )
    return csv_path


def test_valid_row_parsing(valid_csv: Path) -> None:
    result = parse_xm_csv(valid_csv)
    assert len(result.bars) == 3
    assert result.bars[0].symbol == "XAUUSD"
    assert result.bars[0].broker_symbol == "GOLD"
    assert result.bars[0].timestamp.isoformat() == "2023-05-09T01:00:00"
    assert result.bars[0].spread == 5


def test_required_column_validation(tmp_path: Path) -> None:
    path = tmp_path / "missing.csv"
    path.write_text(
        """<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\t<VOL>
2023.05.09\t01:00:00\t2020.84\t2020.95\t2020.63\t2020.82\t27\t0
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="required columns"):
        parse_xm_csv(path)


def test_malformed_row_rejection_reporting(tmp_path: Path) -> None:
    path = tmp_path / "bad.csv"
    path.write_text(
        """<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\t<VOL>\t<SPREAD>
2023.05.09\t01:00:00\t2020.84\t2020.95\t2020.63\t2020.82\t27\t0\t5
2023.05.09\tBADTIME\t2020.84\t2020.95\t2020.63\t2020.82\t27\t0\t5
""",
        encoding="utf-8",
    )
    result = parse_xm_csv(path)
    assert result.invalid_row_count >= 1
    assert any("invalid dates" in issue.message.lower() for issue in result.issues)


def test_invalid_ohlc_detection(tmp_path: Path) -> None:
    path = tmp_path / "bad_ohlc.csv"
    path.write_text(
        """<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\t<VOL>\t<SPREAD>
2023.05.09\t01:00:00\t100\t90\t95\t101\t5\t0\t5
""",
        encoding="utf-8",
    )
    result = parse_xm_csv(path)
    assert result.invalid_ohlc_count == 1


def test_duplicate_detection(tmp_path: Path) -> None:
    path = tmp_path / "dup.csv"
    path.write_text(
        """<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\t<VOL>\t<SPREAD>
2023.05.09\t01:00:00\t2020.84\t2020.95\t2020.63\t2020.82\t27\t0\t5
2023.05.09\t01:00:00\t2020.90\t2020.99\t2020.70\t2020.88\t27\t0\t5
""",
        encoding="utf-8",
    )
    result = parse_xm_csv(path)
    assert result.duplicate_count == 1


def test_negative_spread_detection(tmp_path: Path) -> None:
    path = tmp_path / "neg_spread.csv"
    path.write_text(
        """<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\t<VOL>\t<SPREAD>
2023.05.09\t01:00:00\t2020.84\t2020.95\t2020.63\t2020.82\t27\t0\t-2
""",
        encoding="utf-8",
    )
    result = parse_xm_csv(path)
    assert result.negative_value_counts["spread"] == 1


def test_missing_values_are_reported(tmp_path: Path) -> None:
    path = tmp_path / "missing_values.csv"
    path.write_text(
        """<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\t<VOL>\t<SPREAD>
2023.05.09\t01:00:00\t\t2020.95\t2020.63\t2020.82\t27\t0\t5
""",
        encoding="utf-8",
    )
    result = parse_xm_csv(path)
    assert result.missing_value_counts["open"] == 1


def test_timestamp_ordering_and_gap_detection(tmp_path: Path) -> None:
    path = tmp_path / "ordering.csv"
    path.write_text(
        """<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\t<VOL>\t<SPREAD>
2023.05.09\t01:02:00\t2020.86\t2021.09\t2020.86\t2021.06\t27\t0\t4
2023.05.09\t01:00:00\t2020.84\t2020.95\t2020.63\t2020.82\t27\t0\t5
""",
        encoding="utf-8",
    )
    result = parse_xm_csv(path)
    assert result.timestamp_order_violations >= 1
    assert result.gap_stats["gap_count"] >= 1


def test_gap_detection_uses_timestamps_not_every_minute() -> None:
    ts = pd.to_datetime(["2023-05-09 01:00:00", "2023-05-09 01:02:00", "2023-05-09 01:04:00"])
    stats = detect_gaps(ts)
    assert stats["interval_count"] == 2
    assert stats["normal_1m_intervals"] == 0
    assert stats["gap_count"] == 2
    assert stats["total_missing_minutes"] == 2
    assert stats["max_missing_minutes"] == 1


def test_gap_detection_counts_only_missing_intervals() -> None:
    ts = pd.to_datetime([
        "2023-05-09 10:00:00",
        "2023-05-09 10:01:00",
        "2023-05-09 10:02:00",
        "2023-05-09 10:05:00",
    ])
    stats = detect_gaps(ts)
    assert stats["interval_count"] == 3
    assert stats["normal_1m_intervals"] == 2
    assert stats["gap_count"] == 1
    assert stats["total_missing_minutes"] == 2
    assert stats["max_missing_minutes"] == 2
    assert stats["largest_gap_start"] == "2023-05-09T10:02:00"
    assert stats["largest_gap_end"] == "2023-05-09T10:05:00"


def test_gap_detection_all_consecutive_minutes_is_not_a_gap() -> None:
    ts = pd.to_datetime([
        "2023-05-09 10:00:00",
        "2023-05-09 10:01:00",
        "2023-05-09 10:02:00",
        "2023-05-09 10:03:00",
    ])
    stats = detect_gaps(ts)
    assert stats["interval_count"] == 3
    assert stats["normal_1m_intervals"] == 3
    assert stats["gap_count"] == 0
    assert stats["total_missing_minutes"] == 0
    assert stats["max_missing_minutes"] == 0


def test_market_bar_canonical_mapping() -> None:
    bar = MarketBar(
        timestamp="2023-05-09T01:00:00",
        symbol="XAUUSD",
        broker_symbol="GOLD",
        open="2020.84",
        high="2020.95",
        low="2020.63",
        close="2020.82",
        tick_volume=27,
        real_volume=0,
        spread=5,
        source="XM_MT5",
    )
    assert bar.symbol == "XAUUSD"
    assert bar.broker_symbol == "GOLD"
    assert bar.source == "XM_MT5"
    assert bar.timestamp.isoformat() == "2023-05-09T01:00:00"


def test_timestamp_remains_naive(tmp_path: Path) -> None:
    csv_path = tmp_path / "tiny_valid.csv"
    csv_path.write_text(
        """<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\t<VOL>\t<SPREAD>
2023.05.09\t01:00:00\t2020.84\t2020.95\t2020.63\t2020.82\t27\t0\t5
""",
        encoding="utf-8",
    )
    result = parse_xm_csv(csv_path)
    assert result.bars[0].timestamp.tzinfo is None


def test_summer_offset_uses_dst_aware_broker_timezone() -> None:
    raw = pd.Timestamp("2026-08-19 23:11:00")
    utc_value = convert_broker_time_to_utc(raw, "Europe/Athens")
    assert utc_value.isoformat() == "2026-08-19T20:11:00+00:00"


def test_winter_offset_uses_standard_broker_timezone() -> None:
    raw = pd.Timestamp("2025-01-15 12:00:00")
    utc_value = convert_broker_time_to_utc(raw, "Europe/Athens")
    assert utc_value.isoformat() == "2025-01-15T10:00:00+00:00"


def test_dst_transition_is_handled_correctly() -> None:
    before_spring = convert_broker_time_to_utc(pd.Timestamp("2025-03-30 01:59:00"), "Europe/Athens")
    assert before_spring.isoformat() == "2025-03-29T23:59:00+00:00"
    with pytest.raises(ValueError, match="nonexistent local broker timestamp"):
        convert_broker_time_to_utc(pd.Timestamp("2025-03-30 03:00:00"), "Europe/Athens")


def test_parse_xm_csv_preserves_raw_and_sets_utc_timestamp(tmp_path: Path) -> None:
    csv_path = tmp_path / "utc.csv"
    csv_path.write_text(
        """<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\t<VOL>\t<SPREAD>
2026.08.19\t23:11:00\t2020.84\t2020.95\t2020.63\t2020.82\t27\t0\t5
""",
        encoding="utf-8",
    )
    result = parse_xm_csv(csv_path, broker_timezone="Europe/Athens")
    assert result.bars[0].raw_broker_timestamp == result.bars[0].timestamp
    assert result.bars[0].utc_timestamp is not None
    assert result.bars[0].utc_timestamp.isoformat() == "2026-08-19T20:11:00+00:00"
    assert result.broker_timezone == "Europe/Athens"
