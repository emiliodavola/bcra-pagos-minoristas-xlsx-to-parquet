import pandas as pd

from bcra_pagos_minoristas_xlsx_to_parquet.models import (
    NormalizedDataset,
    StorageRequest,
)
from bcra_pagos_minoristas_xlsx_to_parquet.storage import store_dataset


def test_storage_writes_parquet(tmp_path) -> None:
    df = pd.DataFrame({"a": [1, 2]})
    dataset = NormalizedDataset(
        sheets={"sheet": df},
        schema_={"sheet": {"a": "int64"}},  # type: ignore[call-arg]
        column_mapping={"sheet": {"a": "a"}},
        row_counts={"sheet": 2},
        dropped_rows={"sheet": 0},
    )
    request = StorageRequest(
        dataset=dataset,
        output_path=tmp_path,
        format="parquet",
        partition_by=[],
        mode="overwrite",
    )

    result = store_dataset(request)

    sheet_paths = list((tmp_path / "sheet").glob("schema=*/"))
    assert sheet_paths
    assert list(sheet_paths[0].glob("*.parquet"))
    assert result.row_counts["sheet"] == 2


def test_storage_versions_different_schemas(tmp_path) -> None:
    first = NormalizedDataset(
        sheets={"sheet": pd.DataFrame({"a": [1]})},
        schema_={"sheet": {"a": "int64"}},  # type: ignore[call-arg]
        column_mapping={"sheet": {"a": "a"}},
        row_counts={"sheet": 1},
        dropped_rows={"sheet": 0},
    )
    second = NormalizedDataset(
        sheets={"sheet": pd.DataFrame({"a": [1], "b": [2]})},
        schema_={"sheet": {"a": "int64", "b": "int64"}},  # type: ignore[call-arg]
        column_mapping={"sheet": {"a": "a", "b": "b"}},
        row_counts={"sheet": 1},
        dropped_rows={"sheet": 0},
    )

    store_dataset(
        StorageRequest(
            dataset=first,
            output_path=tmp_path,
            format="parquet",
            partition_by=[],
            mode="append",
        )
    )
    store_dataset(
        StorageRequest(
            dataset=second,
            output_path=tmp_path,
            format="parquet",
            partition_by=[],
            mode="append",
        )
    )

    sheet_root = tmp_path / "sheet"
    assert len(list(sheet_root.glob("schema=*"))) == 2
