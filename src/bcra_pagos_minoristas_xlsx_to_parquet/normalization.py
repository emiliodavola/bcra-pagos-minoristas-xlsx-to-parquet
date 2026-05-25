from __future__ import annotations

import hashlib
import json
import re
from typing import Any

import pandas as pd
import polars as pl

from .logging_utils import get_logger, log_event
from .models import NormalizedDataset, ParsedDataset

_LOGGER = get_logger(__name__)


def normalize_dataset(
    parsed: ParsedDataset,
    *,
    aliases: dict[str, list[str]] | None = None,
) -> NormalizedDataset:
    normalized_sheets: dict[str, Any] = {}
    schema: dict[str, dict[str, str]] = {}
    column_mapping: dict[str, dict[str, str]] = {}
    row_counts: dict[str, int] = {}
    dropped_rows: dict[str, int] = {}
    schema_report: dict[str, dict[str, Any]] = {}

    for sheet, dataframe in parsed.sheets.items():
        if isinstance(dataframe, pl.DataFrame):
            normalized, mapping, report = _normalize_polars(dataframe, aliases=aliases)
            schema[sheet] = {k: str(v) for k, v in normalized.schema.items()}
        elif isinstance(dataframe, pd.DataFrame):
            normalized, mapping, report = _normalize_pandas(dataframe, aliases=aliases)
            schema[sheet] = {k: str(v) for k, v in normalized.dtypes.items()}
        else:
            raise ValueError("Unsupported dataframe type for normalization.")

        normalized_sheets[sheet] = normalized
        column_mapping[sheet] = mapping
        row_counts[sheet] = len(normalized)
        dropped_rows[sheet] = 0
        schema_report[sheet] = report

    result = NormalizedDataset(
        sheets=normalized_sheets,
        schema=schema,
        column_mapping=column_mapping,
        row_counts=row_counts,
        dropped_rows=dropped_rows,
        schema_report=schema_report,
    )
    log_event(_LOGGER, "normalization.completed", sheet_count=len(normalized_sheets))
    return result


def _normalize_pandas(
    df: pd.DataFrame,
    *,
    aliases: dict[str, list[str]] | None = None,
) -> tuple[pd.DataFrame, dict[str, str], dict[str, Any]]:
    new_columns, mapping, report = _build_column_mapping(
        list(df.columns), aliases=aliases
    )
    renamed = df.copy()
    renamed.columns = new_columns
    renamed = renamed.convert_dtypes()

    for column in renamed.columns:
        if pd.api.types.is_datetime64_any_dtype(renamed[column]):
            renamed[column] = _normalize_datetime_series(renamed[column])
        if pd.api.types.is_numeric_dtype(renamed[column]):
            renamed[column] = pd.to_numeric(renamed[column], errors="coerce")

    renamed = _add_period_boundary_pandas(renamed)
    renamed = renamed.where(pd.notna(renamed), None)
    report["schema"] = {k: str(v) for k, v in renamed.dtypes.items()}
    return renamed, mapping, report


def _normalize_polars(
    df: pl.DataFrame,
    *,
    aliases: dict[str, list[str]] | None = None,
) -> tuple[pl.DataFrame, dict[str, str], dict[str, Any]]:
    new_columns, mapping, report = _build_column_mapping(df.columns, aliases=aliases)
    renamed = df.clone()
    renamed.columns = new_columns
    for column, dtype in renamed.schema.items():
        if dtype == pl.Datetime:
            renamed = renamed.with_columns(pl.col(column).dt.replace_time_zone("UTC"))
        if dtype == pl.Date:
            renamed = renamed.with_columns(pl.col(column).cast(pl.Datetime))
    renamed = _add_period_boundary_polars(renamed)
    report["schema"] = {k: str(v) for k, v in renamed.schema.items()}
    return renamed, mapping, report


def _normalize_datetime_series(series: pd.Series) -> pd.Series:
    if series.dt.tz is None:
        return series.dt.tz_localize("UTC")
    return series.dt.tz_convert("UTC")


def _add_period_boundary_pandas(df: pd.DataFrame) -> pd.DataFrame:
    if "fecha" not in df.columns or "period_boundary" in df.columns:
        return df
    series = df["fecha"]
    if not pd.api.types.is_datetime64_any_dtype(series):
        series = pd.to_datetime(series, errors="coerce")
        df = df.copy()
        df["fecha"] = series
    if series.isna().all():
        return df
    boundary = pd.Series(pd.NA, index=series.index, dtype="string")
    boundary[series.dt.is_month_start] = "MS"
    boundary[series.dt.is_month_end] = "ME"
    df["period_boundary"] = boundary
    return df


def _add_period_boundary_polars(df: pl.DataFrame) -> pl.DataFrame:
    if "fecha" not in df.columns or "period_boundary" in df.columns:
        return df
    df = _ensure_polars_fecha_datetime(df)
    fecha = pl.col("fecha")
    boundary = (
        pl.when(fecha.is_null())
        .then(None)
        .when(fecha.dt.month_start() == fecha)
        .then(pl.lit("MS"))
        .when(fecha.dt.month_end() == fecha)
        .then(pl.lit("ME"))
        .otherwise(None)
        .alias("period_boundary")
    )
    return df.with_columns(boundary)


def _ensure_polars_fecha_datetime(df: pl.DataFrame) -> pl.DataFrame:
    dtype = df.schema.get("fecha")
    if dtype is None:
        return df
    if dtype == pl.Datetime:
        return df
    if dtype == pl.Date:
        return df.with_columns(pl.col("fecha").cast(pl.Datetime))
    if dtype == pl.Utf8:
        return df.with_columns(
            pl.col("fecha").str.strptime(pl.Datetime, strict=False).alias("fecha")
        )
    return df


def _build_column_mapping(
    columns: list[str],
    *,
    aliases: dict[str, list[str]] | None = None,
) -> tuple[list[str], dict[str, str], dict[str, Any]]:
    alias_lookup = _build_alias_lookup(aliases or {})
    normalized = [_snake_case(str(name)) for name in columns]
    resolved: list[str] = []
    aliases_used: list[dict[str, str]] = []
    for original_name, normalized_name in zip(columns, normalized):
        canonical = alias_lookup.get(normalized_name, normalized_name)
        resolved.append(canonical)
        if canonical != normalized_name:
            aliases_used.append({"source": str(original_name), "canonical": canonical})
    unique = _ensure_unique(resolved)
    mapping: dict[str, str] = {}
    counts: dict[str, int] = {}
    for original, new_name in zip(columns, unique):
        count = counts.get(original, 0) + 1
        counts[original] = count
        key = original if count == 1 else f"{original}__{count}"
        mapping[key] = new_name
    report = {
        "raw_columns": [str(name) for name in columns],
        "normalized_columns": normalized,
        "canonical_columns": resolved,
        "aliases_used": aliases_used,
        "schema_fingerprint": _schema_fingerprint(unique),
    }
    return unique, mapping, report


def _build_alias_lookup(aliases: dict[str, list[str]]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for canonical, values in aliases.items():
        canonical_name = _snake_case(canonical)
        lookup[canonical_name] = canonical_name
        for alias in values:
            lookup[_snake_case(alias)] = canonical_name
    return lookup


def _schema_fingerprint(columns: list[str]) -> str:
    payload = json.dumps(columns, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


def _snake_case(name: str) -> str:
    value = re.sub(r"[^A-Za-z0-9]+", "_", name.strip().lower())
    value = re.sub(r"_+", "_", value).strip("_")
    return value or "column"


def _ensure_unique(values: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    result: list[str] = []
    for value in values:
        count = seen.get(value, 0) + 1
        seen[value] = count
        if count == 1:
            result.append(value)
        else:
            result.append(f"{value}_{count}")
    return result
