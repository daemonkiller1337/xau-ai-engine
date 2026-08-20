# Silver Bullet-Style Setup Research Specification

## Status and evidence labels

This is a research specification for a future setup implementation. It is not a
claim that the project has established a profitable strategy, and it does not define
BUY/SELL signals or execution behavior.

- **VERIFIED FROM SOURCE** means the behavior or parameter is present in the
  repository's existing research reports, detectors, configuration, or tests.
- **CONFIGURABLE ASSUMPTION** means a value or rule can be supplied for research,
  but is not established as a strategy truth.
- **NOT YET DECIDED** means implementation must not choose silently.

Where this document uses the phrase "Silver Bullet-style", it refers only to the
intended future use of a time-window-filtered liquidity/displacement/FVG setup. It
does not assert that any unverified rule is official Silver Bullet behavior.

## 1. Strategy objective

**CONFIGURABLE ASSUMPTION:** Research a causal, time-window-filtered setup that
identifies a directional liquidity event followed by displacement and a fair value
gap, then supplies a candidate for a future entry model.

**VERIFIED FROM SOURCE:** The repository already supports causal swing structure,
causal liquidity pools and sweeps, causal displacement, causal FVG detection, and a
causal sweep -> displacement -> associated FVG candidate composer.

Profit target, win rate, risk-adjusted objective, and trade frequency are **NOT YET
DECIDED** and must not be implied by this specification.

## 2. Timeframe architecture

| Role | Current specification | Status |
| --- | --- | --- |
| Setup timeframe | The timeframe on which the ordered sweep, displacement, and FVG events are associated. Existing candidate composition accepts a `timeframe` argument. | **NOT YET DECIDED** |
| Context timeframe(s) | Optional higher timeframe data for structural context or bias. The existing project has M5, M15, H1, and H4 aggregation and causal structure events. | **NOT YET DECIDED** |
| Execution timeframe | The timeframe on which a future entry trigger or fill would be evaluated. | **NOT YET DECIDED** |
| Source data | XM XAUUSD M1 data with UTC-normalized artifacts and causal aggregation to M5/M15/H1/H4. | **VERIFIED FROM SOURCE** |

The initial implementation must not infer a timeframe role from the name
"Silver Bullet". The selected setup, context, and execution timeframes must be
explicit configuration or an explicit experiment specification.

## 3. Session/window logic

**VERIFIED FROM SOURCE:** The session framework represents each window as:

- `name`
- local `start` time
- local `end` time
- IANA `timezone`
- `enabled`

Windows are an ordered configurable list. The resolver accepts a timezone-aware
candle timestamp, normalizes it to UTC, and returns whether it matched, the window
name, and UTC session start/end boundaries. The interval is half-open: `[start, end)`.
The start is included and the exact end is excluded. Windows whose end precedes
their start cross midnight on the local calendar.

**VERIFIED FROM SOURCE:** IANA timezone rules are used for DST. Local wall-clock
times remain stable while their UTC boundaries change with the seasonal offset.
Ambiguous fall-back boundary times use a deterministic `fold=0` choice; nonexistent
local boundary times are rejected. Naive candle timestamps are rejected.

**CONFIGURABLE ASSUMPTION:** Setup candidates will be filtered by resolving the
candidate's causal UTC confirmation timestamp against enabled configured windows.
The candidate should carry the matched window identity and boundaries for later
analysis.

The exact strategy window is **NOT YET DECIDED**. No existing project source
confirms an official Silver Bullet interval, and no particular London or New York
interval may be treated as confirmed. The current base YAML windows are examples,
not validated strategy parameters. Timezone, start, end, enabled state, overlap
policy, and whether a candidate is assigned by sweep time or final FVG confirmation
must remain explicit experiment choices.

## 4. Required event sequence

### Current causal candidate sequence

**VERIFIED FROM SOURCE:** The existing candidate composer associates, in order:

1. A causal liquidity sweep.
2. A same-direction causal displacement after the sweep.
3. A same-direction causal FVG associated after the displacement.

The current composer looks for the first qualifying displacement after the sweep and
the first qualifying FVG after that displacement, with `next_n_bars` defaulting to 3
for each association. This is detector behavior, not a final trading rule.

### Event definitions and open choices

- **Liquidity condition:** **VERIFIED FROM SOURCE** liquidity pools derive from
  confirmed causal swing highs/lows. Equal-level pools use the configured tick
  tolerance. **CONFIGURABLE ASSUMPTION:** A bullish setup uses a sell-side low pool
  and a bearish setup uses a buy-side high pool. Whether singleton pools, equal-level
  pools, or both are eligible is **NOT YET DECIDED** for the strategy.
- **Sweep:** **VERIFIED FROM SOURCE** a bullish sweep penetrates a sell-side low and
  later reclaims above it; a bearish sweep is symmetric. The reclaim bar is the
  causal confirmation bar. Penetration, reclaim tolerance, and maximum reclaim
  delay are configurable detector parameters.
- **Displacement:** **VERIFIED FROM SOURCE** displacement is confirmed at candle
  close using causal ATR/body/range evidence. Initial research defaults are ATR
  period 14, body multiple 1.0, and range multiple 1.5; these are not optimized.
- **MSS/BOS:** **VERIFIED FROM SOURCE** the research config has `mss_enabled: false`,
  and the current candidate sequence does not require an MSS/BOS event. Whether a
  future strategy requires causal MSS, BOS, or neither is **NOT YET DECIDED**.
- **FVG:** **VERIFIED FROM SOURCE** a causal three-candle FVG is confirmed on the
  third candle close. Gap size is measured in ticks; direction must match the
  candidate direction. The minimum gap threshold is configurable and not optimized.
- **Entry condition:** **NOT YET DECIDED.** The existing candidate is not an entry
  signal and does not specify a retracement, limit order, market order, or fill rule.

The future implementation must reject any sequence that uses an event before its
causal confirmation timestamp. It must also define whether all events must occur in
one configured window or only the final candidate confirmation must be inside it.

## 5. Direction rules

**CONFIGURABLE ASSUMPTION pending strategy approval:**

- **Bullish setup:** sell-side liquidity low is swept, price reclaims the level,
  bullish displacement follows, and a bullish FVG follows.
- **Bearish setup:** buy-side liquidity high is swept, price reclaims below the
  level, bearish displacement follows, and a bearish FVG follows.

**VERIFIED FROM SOURCE:** The existing sweep, displacement, FVG, and candidate
components are direction-aware and associate same-direction events. A higher
timeframe directional bias filter is **NOT YET DECIDED**; the current research
configuration names `structural` bias but does not define a complete entry rule from
that setting.

## 6. Entry model

**NOT YET DECIDED.** The specification must eventually choose and define, without
look-ahead:

- market entry at a causal confirmation point;
- limit entry on a defined FVG retracement; or
- another explicitly named model.

It must define the eligible price range, order timestamp, expiry, whether partial
fills are possible, spread/slippage assumptions, and the exact candle data required
to determine a fill. No entry model is implemented or implied here.

## 7. Stop-loss model

**NOT YET DECIDED.** Candidate alternatives such as beyond the swept liquidity level,
beyond the FVG, or an ATR/tick distance are research hypotheses only. The eventual
model must specify placement, tick rounding, spread treatment, and whether the stop
is set from the signal candle or the actual fill.

## 8. Take-profit model

**NOT YET DECIDED.** No target, risk/reward multiple, opposing liquidity objective,
fixed distance, trailing rule, or time-based exit is supported by the current source
material. The eventual model must define target selection and the priority when stop
and target are both touched in one candle.

## 9. Invalidation conditions

**VERIFIED FROM SOURCE:** A failed liquidity reclaim does not produce the existing
sweep event, and a candidate requires causal same-direction displacement and FVG
evidence within its configured association horizon.

The following strategy-level invalidations are **NOT YET DECIDED** and must be
specified before entry implementation:

- FVG fully mitigated or crossed before entry.
- Price invalidating the swept level after reclaim.
- Opposite-direction displacement or structure event.
- Window close before entry.
- Expiry of an unfilled order.
- Data gaps, duplicate timestamps, or ambiguous OHLC path during execution.

## 10. Maximum setup lifetime

**VERIFIED FROM SOURCE:** The current event association uses `next_n_bars` (default
3) as a detector-level horizon between sweep, displacement, and FVG. It does not
define how long a completed candidate remains tradable.

The maximum lifetime from sweep confirmation through FVG confirmation, from FVG
confirmation through entry, and from entry through exit is **NOT YET DECIDED**.
Each interval should be specified separately and in bars or elapsed UTC time. A
window close may or may not expire a candidate; that is also unresolved.

## 11. Parameters that should be configurable

The following should be explicit configuration or experiment parameters rather than
constants:

- setup, context, and execution timeframes;
- ordered session windows, names, enabled state, local times, and IANA timezones;
- window assignment timestamp and whether all events must remain in one window;
- swing left/right bars and causal confirmation mode;
- tick size and equal-level tolerance;
- eligible liquidity pool types;
- sweep penetration, reclaim rule, and reclaim horizon;
- ATR period, displacement body/range thresholds, tick floors, and optional close
  location/volume confirmation;
- minimum FVG gap size and any FVG mitigation definition;
- MSS/BOS enablement, event definition, and lookback if selected;
- event association horizon (`next_n_bars` or an explicitly chosen replacement);
- entry model, retracement level, order expiry, and fill assumptions;
- stop model and distance/rounding rules;
- target model, risk/reward or objective parameters, and exit priority;
- maximum setup lifetime, maximum trades per window, and duplicate-candidate policy;
- spread, slippage, commission, and ambiguous-bar handling for later execution
  research.

Existing defaults are research starting points only. They are not evidence that the
listed values are optimal.

## 12. Parameters that must not be optimized prematurely

Until a proper time-ordered validation/holdout experiment exists, do not optimize
any parameter against outcome performance, including:

- session start/end times or timezone selection;
- setup/context/execution timeframe choices;
- swing and liquidity tolerances;
- sweep penetration, reclaim horizon, and pool eligibility;
- ATR period and all displacement thresholds;
- FVG minimum gap and mitigation thresholds;
- event association horizon;
- MSS/BOS requirement or structural-bias rules;
- entry retracement, order expiry, and fill assumptions;
- stop placement, target distance, risk/reward, and exit timing;
- maximum setup lifetime, trade limits, and invalidation thresholds.

**VERIFIED FROM SOURCE:** The project has a protected holdout configuration and
explicitly rejects look-ahead by default. Any future parameter study must preserve
causal event timing, avoid holdout access during selection, and record the selected
specification before holdout evaluation.

## 13. Unresolved ambiguities

Before implementation, the project must resolve at least these questions:

1. What exact window or windows define the strategy, and are they genuinely
   confirmed or only configurable research hypotheses?
2. Which timezone governs each window, and how are DST-transition candles treated?
3. Does window membership use sweep confirmation, displacement, FVG confirmation, or
   require every event to fall within the same window?
4. Which setup, context, and execution timeframes are used?
5. Are singleton liquidity pools eligible, or only equal highs/lows?
6. Is a causal MSS/BOS required, and what exact event definition and confirmation
   delay apply?
7. Must displacement and FVG occur immediately after the sweep, or is the current
   `next_n_bars=3` horizon retained and applied once or separately?
8. Is the FVG itself the entry zone, and what retracement/market-entry rule applies?
9. What price constitutes an entry and how are spread, slippage, partial fills, and
   gaps modeled?
10. Where is the stop placed and how is it rounded?
11. How is profit taken, and what happens when stop and target are both touched in
    one candle?
12. What invalidates a setup before entry or after entry?
13. How long does an unfilled candidate remain valid, especially across a window
    close or midnight?
14. How are overlapping configured windows assigned if a candidate matches more than
    one?
15. What is the risk objective and what minimum sample size is required before any
    parameter comparison is credible?

Until these are answered, this document defines a causal research boundary and an
event vocabulary, not a complete executable trading strategy.