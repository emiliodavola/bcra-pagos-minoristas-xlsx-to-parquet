from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - python<3.11
    import tomli as tomllib


class SourceConfig(BaseModel):
    url: str = "https://www.bcra.gob.ar"
    match_rules: list[str] = Field(default_factory=lambda: [r"\.xlsx$"])
    mode: Literal["latest", "all"] = "latest"


class DownloadConfig(BaseModel):
    output_dir: Path = Path("data/raw")
    retries: int = 3
    timeout_seconds: int = 30


class ParserConfig(BaseModel):
    engine: str = "polars"


class NormalizationConfig(BaseModel):
    aliases: dict[str, list[str]] = Field(default_factory=dict)


class StorageConfig(BaseModel):
    format: str = "parquet"
    output_dir: Path = Path("data/curated")
    partition_by: list[str] = Field(default_factory=list)
    mode: str = "append"


class AppConfig(BaseModel):
    source: SourceConfig = Field(default_factory=SourceConfig)
    download: DownloadConfig = Field(default_factory=DownloadConfig)
    parser: ParserConfig = Field(default_factory=ParserConfig)
    normalization: NormalizationConfig = Field(default_factory=NormalizationConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)


def load_config(path: Path | None = None) -> AppConfig:
    config_path = path or Path("bcra.toml")
    data: dict[str, Any] = {}
    if config_path.exists():
        data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    data = _deep_merge(data, _env_overrides())
    return AppConfig.model_validate(data)


def _env_overrides(prefix: str = "BCRA__") -> dict[str, Any]:
    overrides: dict[str, Any] = {}
    for key, value in os.environ.items():
        if not key.startswith(prefix):
            continue
        path = key[len(prefix) :].lower().split("__")
        if not path:
            continue
        cursor = overrides
        for segment in path[:-1]:
            cursor = cursor.setdefault(segment, {})
        cursor[path[-1]] = _coerce_env_value(value)
    return overrides


def _coerce_env_value(value: str) -> Any:
    lowered = value.strip().lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if lowered.isdigit():
        return int(lowered)
    return value


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged
