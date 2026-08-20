from __future__ import annotations

import signal
import sys
import time
from collections.abc import Callable
from pathlib import Path

import pandas as pd

from xau_engine.features.displacement import detect_displacement
from xau_engine.features.fvg import detect_first_setup_candidates, detect_fvg
from xau_engine.features.liquidity import detect_liquidity_pools, detect_liquidity_sweeps
from xau_engine.features.market_structure import detect_swing_points

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "clean"
RESEARCH_DIR = DATA_DIR / "research"
TICK_SIZE = 0.01


class StageTimeout(RuntimeError):
    pass


def _alarm_handler(_signum: int, _frame: object) -> None:
    raise StageTimeout


def run_stage[T](name: str, function: Callable[[], T]) -> tuple[T, float]:
    print(f"{name}: started", flush=True)
    started = time.perf_counter()
    previous_handler = signal.signal(signal.SIGALRM, _alarm_handler)
    signal.setitimer(signal.ITIMER_REAL, 300)
    try:
        result = function()
    except StageTimeout as error:
        elapsed = time.perf_counter() - started
        print(f"{name}: STOPPED after {elapsed:.1f}s (over 5 minute limit)", flush=True)
        raise StageTimeout(name) from error
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
    elapsed = time.perf_counter() - started
    print(f"{name}: completed in {elapsed:.1f}s", flush=True)
    return result, elapsed


def write_events(timeframe: str, name: str, events: list[dict[str, object]]) -> None:
    pd.DataFrame(events).to_parquet(RESEARCH_DIR / f"{timeframe}_{name}.parquet", index=False)


def materialize_timeframe(timeframe: str) -> None:
    RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
    bars, _ = run_stage(
        f"{timeframe} loading",
        lambda: pd.read_parquet(DATA_DIR / f"GOLD_{timeframe}_XM.parquet"),
    )
    swings, _ = run_stage(
        f"{timeframe} swings",
        lambda: detect_swing_points(bars[["timestamp", "high", "low"]], timeframe, 2, 2),
    )
    write_events(timeframe, "swings", swings)

    liquidity, _ = run_stage(
        f"{timeframe} liquidity",
        lambda: detect_liquidity_pools(
            swings,
            timeframe=timeframe,
            tick_size=TICK_SIZE,
            equal_level_tolerance_ticks=1,
        ),
    )
    write_events(timeframe, "liquidity", liquidity)

    sweeps, _ = run_stage(
        f"{timeframe} sweeps",
        lambda: detect_liquidity_sweeps(
            bars[["timestamp", "high", "low", "close"]],
            liquidity,
            timeframe=timeframe,
            tick_size=TICK_SIZE,
            sweep_penetration_ticks=1,
            sweep_k_bars=5,
        ),
    )
    write_events(timeframe, "sweeps", sweeps)

    displacements, _ = run_stage(
        f"{timeframe} displacement",
        lambda: detect_displacement(
            bars,
            timeframe=timeframe,
            atr_period=14,
            min_body_atr_multiple=1.0,
            min_range_atr_multiple=1.5,
            tick_size=TICK_SIZE,
        ),
    )
    write_events(timeframe, "displacement", displacements)

    fvgs, _ = run_stage(
        f"{timeframe} FVG",
        lambda: detect_fvg(
            bars[["timestamp", "high", "low"]],
            timeframe=timeframe,
            tick_size=TICK_SIZE,
            minimum_gap_ticks=1,
        ),
    )
    write_events(timeframe, "fvg", fvgs)

    persisted_fvgs = pd.read_parquet(RESEARCH_DIR / f"{timeframe}_fvg.parquet").to_dict("records")
    candidates, _ = run_stage(
        f"{timeframe} candidate composition",
        lambda: detect_first_setup_candidates(
            bars[["timestamp", "high", "low"]],
            pd.read_parquet(RESEARCH_DIR / f"{timeframe}_sweeps.parquet").to_dict("records"),
            pd.read_parquet(RESEARCH_DIR / f"{timeframe}_displacement.parquet").to_dict("records"),
            timeframe=timeframe,
            next_n_bars=3,
            tick_size=TICK_SIZE,
            minimum_gap_ticks=1,
            fvg_events=persisted_fvgs,
        ),
    )
    write_events(timeframe, "candidates", candidates)
    print(
        f"{timeframe} counts: swings={len(swings)} liquidity={len(liquidity)} "
        f"sweeps={len(sweeps)} displacement={len(displacements)} FVG={len(fvgs)} "
        f"candidates={len(candidates)}",
        flush=True,
    )


def main() -> int:
    for timeframe in ("M5", "M15"):
        try:
            materialize_timeframe(timeframe)
        except StageTimeout as error:
            print(f"Bottleneck: {error.args[0]}", file=sys.stderr, flush=True)
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
