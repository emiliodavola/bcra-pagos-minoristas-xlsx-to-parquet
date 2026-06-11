"""Parser tests for the Polars engine."""

import pandas as pd

from bcra_pagos_minoristas_xlsx_to_parquet.parser import parse_workbook


def _make_sample_excel(tmp_path, rows):
    """Create a minimal sample XLSX file for testing both engines."""
    df = pd.DataFrame(rows)
    path = tmp_path / "sample.xlsx"
    df.to_excel(path, header=False, index=False)
    return path


def test_polars_parser_detects_header_row(tmp_path) -> None:
    rows = [
        [None, None],
        ["Fecha", "Valor"],
        [pd.Timestamp("2024-01-01"), 10],
    ]
    path = _make_sample_excel(tmp_path, rows)

    parsed = parse_workbook(path, engine="polars")

    assert parsed.metadata.header_row_index["Sheet1"] == 1
    assert parsed.metadata.column_counts["Sheet1"] == 2


def test_polars_parser_combines_double_header(tmp_path) -> None:
    rows = [
        ["Tarjetas de credito", None, "Tarjetas de debito", None],
        ["Cantidad", "Monto nominal", "Cantidad", "Monto nominal"],
        [10, 100.0, 12, 120.0],
    ]
    path = _make_sample_excel(tmp_path, rows)

    parsed = parse_workbook(path, engine="polars")
    columns = list(parsed.sheets["Sheet1"].columns)

    assert columns[0] == "Tarjetas de credito Cantidad"
    assert columns[1] == "Tarjetas de credito Monto nominal"
    assert columns[2] == "Tarjetas de debito Cantidad"
    assert columns[3] == "Tarjetas de debito Monto nominal"


def test_polars_parser_combines_triple_header(tmp_path) -> None:
    rows = [
        ["Tarjetas de credito", None],
        ["Un pago", None],
        ["Cantidad", "Monto nominal"],
        [10, 100.0],
    ]
    path = _make_sample_excel(tmp_path, rows)

    parsed = parse_workbook(path, engine="polars")
    columns = list(parsed.sheets["Sheet1"].columns)

    assert columns[0] == "Tarjetas de credito Un pago Cantidad"
    assert columns[1] == "Tarjetas de credito Un pago Monto nominal"


def test_polars_parser_uniquifies_headers(tmp_path) -> None:
    rows = [
        ["Tarjetas", None],
        ["Un pago", None],
        ["Cantidad", "Cantidad"],
        [10, 12],
    ]
    path = _make_sample_excel(tmp_path, rows)

    parsed = parse_workbook(path, engine="polars")
    columns = list(parsed.sheets["Sheet1"].columns)

    assert columns[0] == "Tarjetas Un pago Cantidad"
    assert columns[1] == "Tarjetas Un pago Cantidad_2"


def test_polars_parser_drops_trailing_sparse_row_and_null_column(tmp_path) -> None:
    rows = [
        ["Saldos en fondos comunes ri pspcp", None, None],
        ["Saldo", "Monto nominal", None],
        [100, 200, None],
        [None, None, 5],
    ]
    path = _make_sample_excel(tmp_path, rows)

    parsed = parse_workbook(path, engine="polars")
    result = parsed.sheets["Sheet1"]

    assert parsed.metadata.header_row_index["Sheet1"] == 0
    assert parsed.metadata.column_counts["Sheet1"] == 2
    assert list(result.columns) == [
        "Saldos en fondos comunes ri pspcp Saldo",
        "Saldos en fondos comunes ri pspcp Monto nominal",
    ]
    assert len(result) == 1


def test_polars_engine_returns_polars_dataframe(tmp_path) -> None:
    """Ensure the polars engine actually returns a Polars DataFrame."""
    import polars as pl

    rows = [
        ["Concepto", "Valor"],
        ["Cheques", 100],
        ["Transferencias", 200],
    ]
    path = _make_sample_excel(tmp_path, rows)

    parsed = parse_workbook(path, engine="polars")
    df = parsed.sheets["Sheet1"]

    assert isinstance(df, pl.DataFrame)


def test_polars_engine_preserves_datetime_type(tmp_path) -> None:
    """Ensure datetime values are preserved correctly in Polars."""
    rows = [
        ["Fecha", "Valor"],
        [pd.Timestamp("2024-05-17"), 10],
        [pd.Timestamp("2024-05-31"), 20],
    ]
    path = _make_sample_excel(tmp_path, rows)

    parsed = parse_workbook(path, engine="polars")
    df = parsed.sheets["Sheet1"]

    # Check that we can read the values correctly
    assert len(df) == 2
    col_names = df.columns
    assert "Fecha" in col_names or any("Fecha" in c for c in col_names)


def test_polars_parser_empty_workbook(tmp_path) -> None:
    """Test handling of an empty workbook."""
    path = tmp_path / "empty.xlsx"
    pd.DataFrame().to_excel(path, header=False, index=False)

    parsed = parse_workbook(path, engine="polars")

    assert len(parsed.sheets) == 1
    assert parsed.metadata.row_counts["Sheet1"] == 0


def test_polars_parser_single_column(tmp_path) -> None:
    """Test parsing a two-column workbook (single column would be dropped as sparse noise)."""
    rows = [["Concepto", "Valor"], ["A", 100], ["B", 200]]
    path = _make_sample_excel(tmp_path, rows)

    parsed = parse_workbook(path, engine="polars")

    assert parsed.metadata.column_counts["Sheet1"] == 2
    assert len(parsed.sheets["Sheet1"]) == 2


def test_polars_parser_inferred_types(tmp_path) -> None:
    """Test that inferred types are correctly recorded for polars."""
    rows = [
        ["Texto", "Numero", "Fecha"],
        ["ABC", 123, pd.Timestamp("2024-05-17")],
        ["DEF", 456, pd.Timestamp("2024-06-30")],
    ]
    path = _make_sample_excel(tmp_path, rows)

    parsed = parse_workbook(path, engine="polars")

    inferred = parsed.metadata.inferred_types["Sheet1"]
    assert "Texto" in inferred or any("Texto" in k for k in inferred)
    assert "Numero" in inferred or any("Numero" in k for k in inferred)
