# Baseline outcome study

## Scope

This is a deterministic trading outcome study of the existing M15 candidate chain. It is not a prediction accuracy measurement, trading recommendation, or optimization exercise. No detector definitions or candidate rules were changed.

The M15 pipeline ran once and produced 1,476 candidates. The same candidate set was evaluated independently at 1R, 1.5R, 2R, and 3R.

## Execution assumptions

- Entry: open of the first M15 candle strictly after `causal_confirmation_timestamp`.
- Stop: sweep candle low for bullish candidates and sweep candle high for bearish candidates.
- Target: entry plus/minus the selected R multiple times initial risk.
- Maximum hold: 20 M15 candles, with the final close marked `expired` if neither level was reached.
- Spread: the M15 `spread` field is treated as ticks; adverse entry adjustment is `spread * 0.01` price units. The dataset field is used directly; no broker-specific cost is invented.
- Slippage: `0` ticks for this baseline because no configured baseline slippage assumption was available.
- Same-bar rule: when both stop and target are touched in one OHLC candle, the stop is selected conservatively and the event is counted in `same_bar_ambiguity_count`.
- Results are processed chronologically by candidate confirmation timestamp.

## Pipeline timing

- Candidate pipeline, including loading and all primitive detectors: `28.405s`
- Outcome evaluation was run separately for each TP multiple from the reused candidate list.

## All data

| TP | trades | wins | losses | expired | win rate | average R | median R | expectancy (R) | profit factor | total R | max drawdown (R) |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1R | 1474 | 480 | 539 | 455 | 0.3256 | -0.0531 | -0.1701 | -0.0531 | 0.8768 | -78.2709 | 105.1062 |
| 1.5R | 1474 | 283 | 563 | 628 | 0.1920 | -0.0347 | -0.2645 | -0.0347 | 0.9233 | -51.0858 | 102.3496 |
| 2R | 1474 | 163 | 574 | 737 | 0.1106 | -0.0282 | -0.3119 | -0.0282 | 0.9388 | -41.5490 | 97.1539 |
| 3R | 1474 | 57 | 576 | 841 | 0.0387 | -0.0323 | -0.3209 | -0.0323 | 0.9302 | -47.6719 | 95.5581 |

Two candidates did not produce executable trades because their entry or sweep timestamp was unavailable in the usable frame.

## Research: 2023-05-09 through 2024-12-31

704 candidates were in the split; 703 executable trades were evaluated.

| TP | trades | wins | losses | expired | win rate | average R | median R | expectancy (R) | profit factor | total R | max drawdown (R) |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1R | 703 | 204 | 257 | 242 | 0.2902 | -0.0930 | -0.2518 | -0.0930 | 0.7912 | -65.3449 | 82.5663 |
| 1.5R | 703 | 121 | 266 | 316 | 0.1721 | -0.0853 | -0.3478 | -0.0853 | 0.8166 | -59.9438 | 81.5349 |
| 2R | 703 | 66 | 274 | 363 | 0.0939 | -0.0942 | -0.3846 | -0.0942 | 0.8025 | -66.1919 | 84.9918 |
| 3R | 703 | 31 | 274 | 398 | 0.0441 | -0.0756 | -0.3894 | -0.0756 | 0.8420 | -53.1123 | 83.5763 |

## Validation: 2025-01-01 through 2025-12-31

466 candidates were in the split; 465 executable trades were evaluated.

| TP | trades | wins | losses | expired | win rate | average R | median R | expectancy (R) | profit factor | total R | max drawdown (R) |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1R | 465 | 163 | 168 | 134 | 0.3505 | -0.0204 | -0.0896 | -0.0204 | 0.9513 | -9.4922 | 40.1484 |
| 1.5R | 465 | 100 | 178 | 187 | 0.2151 | 0.0028 | -0.1701 | 0.0028 | 1.0064 | 1.3219 | 43.2973 |
| 2R | 465 | 60 | 181 | 224 | 0.1290 | 0.0253 | -0.2618 | 0.0253 | 1.0561 | 11.7754 | 33.2495 |
| 3R | 465 | 16 | 182 | 267 | 0.0344 | -0.0071 | -0.2618 | -0.0071 | 0.9843 | -3.3147 | 45.5374 |

## Holdout: 2026-01-01 through 2026-08-19

306 candidates and 306 executable trades were evaluated.

| TP | trades | wins | losses | expired | win rate | average R | median R | expectancy (R) | profit factor | total R | max drawdown (R) |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1R | 306 | 113 | 114 | 79 | 0.3693 | -0.0112 | -0.0545 | -0.0112 | 0.9731 | -3.4338 | 19.1567 |
| 1.5R | 306 | 62 | 119 | 125 | 0.2026 | 0.0246 | -0.1858 | 0.0246 | 1.0568 | 7.5362 | 18.1570 |
| 2R | 306 | 37 | 119 | 150 | 0.1209 | 0.0421 | -0.2060 | 0.0421 | 1.0958 | 12.8675 | 23.6894 |
| 3R | 306 | 10 | 120 | 176 | 0.0327 | 0.0286 | -0.2240 | 0.0286 | 1.0645 | 8.7551 | 23.5022 |

## Long versus short

At 1R across all data:

| direction | trades | wins | total R |
|---|---:|---:|---:|
| bullish | 773 | 266 | -34.0958 |
| bearish | 701 | 214 | -44.1751 |

At 1.5R, bullish total R was `-12.6606` and bearish total R was `-38.4251`. At 2R, bullish total R was `-0.8786` and bearish total R was `-40.6703`. At 3R, bullish total R was `3.2796` and bearish total R was `-50.9515`.

## Yearly performance

All-data yearly totals and trade counts:

| year | trades | 1R total R | 1.5R total R | 2R total R | 3R total R |
|---:|---:|---:|---:|---:|---:|
| 2023 | 245 | -47.4158 | -39.0347 | -52.3740 | -47.4412 |
| 2024 | 458 | -17.9291 | -20.9091 | -13.8180 | -5.6711 |
| 2025 | 465 | -9.4922 | 1.3219 | 11.7754 | -3.3147 |
| 2026 | 306 | -3.4338 | 7.5362 | 12.8675 | 8.7551 |

## MFE and MAE

All-data summaries in R units:

| TP | average MFE | median MFE | average MAE | median MAE | ambiguous same-bar cases |
|---:|---:|---:|---:|---:|---:|
| 1R | 0.6670 | 0.5862 | 0.7625 | 0.6787 | 7 |
| 1.5R | 0.7606 | 0.5862 | 0.7900 | 0.7289 | 3 |
| 2R | 0.8086 | 0.5862 | 0.8019 | 0.7350 | 1 |
| 3R | 0.8625 | 0.5862 | 0.8062 | 0.7485 | 0 |

This baseline is an outcome study only. It does not calculate profitability in currency, transaction-level broker costs beyond the documented spread assumption, or prediction accuracy.
