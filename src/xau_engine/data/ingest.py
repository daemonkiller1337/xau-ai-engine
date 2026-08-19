from __future__ import annotations

import csv
import re
from collections.abc import Iterable
from datetime import datetime
from decimal import Decimal, InvalidOperation
from itertools import pairwise
from pathlib import Path
from typing import Any

import pandas as pd

from .models import MarketBar, ValidationIssue, ValidationReport

REQUIRED_COLUMNS = [
    "DATE",
    "TIME",
    "OPEN",
    "HIGH",
    "LOW",
    "CLOSE",
    "TICKVOL",
    "VOL",
    "SPREAD",
]
BROKER_SYMBOL = "GOLD"
CANONICAL_SYMBOL = "XAUUSD"
SOURCE_NAME = "XM_MT5"


def _normalize_column(name: str) -> str:
    return str(name).strip().strip("<>").strip().upper().replace(" ", "_")


def _as_decimal(value: Any) -> Decimal:
    if value is None:
        raise ValueError("missing value")
    text = str(value).strip()
    if not text:
        raise ValueError("missing value")
    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"invalid numeric value: {value!r}") from exc


def _parse_timestamp(date_value: Any, time_value: Any) -> datetime:
    date_text = str(date_value).strip()
    time_text = str(time_value).strip()
    if not date_text or not time_text:
        raise ValueError("missing timestamp")
    try:
        return datetime.strptime(  # noqa: DTZ007 - broker timestamp timezone is intentionally unresolved
            f"{date_text} {time_text}", "%Y.%m.%d %H:%M:%S"
        )
    except ValueError as exc:
        raise ValueError(f"invalid dates/times: {date_text} {time_text}") from exc


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and pd.isna(value):
        return True
    return isinstance(value, str) and value.strip() == ""


def detect_gaps(timestamps: Iterable[datetime | pd.Timestamp]) -> dict[str, Any]:
    values = sorted(pd.to_datetime(list(timestamps)).tolist())
    if len(values) < 2:
        return {
            "interval_count": 0,
            "normal_1m_intervals": 0,
            "gap_count": 0,
            "total_missing_minutes": 0,
            "max_missing_minutes": 0,
            "largest_gap_start": None,
            "largest_gap_end": None,
        }

    interval_count = len(values) - 1
    normal_1m_intervals = 0
    gaps: list[tuple[datetime, datetime, int]] = []

    for prev, curr in pairwise(values):
        delta_minutes = int((curr - prev).total_seconds() // 60)
        if delta_minutes == 1:
            normal_1m_intervals += 1
            continue
        if delta_minutes > 1:
            missing_minutes = delta_minutes - 1
            gaps.append((prev, curr, missing_minutes))

    if not gaps:
        return {
            "interval_count": interval_count,
            "normal_1m_intervals": normal_1m_intervals,
            "gap_count": 0,
            "total_missing_minutes": 0,
            "max_missing_minutes": 0,
            "largest_gap_start": None,
            "largest_gap_end": None,
        }

    largest_gap = max(gaps, key=lambda item: item[2])
    largest_gap_start, largest_gap_end, largest_gap_minutes = largest_gap

    return {
        "interval_count": interval_count,
        "normal_1m_intervals": normal_1m_intervals,
        "gap_count": len(gaps),
        "total_missing_minutes": sum(item[2] for item in gaps),
        "max_missing_minutes": largest_gap_minutes,
        "largest_gap_start": largest_gap_start.isoformat(),
        "largest_gap_end": largest_gap_end.isoformat(),
    }


def _summarize_numeric(values: list[int | float]) -> dict[str, float | int | None]:
    if not values:
        return {"min": None, "max": None, "mean": None, "median": None}
    numeric = sorted(values)
    count = len(numeric)
    mean_value = sum(numeric) / count
    median_value = numeric[count // 2] if count % 2 else (numeric[count // 2 - 1] + numeric[count // 2]) / 2
    return {
        "min": numeric[0],
        "max": numeric[-1],
        "mean": mean_value,
        "median": median_value,
    }


def _validate_market_bar(row_data: dict[str, Any], row_number: int) -> tuple[MarketBar | None, list[ValidationIssue]]:
    issues: list[ValidationIssue] = []
    try:
        timestamp = _parse_timestamp(row_data["DATE"], row_data["TIME"])
    except ValueError as exc:
        issues.append(ValidationIssue(row=row_number, field="timestamp", message=str(exc)))
        return None, issues

    try:
        open_price = _as_decimal(row_data["OPEN"])
        high_price = _as_decimal(row_data["HIGH"])
        low_price = _as_decimal(row_data["LOW"])
        close_price = _as_decimal(row_data["CLOSE"])
    except ValueError as exc:
        issues.append(ValidationIssue(row=row_number, field="ohlc", message=str(exc)))
        return None, issues

    price_fields = {
        "open": open_price,
        "high": high_price,
        "low": low_price,
        "close": close_price,
    }
    for field_name, value in price_fields.items():
        if value <= 0:
            issues.append(
                ValidationIssue(
                    row=row_number,
                    field=field_name,
                    message=f"positive prices required: {field_name}={value}",
                )
            )

    if high_price < max(open_price, close_price, low_price):
        issues.append(
            ValidationIssue(
                row=row_number,
                field="HIGH",
                message="invalid OHLC: high < max(open, close, low)",
            )
        )
    if low_price > min(open_price, close_price, high_price):
        issues.append(
            ValidationIssue(
                row=row_number,
                field="LOW",
                message="invalid OHLC: low > min(open, close, high)",
            )
        )

    try:
        tick_volume = int(str(row_data["TICKVOL"]).strip())
    except ValueError:
        issues.append(ValidationIssue(row=row_number, field="TICKVOL", message="invalid tick volume"))
        tick_volume = -1
    else:
        if tick_volume < 0:
            issues.append(ValidationIssue(row=row_number, field="TICKVOL", message="tick volume cannot be negative"))

    try:
        real_volume = int(str(row_data["VOL"]).strip())
    except ValueError:
        issues.append(ValidationIssue(row=row_number, field="VOL", message="invalid real volume"))
        real_volume = -1
    else:
        if real_volume < 0:
            issues.append(ValidationIssue(row=row_number, field="VOL", message="real volume cannot be negative"))

    try:
        spread = int(str(row_data["SPREAD"]).strip())
    except ValueError:
        issues.append(ValidationIssue(row=row_number, field="SPREAD", message="invalid spread"))
        spread = -1
    else:
        if spread < 0:
            issues.append(ValidationIssue(row=row_number, field="SPREAD", message="spread cannot be negative"))

    if issues:
        return None, issues

    return (
        MarketBar(
            timestamp=timestamp,
            symbol=CANONICAL_SYMBOL,
            broker_symbol=BROKER_SYMBOL,
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            tick_volume=tick_volume,
            real_volume=real_volume,
            spread=spread,
            source=SOURCE_NAME,
        ),
        issues,
    )


def _load_xm_table(path: Path) -> pd.DataFrame:
    raw_lines = [line.rstrip("\n") for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    if not raw_lines:
        return pd.DataFrame()

    if any("\t" in line for line in raw_lines):
        rows = [next(csv.reader([line], delimiter="\t")) for line in raw_lines]
    else:
        rows = [re.split(r"\s+", line.strip()) for line in raw_lines]

    max_columns = max(len(row) for row in rows)
    normalized_rows = [row + [""] * (max_columns - len(row)) for row in rows]
    frame = pd.DataFrame(normalized_rows[1:], columns=normalized_rows[0])
    return frame.astype(str)


def parse_xm_csv(path: str | Path) -> ValidationReport:
    csv_path = Path(path)
    raw_df = _load_xm_table(csv_path)
    if raw_df.empty:
        return ValidationReport(row_count=0, unique_symbols=[CANONICAL_SYMBOL], missing_value_counts={})

    raw_df.columns = [_normalize_column(col) for col in raw_df.columns]
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in raw_df.columns]
    if missing_columns:
        raise ValueError(f"required columns missing: {missing_columns}")

    report = ValidationReport(
        row_count=len(raw_df),
        missing_value_counts={column.lower(): 0 for column in REQUIRED_COLUMNS},
        negative_value_counts={column.lower(): 0 for column in ["OPEN", "HIGH", "LOW", "CLOSE", "TICKVOL", "VOL", "SPREAD"]},
    )

    seen_timestamps: dict[datetime, int] = {}
    valid_bars: list[MarketBar] = []
    previous_timestamp: datetime | None = None

    for row_number, row in raw_df.iterrows():
        row_data = {key: row.get(key, "") for key in REQUIRED_COLUMNS}
        missing_fields = [field for field in REQUIRED_COLUMNS if _is_missing(row_data.get(field))]
        if missing_fields:
            for field_name in missing_fields:
                lowercase_name = field_name.lower()
                report.missing_value_counts[lowercase_name] += 1
                report.issues.append(
                    ValidationIssue(
                        row=int(row_number) + 2,
                        field=field_name,
                        message=f"missing value for {field_name}",
                    )
                )
            report.invalid_row_count += 1
            continue

        bar, issues = _validate_market_bar(row_data, int(row_number) + 2)
        if issues:
            invalid_ohlc = any(issue.field in {"HIGH", "LOW", "OPEN", "CLOSE"} for issue in issues)
            if invalid_ohlc:
                report.invalid_ohlc_count += 1
            for issue in issues:
                report.issues.append(issue)
                if issue.field in {"VOL", "SPREAD", "TICKVOL"} and "negative" in issue.message.lower():
                    report.negative_value_counts[issue.field.lower()] += 1
            report.invalid_row_count += 1
            continue

        if bar is None:
            continue

        timestamp = bar.timestamp
        if timestamp in seen_timestamps:
            report.duplicate_count += 1
            report.issues.append(
                ValidationIssue(
                    row=int(row_number) + 2,
                    field="timestamp",
                    message=f"duplicate timestamp detected: {timestamp.isoformat()}",
                )
            )
            continue
        seen_timestamps[timestamp] = int(row_number) + 2

        if previous_timestamp is not None and timestamp <= previous_timestamp:
            report.timestamp_order_violations += 1
            report.issues.append(
                ValidationIssue(
                    row=int(row_number) + 2,
                    field="timestamp",
                    message=f"timestamp ordering violation: {timestamp.isoformat()} <= {previous_timestamp.isoformat()}",
                )
            )
        previous_timestamp = timestamp
        valid_bars.append(bar)

    report.bars = valid_bars
    if valid_bars:
        report.first_timestamp = min(bar.timestamp for bar in valid_bars)
        report.last_timestamp = max(bar.timestamp for bar in valid_bars)
        report.unique_symbols = sorted({bar.symbol for bar in valid_bars})
        report.spread_stats = _summarize_numeric([bar.spread for bar in valid_bars])
        report.tick_volume_stats = _summarize_numeric([bar.tick_volume for bar in valid_bars])
        report.zero_real_volume_count = sum(1 for bar in valid_bars if bar.real_volume == 0)
        report.gap_stats = detect_gaps([bar.timestamp for bar in valid_bars])
    else:
        report.unique_symbols = [CANONICAL_SYMBOL]
        report.gap_stats = {"gap_count": 0, "total_gap_minutes": 0, "max_gap_minutes": 0, "mean_gap_minutes": 0.0, "min_gap_minutes": 0}

    for bar in valid_bars:
        if bar.real_volume < 0:
            report.negative_value_counts["vol"] += 1
        if bar.spread < 0:
            report.negative_value_counts["spread"] += 1
        if bar.tick_volume < 0:
            report.negative_value_counts["tickvol"] += 1

    report.invalid_row_count = len(report.issues)
    return report


def validate_market_bars(bars: list[MarketBar]) -> ValidationReport:
    report = ValidationReport(bars=list(bars), row_count=len(bars))
    report.unique_symbols = sorted({bar.symbol for bar in bars})
    report.first_timestamp = min((bar.timestamp for bar in bars), default=None)
    report.last_timestamp = max((bar.timestamp for bar in bars), default=None)
    report.gap_stats = detect_gaps([bar.timestamp for bar in bars])
    report.spread_stats = _summarize_numeric([bar.spread for bar in bars])
    report.tick_volume_stats = _summarize_numeric([bar.tick_volume for bar in bars])
    report.zero_real_volume_count = sum(1 for bar in bars if bar.real_volume == 0)
    return report
