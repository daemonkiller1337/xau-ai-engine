# Causal liquidity research report

## Initial research defaults

- `tick_size`: 0.01, from the existing XAUUSD project configuration
- `equal_level_tolerance_ticks`: 1
- `sweep_penetration_ticks`: 1
- `sweep_k_bars`: 5
- `reclaim_rule`: `close_back_inside` (bullish close above the level; bearish close below)
- Swing input: `swing_left_bars=2`, `swing_right_bars=2`, `confirmation_mode=CAUSAL`

These are initial research defaults only. They were not optimized and are not profitability claims.

## Definitions

A liquidity pool is created only from a confirmed causal swing event. A singleton becomes a `prior_swing_high` or `prior_swing_low` pool. Two or more same-side confirmed swings within one tick of the first level become one equal-high or equal-low pool. Arbitrary candle highs/lows are not automatically treated as pools.

A bullish sweep uses a sell-side low pool: a later bar must trade at least one tick below the level, and a subsequent bar within five bars must close above it. A bearish sweep is the symmetric high-pool case.

## Real XM counts

| timeframe | rows | equal highs | equal lows | sweeps | bullish sweeps | bearish sweeps |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| M5 | 231737 | 5415 | 5530 | 33663 | 17189 | 16474 |
| M15 | 76657 | 905 | 939 | 13103 | 6645 | 6458 |
| H1 | 18516 | 61 | 84 | 3209 | 1632 | 1577 |
| H4 | 3439 | 4 | 5 | 563 | 291 | 272 |

## Example events

| timeframe | event | timestamp | level |
| --- | --- | --- | ---: |
| M5 | liquidity_equal_low | 2023-05-10 13:05 UTC | 2028.82 |
| M5 | liquidity_sweep_bullish | 2023-05-09 02:05 UTC | 2020.61 |
| M15 | liquidity_equal_high | 2023-05-12 08:15 UTC | 2012.23 |
| M15 | liquidity_sweep_bearish | 2023-05-09 04:30 UTC | 2022.29 |
| H1 | liquidity_equal_high | 2023-05-17 07:00 UTC | 1992.89 |
| H1 | liquidity_sweep_bearish | 2023-05-09 15:00 UTC | 2028.62 |
| H4 | liquidity_equal_low | 2023-06-12 12:00 UTC | 1954.11 |
| H4 | liquidity_sweep_bullish | 2023-05-16 12:00 UTC | 2011.38 |

## Causal behavior and edge cases

Pool timestamps use the confirmation timestamp of the final swing that makes an equal-level cluster knowable. Sweep events are emitted on the reclaim bar, never on the penetration bar, because the reclaim close is required evidence. Levels are activated only after pool confirmation, and a level is evaluated once after penetration; a failed reclaim expires that sweep opportunity, suppressing repeated duplicates. Non-causal swing events are rejected as inputs.

The existing configuration safety architecture was not modified. No look-ahead mode was added.
