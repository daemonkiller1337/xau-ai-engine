import json
from pathlib import Path
from typing import Any

import yaml

from .models import EngineConfig, ProjectConfig, ResearchConfig


class ConfigError(ValueError):
    """Raised when a configuration file cannot be loaded or validated."""


def _read_mapping(path: Path) -> dict[str, Any]:
    try:
        with path.open(encoding="utf-8") as config_file:
            if path.suffix.lower() in {".yaml", ".yml"}:
                value = yaml.safe_load(config_file)
            elif path.suffix.lower() == ".json":
                value = json.load(config_file)
            else:
                raise ConfigError(f"unsupported configuration format: {path.suffix}")
    except (OSError, json.JSONDecodeError, yaml.YAMLError) as error:
        raise ConfigError(f"could not read configuration: {path}") from error
    if not isinstance(value, dict):
        raise ConfigError(f"configuration must contain a mapping: {path}")
    return value


def _merge_sections(*mappings: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for mapping in mappings:
        for section, values in mapping.items():
            if not isinstance(values, dict):
                raise ConfigError(f"configuration section must be a mapping: {section}")
            existing = merged.setdefault(section, {})
            if not isinstance(existing, dict):
                raise ConfigError(f"duplicate configuration section: {section}")
            existing.update(values)
    return merged


def load_config(base_path: str | Path, *additional_paths: str | Path) -> EngineConfig:
    """Load and validate a complete configuration from one or more files."""
    paths = [Path(base_path), *(Path(path) for path in additional_paths)]
    merged = _merge_sections(*(_read_mapping(path) for path in paths))
    try:
        project = ProjectConfig.model_validate(merged["project"])
        merged["research"] = ResearchConfig.model_validate(
            merged["research"], context={"allow_lookahead": project.allow_lookahead}
        )
        return EngineConfig.model_validate(merged)
    except (KeyError, TypeError, ValueError) as error:
        raise ConfigError("configuration validation failed") from error