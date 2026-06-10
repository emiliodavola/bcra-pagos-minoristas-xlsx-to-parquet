from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from typing import Any

import pandas as pd
import polars as pl

from .logging_utils import get_logger, log_event
from .utils import is_blank
from .models import NormalizedDataset, ParsedDataset

_LOGGER = get_logger(__name__)
_DATE_SOURCE_COLUMN = "fecha"
_DATE_ORIGINAL_COLUMN = "fecha_original"


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
            normalized, mapping, report, dropped = _normalize_polars(
                dataframe, aliases=aliases
            )
            schema[sheet] = {k: str(v) for k, v in normalized.schema.items()}
        elif isinstance(dataframe, pd.DataFrame):
            normalized, mapping, report, dropped = _normalize_pandas(
                dataframe, aliases=aliases
            )
            schema[sheet] = {k: str(v) for k, v in normalized.dtypes.items()}
        else:
            raise ValueError("Unsupported dataframe type for normalization.")

        normalized_sheets[sheet] = normalized
        column_mapping[sheet] = mapping
        row_counts[sheet] = len(normalized)
        dropped_rows[sheet] = dropped
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
) -> tuple[pd.DataFrame, dict[str, str], dict[str, Any], int]:
    new_columns, mapping, report = _build_column_mapping(
        list(df.columns), aliases=aliases
    )
    renamed = df.copy()
    renamed.columns = new_columns
    renamed = renamed.convert_dtypes()
    renamed = renamed.replace(r"^\s*$", pd.NA, regex=True)
    renamed, dropped_rows = _drop_trailing_blank_rows_pandas(renamed)

    renamed, mapping = _normalize_fecha_pandas(renamed, mapping)
    report["schema"] = {k: str(v) for k, v in renamed.dtypes.items()}
    report["date_columns"] = {
        "source": (
            _DATE_SOURCE_COLUMN if _DATE_SOURCE_COLUMN in renamed.columns else None
        ),
        "original": (
            _DATE_ORIGINAL_COLUMN if _DATE_ORIGINAL_COLUMN in renamed.columns else None
        ),
    }
    report["dropped_trailing_rows"] = dropped_rows
    return renamed, mapping, report, dropped_rows


def _normalize_polars(
    df: pl.DataFrame,
    *,
    aliases: dict[str, list[str]] | None = None,
) -> tuple[pl.DataFrame, dict[str, str], dict[str, Any], int]:
    new_columns, mapping, report = _build_column_mapping(df.columns, aliases=aliases)
    renamed = df.clone()
    renamed.columns = new_columns
    renamed, dropped_rows = _drop_trailing_blank_rows_polars(renamed)
    renamed, mapping = _normalize_fecha_polars(renamed, mapping)
    report["schema"] = {k: str(v) for k, v in renamed.schema.items()}
    report["date_columns"] = {
        "source": (
            _DATE_SOURCE_COLUMN if _DATE_SOURCE_COLUMN in renamed.columns else None
        ),
        "original": (
            _DATE_ORIGINAL_COLUMN if _DATE_ORIGINAL_COLUMN in renamed.columns else None
        ),
    }
    report["dropped_trailing_rows"] = dropped_rows
    return renamed, mapping, report, dropped_rows


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
    normalized = unicodedata.normalize("NFKD", name)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^A-Za-z0-9]+", "_", ascii_text.strip().lower())
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


def _normalize_fecha_pandas(
    df: pd.DataFrame, mapping: dict[str, str]
) -> tuple[pd.DataFrame, dict[str, str]]:
    if (
        _DATE_SOURCE_COLUMN not in df.columns
        and _DATE_ORIGINAL_COLUMN not in df.columns
    ):
        return df, mapping
    if _DATE_SOURCE_COLUMN in df.columns and _DATE_ORIGINAL_COLUMN in df.columns:
        raise ValueError(
            "Ambiguous date columns: fecha and fecha_original already exist."
        )

    frame = df.copy()
    if _DATE_SOURCE_COLUMN in frame.columns:
        frame = frame.rename(columns={_DATE_SOURCE_COLUMN: _DATE_ORIGINAL_COLUMN})
        mapping = {
            raw: (
                _DATE_ORIGINAL_COLUMN
                if normalized == _DATE_SOURCE_COLUMN
                else normalized
            )
            for raw, normalized in mapping.items()
        }

    original = pd.to_datetime(frame[_DATE_ORIGINAL_COLUMN], errors="coerce", utc=True)
    original = original.dt.tz_convert(None)
    frame[_DATE_ORIGINAL_COLUMN] = original
    frame[_DATE_SOURCE_COLUMN] = original.dt.to_period("M").dt.to_timestamp()
    mapping.setdefault(_DATE_SOURCE_COLUMN, _DATE_SOURCE_COLUMN)
    if _DATE_ORIGINAL_COLUMN not in mapping.values():
        mapping[_DATE_ORIGINAL_COLUMN] = _DATE_ORIGINAL_COLUMN
    return frame, mapping


def _normalize_fecha_polars(
    df: pl.DataFrame, mapping: dict[str, str]
) -> tuple[pl.DataFrame, dict[str, str]]:
    if (
        _DATE_SOURCE_COLUMN not in df.columns
        and _DATE_ORIGINAL_COLUMN not in df.columns
    ):
        return df, mapping
    if _DATE_SOURCE_COLUMN in df.columns and _DATE_ORIGINAL_COLUMN in df.columns:
        raise ValueError(
            "Ambiguous date columns: fecha and fecha_original already exist."
        )

    frame = df.clone()
    if _DATE_SOURCE_COLUMN in frame.columns:
        frame = frame.rename({_DATE_SOURCE_COLUMN: _DATE_ORIGINAL_COLUMN})
        mapping = {
            raw: (
                _DATE_ORIGINAL_COLUMN
                if normalized == _DATE_SOURCE_COLUMN
                else normalized
            )
            for raw, normalized in mapping.items()
        }

    frame = _ensure_polars_datetime(frame, _DATE_ORIGINAL_COLUMN)
    frame = frame.with_columns(
        pl.col(_DATE_ORIGINAL_COLUMN).dt.truncate("1mo").alias(_DATE_SOURCE_COLUMN)
    )
    mapping.setdefault(_DATE_SOURCE_COLUMN, _DATE_SOURCE_COLUMN)
    if _DATE_ORIGINAL_COLUMN not in mapping.values():
        mapping[_DATE_ORIGINAL_COLUMN] = _DATE_ORIGINAL_COLUMN
    return frame, mapping


def _ensure_polars_datetime(df: pl.DataFrame, column: str) -> pl.DataFrame:
    dtype = df.schema.get(column)
    if dtype is None:
        return df
    if dtype == pl.Datetime:
        return df
    if dtype == pl.Date:
        return df.with_columns(pl.col(column).cast(pl.Datetime).alias(column))
    if dtype == pl.Utf8:
        return df.with_columns(
            pl.col(column).str.strptime(pl.Datetime, strict=False).alias(column)
        )
    return df.with_columns(pl.col(column).cast(pl.Datetime, strict=False).alias(column))


def _drop_trailing_blank_rows_pandas(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    if df.empty:
        return df, 0
    trimmed = df.copy()
    dropped = 0
    while not trimmed.empty and _row_is_blank_pandas(trimmed.iloc[-1]):
        trimmed = trimmed.iloc[:-1].copy()
        dropped += 1
    return trimmed, dropped


def _drop_trailing_blank_rows_polars(df: pl.DataFrame) -> tuple[pl.DataFrame, int]:
    if df.is_empty():
        return df, 0
    trimmed = df.clone()
    dropped = 0
    while not trimmed.is_empty() and _row_is_blank_polars(trimmed.row(-1, named=True)):
        trimmed = trimmed.head(trimmed.height - 1)
        dropped += 1
    return trimmed, dropped


def _row_is_blank_pandas(row: pd.Series) -> bool:
    for _, value in row.items():
        if not is_blank(value):
            return False
    return True


def _row_is_blank_polars(row: dict[str, Any]) -> bool:
    for value in row.values():
        if not is_blank(value):
            return False
    return True
