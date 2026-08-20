# Session Windows Research

## Representation

Each `SessionWindow` is an independent configuration record with a `name`, local
`start` and `end` time, IANA `timezone`, and `enabled` flag. `SessionConfig.windows`
is an ordered list, so arbitrary named windows can be added without encoding a
particular strategy or market claim. Window names must be unique.

## Timezone handling

The resolver accepts timezone-aware candle timestamps and normalizes them to UTC
before comparison. Window times are interpreted in their configured IANA timezone;
the returned `session_start` and `session_end` are timezone-aware UTC datetimes.
Naive candle timestamps are rejected because their meaning is ambiguous.

IANA timezone rules provide seasonal offset changes. A local window therefore keeps
the same wall-clock times while its UTC boundaries move when daylight saving time
changes. Ambiguous fall-back boundary times use `fold=0` deterministically, while
nonexistent local boundary times are rejected.

## Boundary behavior

Windows use the half-open interval `[start, end)`: the start timestamp belongs to the
window and the exact end timestamp does not. If the end time is earlier than the
start time, the window crosses midnight and its end is placed on the following local
calendar date. Equal start and end times are invalid rather than silently meaning a
24-hour window.

When enabled windows overlap, the first matching window in configuration order wins.
This makes assignment deterministic. Disabled windows are skipped.

## Later candidate filtering

Once setup candidates exist, a caller can resolve each candidate candle's UTC
timestamp and retain only matches with `matched=True`, optionally grouping by
`session_name` and enforcing strategy-specific limits per name. This framework only
labels the time window; it does not create entries, signals, or trade decisions.