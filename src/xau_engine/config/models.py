from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProjectConfig(ConfigModel):
    symbol: str
    timezone: str
    broker_timezone: str = "Europe/Athens"
    tick_size: float = Field(gt=0)
    price_unit: str
    holdout_enabled: bool = False
    allow_lookahead: bool = False


class SessionWindow(ConfigModel):
    start: str
    end: str


class SessionConfig(ConfigModel):
    london: SessionWindow
    ny_am: SessionWindow
    ny_pm: SessionWindow
    timezone: str


class DataConfig(ConfigModel):
    timestamp_column: str
    open_column: str
    high_column: str
    low_column: str
    close_column: str
    volume_column: str
    bid_ask_available: bool = False
    default_data_path: str


class ResearchConfig(ConfigModel):
    atr_period: int = Field(gt=0)
    fvg_timeframe: str
    fvg_minimum_size_points: float = Field(ge=0)
    fvg_minimum_atr_multiple: float = Field(ge=0)
    sweep_k_bars: int = Field(gt=0)
    sweep_penetration_ticks: float = Field(ge=0)
    displacement_atr_multiple: float = Field(ge=0)
    mss_enabled: bool = False
    bias_definition: str
    entry_model: str
    stop_model: str
    target_model: str
    max_trades_per_window: int = Field(ge=1)

    @field_validator("bias_definition")
    @classmethod
    def normalize_bias_definition(cls, value: str) -> str:
        return value.strip().lower()

    @model_validator(mode="after")
    def reject_unapproved_lookahead(self, info: Any) -> "ResearchConfig":
        allow_lookahead = bool((info.context or {}).get("allow_lookahead", False))
        if self.bias_definition == "perfect" and not allow_lookahead:
            raise ValueError("bias_definition='perfect' requires allow_lookahead=true")
        return self


class ExecutionConfig(ConfigModel):
    spread_model: str
    slippage_ticks: float = Field(ge=0)
    commission: float | None = None
    tick_size: float = Field(gt=0)
    ambiguous_bar_rule: str


class HoldoutConfig(ConfigModel):
    cutoff_date: date
    enabled: bool = True
    access_override: bool = False
    explicit_override_required: bool = True

    @model_validator(mode="after")
    def require_explicit_override(self) -> "HoldoutConfig":
        if self.access_override and not self.explicit_override_required:
            raise ValueError("holdout access must require an explicit override")
        return self


class EngineConfig(ConfigModel):
    project: ProjectConfig
    session: SessionConfig
    data: DataConfig
    research: ResearchConfig
    execution: ExecutionConfig
    holdout: HoldoutConfig

    @model_validator(mode="after")
    def validate_cross_section_safety(self) -> "EngineConfig":
        if self.research.bias_definition == "perfect" and not self.project.allow_lookahead:
            raise ValueError("perfect bias requires project.allow_lookahead=true")
        return self