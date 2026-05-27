import pandas as pd

from bcra_pagos_minoristas_xlsx_to_parquet.parser import parse_workbook


def test_parser_detects_header_row(tmp_path) -> None:
    raw = pd.DataFrame(
        [
            [None, None],
            ["Fecha", "Valor"],
            [pd.Timestamp("2024-01-01"), 10],
        ]
    )
    path = tmp_path / "sample.xlsx"
    raw.to_excel(path, header=False, index=False)

    parsed = parse_workbook(path, engine="pandas")

    assert parsed.metadata.header_row_index["Sheet1"] == 1
    assert parsed.metadata.column_counts["Sheet1"] == 2


def test_parser_combines_double_header(tmp_path) -> None:
    raw = pd.DataFrame(
        [
            ["Tarjetas de credito", None, "Tarjetas de debito", None],
            ["Cantidad", "Monto nominal", "Cantidad", "Monto nominal"],
            [10, 100.0, 12, 120.0],
        ]
    )
    path = tmp_path / "double_header.xlsx"
    raw.to_excel(path, header=False, index=False)

    parsed = parse_workbook(path, engine="pandas")
    columns = list(parsed.sheets["Sheet1"].columns)

    assert columns[0] == "Tarjetas de credito Cantidad"
    assert columns[1] == "Tarjetas de credito Monto nominal"
    assert columns[2] == "Tarjetas de debito Cantidad"
    assert columns[3] == "Tarjetas de debito Monto nominal"


def test_parser_combines_triple_header(tmp_path) -> None:
    raw = pd.DataFrame(
        [
            ["Tarjetas de credito", None],
            ["Un pago", None],
            ["Cantidad", "Monto nominal"],
            [10, 100.0],
        ]
    )
    path = tmp_path / "triple_header.xlsx"
    raw.to_excel(path, header=False, index=False)

    parsed = parse_workbook(path, engine="pandas")
    columns = list(parsed.sheets["Sheet1"].columns)

    assert columns[0] == "Tarjetas de credito Un pago Cantidad"
    assert columns[1] == "Tarjetas de credito Un pago Monto nominal"


def test_parser_uniquifies_headers(tmp_path) -> None:
    raw = pd.DataFrame(
        [
            ["Tarjetas", None],
            ["Un pago", None],
            ["Cantidad", "Cantidad"],
            [10, 12],
        ]
    )
    path = tmp_path / "duplicate_headers.xlsx"
    raw.to_excel(path, header=False, index=False)

    parsed = parse_workbook(path, engine="pandas")
    columns = list(parsed.sheets["Sheet1"].columns)

    assert columns[0] == "Tarjetas Un pago Cantidad"
    assert columns[1] == "Tarjetas Un pago Cantidad_2"


def test_parser_drops_trailing_sparse_row_and_null_column(tmp_path) -> None:
    raw = pd.DataFrame(
        [
            ["Saldos en fondos comunes ri pspcp", None, None],
            ["Saldo", "Monto nominal", None],
            [100, 200, None],
            [None, None, 5],
        ]
    )
    path = tmp_path / "sparse_footer.xlsx"
    raw.to_excel(path, header=False, index=False)

    parsed = parse_workbook(path, engine="pandas")
    result = parsed.sheets["Sheet1"]

    assert parsed.metadata.header_row_index["Sheet1"] == 0
    assert parsed.metadata.column_counts["Sheet1"] == 2
    assert list(result.columns) == [
        "Saldos en fondos comunes ri pspcp Saldo",
        "Saldos en fondos comunes ri pspcp Monto nominal",
    ]
    assert len(result) == 1
