from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import pandas as pd
import polars as pl
import pyarrow as pa
import pyarrow.parquet as pq

from .logging_utils import get_logger, log_event
from .models import NormalizedDataset, StorageRequest, StorageResult

_LOGGER = get_logger(__name__)


def store_dataset(request: StorageRequest) -> StorageResult:
    paths: dict[str, Path] = {}
    row_counts: dict[str, int] = {}

    request.output_path.mkdir(parents=True, exist_ok=True)

    for sheet, dataframe in request.dataset.sheets.items():
        sheet_path = (
            request.output_path
            / _safe_name(sheet)
            / _schema_snapshot_name(request.dataset, sheet)
        )
        if request.format == "parquet":
            if request.mode == "overwrite" and sheet_path.exists():
                shutil.rmtree(sheet_path)
            sheet_path.mkdir(parents=True, exist_ok=True)
            _write_parquet(
                dataframe, sheet_path, request.partition_by or [], request.mode
            )
        elif request.format == "delta":
            _write_delta(
                dataframe, sheet_path, request.partition_by or [], request.mode
            )
        else:
            raise ValueError(f"Unsupported storage format: {request.format}")

        _write_manifest(request, sheet, sheet_path)
        paths[sheet] = sheet_path
        row_counts[sheet] = len(dataframe)

    result = StorageResult(paths=paths, format=request.format, row_counts=row_counts)
    log_event(
        _LOGGER,
        "storage.completed",
        format=request.format,
        sheet_count=len(paths),
    )
    return result


def _write_parquet(
    dataframe: Any,
    path: Path,
    partition_by: list[str],
    mode: str,
) -> None:
    table = _to_arrow_table(dataframe)
    if partition_by or mode == "append":
        pq.write_to_dataset(
            table,
            root_path=str(path),
            partition_cols=partition_by or None,
            compression="snappy",
        )
    else:
        file_path = path / "data.parquet"
        pq.write_table(table, file_path, compression="snappy")


def _write_delta(
    dataframe: Any,
    path: Path,
    partition_by: list[str],
    mode: str,
) -> None:
    try:
        from deltalake import write_deltalake
    except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
        raise ModuleNotFoundError("deltalake is not installed.") from exc

    table = _to_arrow_table(dataframe)
    write_deltalake(
        str(path),
        table,
        mode=mode,
        partition_by=partition_by or None,
    )


def _write_manifest(request: StorageRequest, sheet: str, path: Path) -> None:
    schema = request.dataset.schema_.get(sheet, {})
    manifest = {
        "sheet": sheet,
        "format": request.format,
        "mode": request.mode,
        "partition_by": request.partition_by or [],
        "schema_fingerprint": _schema_snapshot_name(request.dataset, sheet),
        "columns": schema,
        "column_mapping": request.dataset.column_mapping.get(sheet, {}),
        "row_count": request.dataset.row_counts.get(sheet, 0),
        "dropped_rows": request.dataset.dropped_rows.get(sheet, 0),
    }
    path.joinpath("manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=True, indent=2, default=str),
        encoding="utf-8",
    )


def _schema_snapshot_name(dataset: NormalizedDataset, sheet: str) -> str:
    report = dataset.schema_report.get(sheet, {})
    fingerprint = report.get("schema_fingerprint")
    if isinstance(fingerprint, str) and fingerprint:
        return f"schema={fingerprint}"
    schema = dataset.schema_.get(sheet, {})
    payload = json.dumps(list(schema.items()), ensure_ascii=True, separators=(",", ":"))
    fingerprint = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"schema={fingerprint}"


def _to_arrow_table(dataframe: Any) -> pa.Table:
    if isinstance(dataframe, pl.DataFrame):
        return dataframe.to_arrow()
    if isinstance(dataframe, pd.DataFrame):
        return pa.Table.from_pandas(dataframe, preserve_index=False)
    raise ValueError("Unsupported dataframe type for storage.")


def _safe_name(value: str) -> str:
    return "".join(
        char if char.isalnum() or char in {"_", "-"} else "_" for char in value
    )
