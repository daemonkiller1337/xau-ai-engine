from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class ValidationIssue:
    row: int
    field: str | None
    message: str


@dataclass(frozen=True)
class MarketBar:
    timestamp: datetime
    symbol: str
    broker_symbol: str = "GOLD"
    raw_broker_timestamp: datetime | None = None
    broker_timezone: str = "Europe/Athens"
    utc_timestamp: datetime | None = None
    open: Decimal = Decimal(0)
    high: Decimal = Decimal(0)
    low: Decimal = Decimal(0)
    close: Decimal = Decimal(0)
    tick_volume: int = 0
    real_volume: int = 0
    spread: int = 0
    source: str = "XM_MT5"

    def __post_init__(self) -> None:
        if isinstance(self.timestamp, str):
            object.__setattr__(self, "timestamp", datetime.fromisoformat(self.timestamp.replace("Z", "+00:00").replace(" ", "T")))
        if isinstance(self.raw_broker_timestamp, str):
            object.__setattr__(self, "raw_broker_timestamp", datetime.fromisoformat(self.raw_broker_timestamp.replace("Z", "+00:00").replace(" ", "T")))
        if self.raw_broker_timestamp is None:
            object.__setattr__(self, "raw_broker_timestamp", self.timestamp)
        if isinstance(self.utc_timestamp, str):
            object.__setattr__(self, "utc_timestamp", datetime.fromisoformat(self.utc_timestamp.replace("Z", "+00:00").replace(" ", "T")))
        if isinstance(self.open, str):
            object.__setattr__(self, "open", Decimal(self.open))
        if isinstance(self.high, str):
            object.__setattr__(self, "high", Decimal(self.high))
        if isinstance(self.low, str):
            object.__setattr__(self, "low", Decimal(self.low))
        if isinstance(self.close, str):
            object.__setattr__(self, "close", Decimal(self.close))


@dataclass
class ValidationReport:
    bars: list[MarketBar] = field(default_factory=list)
    issues: list[ValidationIssue] = field(default_factory=list)
    row_count: int = 0
    duplicate_count: int = 0
    invalid_ohlc_count: int = 0
    invalid_row_count: int = 0
    timestamp_order_violations: int = 0
    missing_value_counts: dict[str, int] = field(default_factory=dict)
    negative_value_counts: dict[str, int] = field(default_factory=dict)
    gap_stats: dict[str, Any] = field(default_factory=dict)
    spread_stats: dict[str, Any] = field(default_factory=dict)
    tick_volume_stats: dict[str, Any] = field(default_factory=dict)
    zero_real_volume_count: int = 0
    first_timestamp: datetime | None = None
    last_timestamp: datetime | None = None
    utc_first_timestamp: datetime | None = None
    utc_last_timestamp: datetime | None = None
    broker_timezone: str = "Europe/Athens"
    utc_conversion_applied: bool = False
    unique_symbols: list[str] = field(default_factory=list)

    @property
    def valid_row_count(self) -> int:
        return len(self.bars)
