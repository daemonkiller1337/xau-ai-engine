from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from .ingest import parse_xm_csv


def _write_clean_parquet(report, output_path: Path) -> None:
    frame = pd.DataFrame(
        [
            {
                "timestamp": bar.timestamp.isoformat(),
                "symbol": bar.symbol,
                "broker_symbol": bar.broker_symbol,
                "open": str(bar.open),
                "high": str(bar.high),
                "low": str(bar.low),
                "close": str(bar.close),
                "tick_volume": bar.tick_volume,
                "real_volume": bar.real_volume,
                "spread": bar.spread,
                "source": bar.source,
            }
            for bar in report.bars
        ]
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(output_path, index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate and normalize XM MT5 XAUUSD market-bar exports.")
    parser.add_argument("input_csv", type=Path, help="Path to raw XM CSV export")
    parser.add_argument("--output", type=Path, default=Path("data/clean/GOLD_M1_XM.parquet"), help="Parquet output path")
    parser.add_argument("--report", type=Path, default=Path("data/clean/GOLD_M1_XM_REPORT.json"), help="JSON validation report path")
    args = parser.parse_args()

    report = parse_xm_csv(args.input_csv)
    _write_clean_parquet(report, args.output)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps({
        "row_count": report.row_count,
        "valid_row_count": report.valid_row_count,
        "first_timestamp": report.first_timestamp.isoformat() if report.first_timestamp else None,
        "last_timestamp": report.last_timestamp.isoformat() if report.last_timestamp else None,
        "unique_symbols": report.unique_symbols,
        "duplicate_count": report.duplicate_count,
        "invalid_ohlc_count": report.invalid_ohlc_count,
        "missing_value_counts": report.missing_value_counts,
        "negative_value_counts": report.negative_value_counts,
        "gap_stats": report.gap_stats,
        "spread_stats": report.spread_stats,
        "tick_volume_stats": report.tick_volume_stats,
        "zero_real_volume_count": report.zero_real_volume_count,
        "issue_count": len(report.issues),
        "issues": [
            {"row": issue.row, "field": issue.field, "message": issue.message} for issue in report.issues
        ],
    }, indent=2), encoding="utf-8")

    print(json.dumps({
        "row_count": report.row_count,
        "valid_row_count": report.valid_row_count,
        "first_timestamp": report.first_timestamp.isoformat() if report.first_timestamp else None,
        "last_timestamp": report.last_timestamp.isoformat() if report.last_timestamp else None,
        "unique_symbols": report.unique_symbols,
        "duplicate_count": report.duplicate_count,
        "invalid_ohlc_count": report.invalid_ohlc_count,
        "negative_value_counts": report.negative_value_counts,
        "gap_stats": report.gap_stats,
        "spread_stats": report.spread_stats,
        "tick_volume_stats": report.tick_volume_stats,
        "zero_real_volume_count": report.zero_real_volume_count,
    }, indent=2))


if __name__ == "__main__":
    main()
