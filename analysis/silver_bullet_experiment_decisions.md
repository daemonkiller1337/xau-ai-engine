# Silver Bullet Experiment Decision Matrix

## Scope and source limitations

This document turns the current research into decisions required before a future
Experiment #2 implementation. It does not implement a strategy, entry/exit logic,
MSS/BOS, or a backtest.

The reviewed sources were:

- `analysis/silver_bullet_strategy_spec.md`
- `analysis/market_structure_research_report.md`
- `analysis/liquidity_research_report.md`
- `analysis/displacement_research_report.md`
- `analysis/first_setup_research.md`
- `analysis/backtest_baseline.md`

`analysis/backtest_baseline.md` is absent from the repository. Therefore, this
matrix uses no backtest result or baseline assumption. The existing reports also
state that the first setup research is composition only and contains no entries,
exits, profitability, or optimization.

Each component has exactly one status:

- **VERIFIED:** directly supported by existing implementation or project
  specification.
- **CONFIGURABLE ASSUMPTION:** a selectable Experiment #2 value or rule that is
  reasonable to test, but is not established as fact.
- **UNDECIDED:** the source material does not responsibly determine the choice.

## Decision matrix

| Component | Status | Current evidence or Experiment #2 position |
| --- | --- | --- |
| Setup timeframe | **UNDECIDED** | M5, M15, H1, and H4 artifacts exist, and the first setup report presents M15 results, but no source assigns one as the strategy setup timeframe. Before implementation, select the timeframe on which sweep, displacement, and FVG are associated. |
| Context timeframe | **UNDECIDED** | Higher-timeframe context is described as optional, but no context timeframe or bias calculation is defined. Before implementation, decide whether context exists and, if so, which timeframe(s) and causal rule supply it. |
| Execution timeframe | **UNDECIDED** | No entry or fill model exists, so no execution timeframe is established. Before implementation, decide which bars determine entry, order fills, invalidation, and exits. |
| Session timezone | **CONFIGURABLE ASSUMPTION** | The framework supports an IANA timezone per window and normalizes candle timestamps to UTC. Using `UTC` for Experiment #2 is a reasonable neutral baseline because the canonical data and internal comparisons are UTC-normalized and the base config uses UTC. Selecting UTC rather than another zone can bias results if it changes which candles enter the sample; it must be fixed before analysis and not selected by outcome performance. |
| Session start | **UNDECIDED** | The base YAML has example windows, but the strategy specification explicitly says no exact Silver Bullet interval is confirmed. Before implementation, choose the local start time for the experiment window. |
| Session end | **UNDECIDED** | The base YAML end times are examples only. Before implementation, choose the local end time and determine whether the end excludes the final timestamp as the framework currently specifies. |
| Session boundary semantics | **VERIFIED** | Windows use `[start, end)`: start inclusive and exact end exclusive. Windows whose end precedes start cross midnight. Inputs must be timezone-aware; returned boundaries are UTC-aware. IANA DST rules are applied, nonexistent local boundaries are rejected, and ambiguous fall-back boundaries use deterministic `fold=0`. |
| Liquidity definition | **VERIFIED** | Liquidity pools are built only from confirmed causal swing events. A singleton can form a prior swing high/low pool; same-side confirmed swings within one tick form equal-level pools. Arbitrary candle highs/lows are not automatically pools. Strategy eligibility of singleton versus equal-level pools is a separate choice. |
| Sweep definition | **VERIFIED** | A bullish sweep penetrates a sell-side low pool by at least the configured penetration amount and later closes back above it within the configured horizon. A bearish sweep is symmetric. The reclaim bar is the causal confirmation bar; failed reclaim opportunities expire and are not duplicated. |
| Displacement definition | **VERIFIED** | A displacement event is confirmed at candle close using causal ATR/body/range evidence and an unambiguous direction. The documented initial parameters are ATR period 14, minimum body 1.0 ATR, minimum range 1.5 ATR, with optional close-location and volume confirmation disabled. These are verified definitions/defaults, not proven optimal values. |
| FVG definition | **VERIFIED** | A causal three-candle FVG is confirmed on the third candle close: bullish when candle `i-2` high is below candle `i` low, bearish when candle `i-2` low is above candle `i` high, subject to the minimum tick gap. |
| MSS/BOS requirement | **UNDECIDED** | `mss_enabled` is currently false and the candidate composer does not require MSS/BOS, but that establishes current detector configuration, not the future strategy requirement. Before implementation, decide whether MSS, BOS, or neither is required and define the exact causal event. |
| Candidate sequence | **VERIFIED** | The existing causal composition is: liquidity sweep, then same-direction displacement within `next_n_bars`, then same-direction FVG associated after displacement within the configured horizon. The first setup research uses `next_n_bars=3`; this is detector composition behavior, not an entry rule. |
| Entry trigger | **UNDECIDED** | No source chooses a market entry, FVG retracement, limit order, or other trigger. Before implementation, specify the exact causal event that changes a candidate into an entry order or signal. |
| Entry price | **UNDECIDED** | No source specifies FVG midpoint, FVG boundary, market close, next open, or another price. Before implementation, define the price, tick rounding, timestamp, and fill precedence. |
| Stop-loss definition | **UNDECIDED** | The material lists possible research hypotheses such as beyond the swept level, beyond the FVG, or an ATR/tick distance, but selects none. Before implementation, select placement, offset, rounding, and spread treatment. |
| Take-profit definition | **UNDECIDED** | No target, risk/reward multiple, opposing liquidity target, fixed distance, trailing rule, or time exit is supported. Before implementation, define target placement and the rule for simultaneous stop/target touches. |
| Maximum setup lifetime | **UNDECIDED** | `next_n_bars=3` constrains event association only; it does not define the lifetime of a completed candidate or an unfilled order. Before implementation, specify sweep-to-FVG, FVG-to-entry, and entry-to-exit limits, in bars or elapsed UTC time. |
| Spread treatment | **UNDECIDED** | The data model contains spread and execution config contains spread/slippage fields, but no strategy entry/stop/target price treatment is defined. Before implementation, decide whether spread is included in trigger, fill, stop, target, and ambiguity calculations. |
| Slippage | **UNDECIDED** | Slippage is configurable in the execution model, but no Experiment #2 assumption or fill model is established. Before implementation, specify whether it is zero, fixed, side-aware, or otherwise modeled, and when it is applied. |
| Candidate invalidation | **UNDECIDED** | The source verifies failed sweep reclaim rejection and causal event-horizon requirements, but does not define strategy invalidation after candidate confirmation. Before implementation, decide FVG mitigation, opposite movement, window close, data gaps, and unfilled-order expiry rules. |
| Direction/bias rules | **UNDECIDED** | Directional event semantics are verified: bullish uses sell-side low sweep followed by bullish displacement/FVG, and bearish is symmetric. A higher-timeframe bias rule is not defined; `bias_definition=structural` is only a configuration label. Before implementation, decide whether both directions trade and whether any causal context filter is required. |

## Configurable assumptions and optimization-bias risk

Only the session timezone is proposed as a concrete Experiment #2 assumption above:
use UTC as a neutral baseline. It is reasonable because UTC is the canonical
internal representation and avoids silently selecting a broker or market-local
clock. It can still introduce optimization bias if the timezone is changed after
seeing candidate counts or outcomes, because timezone changes alter the sample
membership. Fix it before running the experiment.

The existing numeric detector values are reasonable **CONFIGURABLE ASSUMPTIONS**
for a reproducible baseline, but they are not newly selected strategy decisions:

- `swing_left_bars=2`, `swing_right_bars=2`, causal confirmation;
- `equal_level_tolerance_ticks=1`;
- `sweep_penetration_ticks=1`, `sweep_k_bars=5`, `close_back_inside` reclaim;
- `atr_period=14`, minimum body `1.0 ATR`, minimum range `1.5 ATR`;
- `minimum_gap_ticks=1`;
- `next_n_bars=3`.

Keeping these values fixed is reasonable because they are the documented initial
research defaults and were not optimized. Selecting among them after looking at
Experiment #2 outcomes would introduce optimization bias. If any must change, the
change must be recorded as a new pre-registered experiment decision.

## Minimum decisions required before Experiment #2

The smallest explicit decision set needed before implementation is:

1. Select the setup timeframe.
2. Decide whether there is a context timeframe and select it if so.
3. Select the execution timeframe or explicitly state that execution is evaluated
   on the setup timeframe.
4. Select one session timezone, local start, and local end; confirm that the
   existing `[start, end)` and DST semantics apply.
5. Decide which liquidity pool types are eligible: singleton, equal-level, or both.
6. Decide whether MSS/BOS is required; if yes, define the causal event.
7. Confirm the candidate sequence and its fixed association horizon.
8. Define the entry trigger, entry price, order expiry, and fill assumptions.
9. Define stop-loss placement and take-profit placement.
10. Define candidate invalidation and maximum setup lifetime.
11. Define direction/bias rules, including whether both directions are eligible.
12. Define spread and slippage treatment for the experiment's price model.

No profitability-based parameter selection should occur while making these choices.

## Decisions we should NOT optimize yet

Keep the following fixed during Experiment #2:

- session timezone, start, and end;
- setup, context, and execution timeframe choices;
- swing confirmation parameters and causal mode;
- tick size and equal-level tolerance;
- liquidity pool eligibility and sweep penetration/reclaim parameters;
- ATR period and displacement thresholds;
- FVG minimum gap threshold;
- candidate association horizon;
- MSS/BOS choice and any structural-bias definition;
- entry price/trigger, stop placement, target placement, and setup lifetime;
- spread, slippage, fill, and ambiguous-bar assumptions;
- candidate invalidation and maximum-trades-per-window rules.

These should be selected once, documented before the run, and evaluated without
holdout access. The missing `backtest_baseline.md` must be resolved before comparing
Experiment #2 results to a claimed baseline.