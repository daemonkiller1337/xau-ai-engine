from pathlib import Path

import pytest
from pydantic import ValidationError

from xau_engine.config import (
    EngineConfig,
    ExecutionConfig,
    ProjectConfig,
    ResearchConfig,
    load_config,
)

ROOT = Path(__file__).parents[1]
BASE_CONFIG = ROOT / "configs" / "base.yaml"
RESEARCH_CONFIG = ROOT / "configs" / "research.yaml"
HOLDOUT_CONFIG = ROOT / "configs" / "holdout.yaml"


def test_configuration_loads_successfully() -> None:
    config = load_config(BASE_CONFIG, RESEARCH_CONFIG, HOLDOUT_CONFIG)

    assert config.project.symbol == "XAUUSD"
    assert config.project.broker_timezone == "Europe/Athens"


def test_invalid_tick_size_fails() -> None:
    with pytest.raises(ValidationError):
        ProjectConfig(
            symbol="XAUUSD",
            timezone="UTC",
            broker_timezone="Europe/Athens",
            tick_size=0,
            price_unit="points",
        )


def test_negative_slippage_fails() -> None:
    with pytest.raises(ValidationError):
        ExecutionConfig(
            spread_model="placeholder",
            slippage_ticks=-1,
            tick_size=0.01,
            ambiguous_bar_rule="reject",
        )


def test_invalid_atr_period_fails() -> None:
    with pytest.raises(ValidationError):
        ResearchConfig(
            atr_period=0,
            fvg_timeframe="5m",
            fvg_minimum_size_points=1,
            fvg_minimum_atr_multiple=0.5,
            sweep_k_bars=5,
            sweep_penetration_ticks=0,
            displacement_atr_multiple=1,
            bias_definition="structural",
            entry_model="placeholder",
            stop_model="placeholder",
            target_model="placeholder",
            max_trades_per_window=1,
        )


def test_holdout_defaults_to_protected() -> None:
    config = load_config(BASE_CONFIG, RESEARCH_CONFIG, HOLDOUT_CONFIG)

    assert config.holdout.enabled is True
    assert config.holdout.access_override is False
    assert config.holdout.explicit_override_required is True


def test_lookahead_defaults_to_false() -> None:
    assert (
        ProjectConfig(
            symbol="XAUUSD",
            timezone="UTC",
            broker_timezone="Europe/Athens",
            tick_size=0.01,
            price_unit="points",
        ).allow_lookahead is False
    )


def test_perfect_bias_is_rejected_when_lookahead_is_false() -> None:
    with pytest.raises(ValidationError):
        ResearchConfig(
            atr_period=14,
            fvg_timeframe="5m",
            fvg_minimum_size_points=1,
            fvg_minimum_atr_multiple=0.5,
            sweep_k_bars=5,
            sweep_penetration_ticks=0,
            displacement_atr_multiple=1,
            bias_definition="perfect",
            entry_model="placeholder",
            stop_model="placeholder",
            target_model="placeholder",
            max_trades_per_window=1,
        )


def test_perfect_bias_requires_explicit_lookahead_enablement() -> None:
    research = {
        "atr_period": 14,
        "fvg_timeframe": "5m",
        "fvg_minimum_size_points": 1,
        "fvg_minimum_atr_multiple": 0.5,
        "sweep_k_bars": 5,
        "sweep_penetration_ticks": 0,
        "displacement_atr_multiple": 1,
        "bias_definition": "perfect",
        "entry_model": "placeholder",
        "stop_model": "placeholder",
        "target_model": "placeholder",
        "max_trades_per_window": 1,
    }

    with pytest.raises(ValidationError):
        ResearchConfig.model_validate(research)
    assert ResearchConfig.model_validate(research, context={"allow_lookahead": True}).bias_definition == "perfect"


def test_configuration_contains_no_percentage_price_threshold_fields() -> None:
    field_names = set(EngineConfig.model_fields)
    for model in (ProjectConfig, ResearchConfig, ExecutionConfig):
        field_names.update(model.model_fields)

    assert not any(
        "percent" in name or "percentage" in name or "price_ratio" in name for name in field_names
    )