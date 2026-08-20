# Causal swing-structure research report

## Initial configuration

- swing_left_bars: 2
- swing_right_bars: 2
- confirmation_mode: CAUSAL
- allow_lookahead: false

## Swing counts by timeframe

| timeframe | rows | total swings | swing highs | swing lows |
| --- | ---: | ---: | ---: | ---: |
| M5 | 231737 | 62664 | 31225 | 31439 |
| M15 | 76657 | 20674 | 10325 | 10349 |
| H1 | 18516 | 4989 | 2457 | 2532 |
| H4 | 3439 | 973 | 488 | 485 |

## Causal confirmation delay

The detector is causal: a swing may only be recognized after the required left-side and right-side bars have been observed. The confirmation timestamp is the first bar at or after the point where the swing pattern has been fully known, and it is stored in the event payload as confirmation_timestamp.

## Edge cases

- Equal highs/lows are collapsed to a single swing event using the later plateau bar to avoid duplicates.
- The detector emits chronological event ordering only.
- PERFECT mode is explicitly marked as look-ahead and is rejected by default unless allow_lookahead=true.

## Notes

This is a conservative initial configuration, not an optimization or profitability claim.
