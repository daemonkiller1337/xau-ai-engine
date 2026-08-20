# Causal displacement research report

## Initial research parameters

- `atr_period`: 14 completed candles
- `min_body_atr_multiple`: 1.0
- `min_range_atr_multiple`: 1.5
- `tick_size`: 0.01, from the existing XAUUSD project configuration
- `min_body_ticks`: 0
- `min_range_ticks`: 0
- `close_location_requirement`: disabled
- `volume_confirmation`: disabled

These are initial research defaults only. They were not optimized and are not profitability claims.

## Definition and causal timing

True range is the maximum of the current high-low range and the current high/low distance from the previous close. ATR is the rolling mean of true range over 14 completed candles, including the current candle. A displacement event is emitted only at that candle's close when its body and range meet the configured ATR multiples and its direction is unambiguous.

The first 13 candles have insufficient ATR history and are skipped. No ATR value is manufactured. Every event has `causal=true`, and `confirmation_timestamp` equals the displacement candle timestamp because all required inputs are known at close.

## Real XM results

| timeframe | rows | displacement | bullish | bearish | ATR mean | ATR median | ATR min | ATR max |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| M5 | 231737 | 16914 | 8330 | 8584 | 2.963386 | 1.975714 | 0.159286 | 82.944286 |
| M15 | 76657 | 6506 | 3283 | 3223 | 5.293167 | 3.593571 | 0.395000 | 87.142143 |
| H1 | 18516 | 1697 | 845 | 852 | 11.076202 | 7.465714 | 1.624286 | 144.905714 |
| H4 | 3439 | 222 | 88 | 134 | 25.503011 | 17.080000 | 5.457857 | 227.680714 |

ATR statistics are computed over all warm ATR values using the same true-range calculation as the detector.

## Representative events

| timeframe | event | timestamp UTC | open | high | low | close | ATR | body/ATR | range/ATR |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| M5 | displacement_bearish | 2023-05-09 03:00 | 2021.11 | 2021.22 | 2019.70 | 2020.11 | 0.712857 | 1.4028 | 2.1323 |
| M15 | displacement_bullish | 2023-05-09 04:15 | 2021.76 | 2024.42 | 2021.50 | 2023.23 | 1.424286 | 1.0321 | 2.0502 |
| H1 | displacement_bearish | 2023-05-09 15:00 | 2030.91 | 2031.99 | 2026.52 | 2026.79 | 3.335000 | 1.2354 | 1.6402 |
| H4 | displacement_bearish | 2023-05-16 16:00 | 2011.88 | 2012.35 | 1987.37 | 1987.49 | 12.904286 | 1.8901 | 1.9358 |

## Edge cases

- Zero-body candles are excluded because they have no bullish or bearish direction.
- Zero or invalid ATR values cannot produce events.
- Absolute tick floors are supported through `min_body_ticks` and `min_range_ticks`; no percentage-price thresholds are used.
- Close-location and tick-volume confirmation are optional and disabled in the initial real-data run.
- Future bars do not affect earlier events; ATR and all event fields use data through the current candle only.
- No existing configuration safety architecture was modified.
