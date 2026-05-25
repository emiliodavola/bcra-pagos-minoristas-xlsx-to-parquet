import pandas as pd

from bcra_pagos_minoristas_xlsx_to_parquet.models import ParsedDataset, ParsingMetadata
from bcra_pagos_minoristas_xlsx_to_parquet.normalization import normalize_dataset


def test_normalization_snake_case_and_uniqueness() -> None:
    df = pd.DataFrame([[1, 2]], columns=["Total %", "Total %"])
    metadata = ParsingMetadata(
        sheet_names=["sheet"],
        row_counts={"sheet": 1},
        column_counts={"sheet": 2},
        inferred_types={"sheet": {"Total %": "int64"}},
        header_row_index={"sheet": 0},
    )
    parsed = ParsedDataset(sheets={"sheet": df}, metadata=metadata)

    normalized = normalize_dataset(parsed)
    columns = list(normalized.sheets["sheet"].columns)

    assert columns[0] == "total"
    assert columns[1] == "total_2"


def test_normalization_adds_period_boundary() -> None:
    df = pd.DataFrame(
        {"Fecha": [pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-31"), pd.NaT]}
    )
    metadata = ParsingMetadata(
        sheet_names=["sheet"],
        row_counts={"sheet": 3},
        column_counts={"sheet": 1},
        inferred_types={"sheet": {"Fecha": "datetime"}},
        header_row_index={"sheet": 0},
    )
    parsed = ParsedDataset(sheets={"sheet": df}, metadata=metadata)

    normalized = normalize_dataset(parsed)
    result = normalized.sheets["sheet"]

    assert "period_boundary" in result.columns
    assert result["period_boundary"].iloc[0] == "MS"
    assert result["period_boundary"].iloc[1] == "ME"
    assert pd.isna(result["period_boundary"].iloc[2])


def test_normalization_applies_aliases() -> None:
    df = pd.DataFrame({"Fecha Movimiento": [pd.Timestamp("2024-01-01")]})
    metadata = ParsingMetadata(
        sheet_names=["sheet"],
        row_counts={"sheet": 1},
        column_counts={"sheet": 1},
        inferred_types={"sheet": {"Fecha Movimiento": "datetime"}},
        header_row_index={"sheet": 0},
    )
    parsed = ParsedDataset(sheets={"sheet": df}, metadata=metadata)

    normalized = normalize_dataset(parsed, aliases={"fecha": ["Fecha Movimiento"]})

    assert list(normalized.sheets["sheet"].columns)[0] == "fecha"
    assert normalized.schema_report["sheet"]["aliases_used"] == [
        {"source": "Fecha Movimiento", "canonical": "fecha"}
    ]
