from __future__ import annotations

import pandas as pd
import polars as pl

from bcra_pagos_minoristas_xlsx_to_parquet.models import ParsedDataset, ParsingMetadata
from bcra_pagos_minoristas_xlsx_to_parquet.normalization import normalize_dataset


def test_normalization_snake_case_and_uniqueness() -> None:
    df = pd.DataFrame([[1, 2]], columns=["Crédito Total", "Crédito Total"])
    metadata = ParsingMetadata(
        sheet_names=["sheet"],
        row_counts={"sheet": 1},
        column_counts={"sheet": 2},
        inferred_types={"sheet": {"Crédito Total": "int64"}},
        header_row_index={"sheet": 0},
    )
    parsed = ParsedDataset(sheets={"sheet": df}, metadata=metadata)

    normalized = normalize_dataset(parsed)
    columns = list(normalized.sheets["sheet"].columns)

    assert columns[0] == "credito_total"
    assert columns[1] == "credito_total_2"


def test_normalization_adds_month_start_fecha_and_keeps_original() -> None:
    df = pd.DataFrame(
        {
            "Fecha": [
                pd.Timestamp("2024-05-17"),
                pd.Timestamp("2024-05-31"),
                pd.NaT,
            ],
            "Valor": [10, 20, None],
        }
    )
    metadata = ParsingMetadata(
        sheet_names=["sheet"],
        row_counts={"sheet": 3},
        column_counts={"sheet": 2},
        inferred_types={"sheet": {"Fecha": "datetime"}},
        header_row_index={"sheet": 0},
    )
    parsed = ParsedDataset(sheets={"sheet": df}, metadata=metadata)

    normalized = normalize_dataset(parsed)
    result = normalized.sheets["sheet"]

    assert list(result.columns) == ["fecha_original", "valor", "fecha"]
    assert result["fecha_original"].iloc[0] == pd.Timestamp("2024-05-17")
    assert result["fecha"].iloc[0] == pd.Timestamp("2024-05-01")
    assert result["fecha_original"].iloc[1] == pd.Timestamp("2024-05-31")
    assert result["fecha"].iloc[1] == pd.Timestamp("2024-05-01")
    assert len(result) == 2
    assert normalized.dropped_rows["sheet"] == 1


def test_normalization_applies_aliases() -> None:
    df = pl.DataFrame({"Fecha Movimiento": [pd.Timestamp("2024-01-01")]})
    metadata = ParsingMetadata(
        sheet_names=["sheet"],
        row_counts={"sheet": 1},
        column_counts={"sheet": 1},
        inferred_types={"sheet": {"Fecha Movimiento": "datetime"}},
        header_row_index={"sheet": 0},
    )
    parsed = ParsedDataset(sheets={"sheet": df}, metadata=metadata)

    normalized = normalize_dataset(parsed, aliases={"fecha": ["Fecha Movimiento"]})

    assert list(normalized.sheets["sheet"].columns) == ["fecha_original", "fecha"]
    assert normalized.schema_report["sheet"]["aliases_used"] == [
        {"source": "Fecha Movimiento", "canonical": "fecha"}
    ]
    assert normalized.sheets["sheet"]["fecha_original"][0] == pd.Timestamp("2024-01-01")
    assert normalized.sheets["sheet"]["fecha"][0] == pd.Timestamp("2024-01-01")


def test_normalization_drops_trailing_blank_rows_without_fecha() -> None:
    df = pl.DataFrame(
        {
            "concepto": ["pago", None],
            "monto": [100, None],
        }
    )
    metadata = ParsingMetadata(
        sheet_names=["sheet"],
        row_counts={"sheet": 2},
        column_counts={"sheet": 2},
        inferred_types={"sheet": {"concepto": "str", "monto": "int64"}},
        header_row_index={"sheet": 0},
    )
    parsed = ParsedDataset(sheets={"sheet": df}, metadata=metadata)

    normalized = normalize_dataset(parsed)
    result = normalized.sheets["sheet"]

    assert list(result.columns) == ["concepto", "monto"]
    assert len(result) == 1
    assert normalized.dropped_rows["sheet"] == 1
