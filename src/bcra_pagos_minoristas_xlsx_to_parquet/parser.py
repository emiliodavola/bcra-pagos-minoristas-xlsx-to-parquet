from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any, Literal

import pandas as pd
import polars as pl
import pyarrow as pa

from .logging_utils import get_logger, log_event
from .models import ParsedDataset, ParsingMetadata
from .utils import is_blank

_LOGGER = get_logger(__name__)


def parse_workbook(
    path: Path,
    *,
    engine: Literal["polars", "pandas"] = "polars",
    sheet_names: list[str] | None = None,
) -> ParsedDataset:
    excel = pd.ExcelFile(path)
    target_sheets = sheet_names or excel.sheet_names

    sheets: dict[str, pl.DataFrame | pd.DataFrame] = {}
    row_counts: dict[str, int] = {}
    column_counts: dict[str, int] = {}
    inferred_types: dict[str, dict[str, str]] = {}
    header_row_index: dict[str, int] = {}

    for sheet in target_sheets:
        raw = pd.read_excel(excel, sheet_name=sheet, header=None, dtype=object)
        header_idx = _find_header_row(raw)
        header_row_index[sheet] = header_idx
        headers, data_start = _extract_headers(raw, header_idx)
        headers = _ensure_unique_headers(headers)
        data = raw.iloc[data_start:].copy()
        data.columns = headers
        for column in data.columns:
            if data[column].dtype == object:
                data[column] = data[column].map(_blank_string_to_na)
        data = data.infer_objects(copy=False)
        data, _ = _drop_trailing_sparse_rows(data)
        data = data.dropna(axis=1, how="all")
        data = data.dropna(how="all")
        data = data.reset_index(drop=True)

        if engine == "polars":
            dataframe = _to_polars(data)
            inferred_types[sheet] = {k: str(v) for k, v in dataframe.schema.items()}
        elif engine == "pandas":
            dataframe = data
            inferred_types[sheet] = {k: str(v) for k, v in dataframe.dtypes.items()}
        else:
            raise ValueError(f"Unsupported parser engine: {engine}")

        sheets[sheet] = dataframe
        row_counts[sheet] = len(dataframe)
        column_counts[sheet] = len(dataframe.columns)

    metadata = ParsingMetadata(
        sheet_names=list(sheets.keys()),
        row_counts=row_counts,
        column_counts=column_counts,
        inferred_types=inferred_types,
        header_row_index=header_row_index,
    )
    log_event(
        _LOGGER,
        "parser.completed",
        path=str(path),
        engine=engine,
        sheet_count=len(sheets),
    )
    return ParsedDataset(sheets=sheets, metadata=metadata)


def _find_header_row(df: pd.DataFrame) -> int:
    for index, row in df.iterrows():
        non_empty = row.dropna()
        if not non_empty.empty:
            return int(index)
    return 0


def _extract_headers(raw: pd.DataFrame, header_idx: int) -> tuple[list[str], int]:
    header_rows: list[pd.Series] = []
    max_depth = 3
    for offset in range(max_depth):
        row_index = header_idx + offset
        if row_index >= len(raw):
            break
        row = raw.iloc[row_index]
        if offset == 0:
            header_rows.append(row)
            continue
        if _row_is_header(row):
            header_rows.append(row)
        else:
            break

    headers = _build_combined_headers(header_rows)
    return headers, header_idx + len(header_rows)


def _row_is_header(row: pd.Series) -> bool:
    values = [
        value
        for value in row.tolist()
        if value is not None and not (isinstance(value, float) and pd.isna(value))
    ]
    if not values:
        return False
    return not any(_is_data_like_value(value) for value in values)


def _build_combined_headers(rows: list[pd.Series]) -> list[str]:
    if not rows:
        return []
    filled_rows: list[list[str | None]] = []
    for row in rows:
        filled: list[str | None] = []
        last_value: str | None = None
        for cell in row.tolist():
            value = _normalize_header_cell(cell)
            if value:
                last_value = value
            filled.append(last_value)
        filled_rows.append(filled)

    column_count = max(len(row) for row in filled_rows)
    headers: list[str] = []
    for idx in range(column_count):
        parts: list[str] = []
        for row in filled_rows:
            if idx >= len(row):
                continue
            part = row[idx]
            if part and (not parts or part != parts[-1]):
                parts.append(part)
        if parts:
            headers.append(" ".join(parts))
        else:
            headers.append(f"column_{idx}")
    return headers


def _ensure_unique_headers(headers: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    unique: list[str] = []
    for header in headers:
        count = seen.get(header, 0) + 1
        seen[header] = count
        if count == 1:
            unique.append(header)
        else:
            unique.append(f"{header}_{count}")
    return unique


def _normalize_header_cell(value: object) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    return text or None


def _blank_string_to_na(value: object) -> object:
    if isinstance(value, str) and not value.strip():
        return pd.NA
    return value


def _drop_trailing_sparse_rows(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    if df.empty:
        return df, 0
    trimmed = df.copy()
    dropped = 0
    while not trimmed.empty and _row_is_sparse_noise(trimmed.iloc[-1]):
        trimmed = trimmed.iloc[:-1].copy()
        dropped += 1
    return trimmed, dropped


def _to_polars(data: pd.DataFrame) -> pl.DataFrame:
    try:
        return pl.from_pandas(data, include_index=False)
    except (pa.ArrowTypeError, TypeError, ValueError):
        coerced = _coerce_object_columns(data)
        try:
            return pl.from_pandas(coerced, include_index=False)
        except Exception as exc:  # pragma: no cover - fallback protection
            raise ValueError(
                "Unable to convert sheet to Polars. Try parser.engine = 'pandas'."
            ) from exc


def _coerce_object_columns(data: pd.DataFrame) -> pd.DataFrame:
    coerced = data.copy()
    for idx, _ in enumerate(coerced.columns):
        series = coerced.iloc[:, idx]
        if series.dtype != object:
            continue
        coerced.iloc[:, idx] = _coerce_object_series(series)
    return coerced


def _coerce_object_series(series: pd.Series) -> pd.Series:
    non_null = series.dropna()
    if non_null.empty:
        return series
    if all(isinstance(value, (datetime, date, pd.Timestamp)) for value in non_null):
        return pd.to_datetime(series, errors="coerce")
    if all(isinstance(value, (int, float, bool)) for value in non_null):
        return pd.to_numeric(series, errors="coerce")
    if all(isinstance(value, str) for value in non_null):
        return series
    return series.map(_stringify_value)


def _stringify_value(value: object) -> str | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def _row_is_sparse_noise(row: pd.Series) -> bool:
    non_empty = [value for value in row.tolist() if not is_blank(value)]
    return len(non_empty) <= 1


def _is_data_like_value(value: Any) -> bool:
    if isinstance(value, (datetime, date, pd.Timestamp)):
        return True
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return True
    return False
