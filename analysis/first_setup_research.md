# First setup research

## Scope

This is a causal research composition only, not a trading backtest. No profitability, accuracy, optimization, entries, exits, MSS, BOS, or Silver Bullet logic is included.

## Initial parameters

- `tick_size`: 0.01
- swing detector: `swing_left_bars=2`, `swing_right_bars=2`, `confirmation_mode=CAUSAL`
- liquidity: `sweep_penetration_ticks=1`, `sweep_k_bars=5`, equal-level tolerance `1` tick
- displacement: `atr_period=14`, minimum body `1.0 ATR`, minimum range `1.5 ATR`
- FVG: `minimum_gap_ticks=1`
- candidate window: `next_n_bars=3`

## Causal definitions

The FVG detector uses the standard three-candle rule. Candle `i` is the confirmation candle: bullish when `candle[i-2].high < candle[i].low`, bearish when `candle[i-2].low > candle[i].high`, subject to the minimum tick gap. The FVG timestamp and confirmation timestamp are candle `i` close.

A candidate requires a causal liquidity sweep, then a same-direction causal displacement strictly within the next `N` bars, then a same-direction FVG associated with that displacement within the configured window. Candidate confirmation is the FVG confirmation timestamp.

## Synthetic validation

Focused FVG and candidate tests: passed. They cover bullish and bearish gaps, tick thresholds, no-gap cases, causal timestamps, future-bar mutation invariance, same-direction sequencing, window limits, and non-causal input rejection.

## Real XM M15 results

Input: `data/clean/GOLD_M15_XM.parquet`

| metric | value |
| --- | ---: |
| rows | 76657 |
| swing highs | 10325 |
| swing lows | 10349 |
| equal highs | 909 |
| equal lows | 941 |
| bullish sweeps | 6642 |
| bearish sweeps | 6457 |
| total sweeps | 13099 |
| bullish displacement | 3283 |
| bearish displacement | 3223 |
| total displacement | 6506 |
| bullish FVG | 8456 |
| bearish FVG | 7415 |
| total FVG | 15871 |
| sweeps followed by same-direction displacement within 3 bars | 1870 |
| sweeps followed by displacement plus FVG | 1476 |
| bullish candidates | 775 |
| bearish candidates | 701 |

Each detector ran once. Candidate composition reused the in-memory sweep, displacement, and FVG results through the persisted-FVG input path and did not rerun upstream detectors.

## Stage timings

| stage | seconds |
| --- | ---: |
| loading | 0.060 |
| swings | 4.710 |
| liquidity | 0.091 |
| sweeps | 0.469 |
| displacement | 3.916 |
| FVG | 19.898 |
| candidate composition | 0.231 |

## First 10 candidates

| direction | sweep timestamp | liquidity level | displacement timestamp | FVG timestamp | FVG bounds | confirmation timestamp |
| --- | --- | ---: | --- | --- | --- | --- |
| bearish | 2023-05-12 10:30 UTC | 2012.23 | 2023-05-12 10:45 UTC | 2023-05-12 11:00 UTC | 2009.58 - 2010.77 | 2023-05-12 11:00 UTC |
| bearish | 2023-05-15 04:15 UTC | 2016.34 | 2023-05-15 05:00 UTC | 2023-05-15 05:15 UTC | 2014.80 - 2016.81 | 2023-05-15 05:15 UTC |
| bearish | 2023-05-15 04:15 UTC | 2015.51 | 2023-05-15 05:00 UTC | 2023-05-15 05:15 UTC | 2014.80 - 2016.81 | 2023-05-15 05:15 UTC |
| bearish | 2023-05-15 17:00 UTC | 2020.77 | 2023-05-15 17:15 UTC | 2023-05-15 17:30 UTC | 2016.99 - 2018.21 | 2023-05-15 17:30 UTC |
| bullish | 2023-05-19 18:00 UTC | 1957.80 | 2023-05-19 18:15 UTC | 2023-05-19 18:15 UTC | 1959.25 - 1967.20 | 2023-05-19 18:15 UTC |
| bearish | 2023-05-22 04:15 UTC | 1981.40 | 2023-05-22 04:30 UTC | 2023-05-22 05:15 UTC | 1978.65 - 1978.82 | 2023-05-22 05:15 UTC |
| bearish | 2023-05-22 04:15 UTC | 1981.21 | 2023-05-22 04:30 UTC | 2023-05-22 05:15 UTC | 1978.65 - 1978.82 | 2023-05-22 05:15 UTC |
| bullish | 2023-05-23 08:45 UTC | 1960.09 | 2023-05-23 09:00 UTC | 2023-05-23 09:15 UTC | 1961.86 - 1961.91 | 2023-05-23 09:15 UTC |
| bearish | 2023-05-23 09:30 UTC | 1964.25 | 2023-05-23 10:00 UTC | 2023-05-23 10:15 UTC | 1959.30 - 1961.74 | 2023-05-23 10:15 UTC |
| bearish | 2023-05-24 08:15 UTC | 1977.15 | 2023-05-24 09:00 UTC | 2023-05-24 09:15 UTC | 1977.17 - 1977.41 | 2023-05-24 09:15 UTC |

These are research counts only. No profitability or accuracy calculation was performed.
