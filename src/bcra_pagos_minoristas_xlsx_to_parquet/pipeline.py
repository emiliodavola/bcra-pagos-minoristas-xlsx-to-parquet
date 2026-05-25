from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Literal, cast

import httpx
import pandas as pd
import polars as pl

from .config import AppConfig
from .discovery import discover_files, sort_candidates
from .download import download_file
from .logging_utils import get_logger, log_event
from .models import DiscoveryRequest, DownloadRequest, ParsedDataset
from .normalization import normalize_dataset
from .parser import parse_workbook
from .storage import store_dataset

_LOGGER = get_logger(__name__)

if TYPE_CHECKING:
    from .models import StorageRequest


def run_fetch(config: AppConfig, *, client: httpx.Client | None = None) -> dict:
    discovery_request = DiscoveryRequest(
        source_url=config.source.url,
        match_rules=config.source.match_rules,
    )
    discovery_result = discover_files(discovery_request, client=client)
    candidates = _select_candidates(config, discovery_result)
    downloads = []
    for candidate in candidates:
        download_request = DownloadRequest(
            url=candidate.url,
            output_dir=config.download.output_dir,
        )
        download_result = download_file(
            download_request,
            client=client,
            retries=config.download.retries,
            timeout_seconds=config.download.timeout_seconds,
        )
        downloads.append(download_result)
    return {"discovery": discovery_result, "downloads": downloads}


def run_parse(config: AppConfig, *, input_path: Path | None = None) -> ParsedDataset:
    path = input_path or _latest_xlsx(config.download.output_dir)
    parsed = parse_workbook(
        path, engine=cast(Literal["polars", "pandas"], config.parser.engine)
    )
    log_event(_LOGGER, "pipeline.parse.completed", input_path=str(path))
    return parsed


def run_build(config: AppConfig, *, input_path: Path | None = None) -> dict:
    paths = [input_path] if input_path else _local_inputs(config)
    results: list[dict] = []
    for path in paths:
        parsed = run_parse(config, input_path=path)
        normalized = normalize_dataset(parsed, aliases=config.normalization.aliases)
        normalized = _add_ingestion_metadata(
            normalized,
            ingested_at=datetime.now(timezone.utc),
            source_url=str(path),
            source_sha256=None,
            source_version=None,
        )
        storage_result = store_dataset(request=_storage_request(config, normalized))
        results.append({"normalized": normalized, "storage": storage_result})
    if len(results) == 1:
        return results[0]
    return {"results": results}


def run_all(config: AppConfig, *, client: httpx.Client | None = None) -> dict:
    fetch_result = run_fetch(config, client=client)
    discovery = fetch_result["discovery"]
    candidates = _select_candidates(config, discovery)
    downloads = fetch_result["downloads"]
    if len(downloads) != len(candidates):
        raise ValueError("Download count does not match discovered candidates.")

    results: list[dict] = []
    for candidate, download_result in zip(candidates, downloads):
        parsed = run_parse(config, input_path=download_result.path)
        normalized = normalize_dataset(parsed, aliases=config.normalization.aliases)
        normalized = _add_ingestion_metadata(
            normalized,
            ingested_at=datetime.now(timezone.utc),
            source_url=download_result.url,
            source_sha256=download_result.sha256,
            source_version=candidate.version,
        )
        storage_result = store_dataset(request=_storage_request(config, normalized))
        results.append(
            {
                "download": download_result,
                "normalized": normalized,
                "storage": storage_result,
            }
        )
    return {
        "discovery": discovery,
        "downloads": downloads,
        "results": results,
    }


def _storage_request(config: AppConfig, normalized) -> StorageRequest:
    from .models import StorageRequest

    # `StorageRequest` is imported here at runtime to avoid import cycles.
    # Importing it for type checking allows linters (ruff/mypy) to resolve the name.

    return StorageRequest(
        dataset=normalized,
        output_path=config.storage.output_dir,
        format=cast(Literal["parquet", "delta"], config.storage.format),
        partition_by=config.storage.partition_by,
        mode=cast(Literal["append", "overwrite"], config.storage.mode),
    )


def _latest_xlsx(directory: Path) -> Path:
    candidates = list(directory.glob("*.xlsx"))
    if not candidates:
        raise FileNotFoundError(f"No XLSX files found in {directory}.")
    return max(candidates, key=lambda path: path.stat().st_mtime)


def _local_inputs(config: AppConfig) -> list[Path]:
    if config.source.mode == "all":
        paths = sorted(config.download.output_dir.glob("*.xlsx"))
        if not paths:
            raise FileNotFoundError(
                f"No XLSX files found in {config.download.output_dir}."
            )
        return paths
    return [_latest_xlsx(config.download.output_dir)]


def _select_candidates(config: AppConfig, discovery_result) -> list:
    if config.source.mode == "all":
        if config.storage.mode == "overwrite":
            raise ValueError(
                "storage.mode='overwrite' is not compatible with source.mode='all'."
            )
        return sort_candidates(discovery_result.candidates, descending=False)
    return [discovery_result.selected]


def _add_ingestion_metadata(
    dataset,
    *,
    ingested_at: datetime,
    source_url: str,
    source_sha256: str | None,
    source_version: str | None,
):
    ingested_at_value = ingested_at.isoformat()
    new_sheets = {}
    new_schema: dict[str, dict[str, str]] = {}
    new_mapping: dict[str, dict[str, str]] = {}
    for sheet, dataframe in dataset.sheets.items():
        _ensure_ingestion_columns_absent(dataframe)
        if isinstance(dataframe, pl.DataFrame):
            df = dataframe.with_columns(
                pl.lit(ingested_at_value).alias("ingested_at"),
                pl.lit(source_url).alias("source_url"),
                pl.lit(source_sha256).alias("source_sha256"),
                pl.lit(source_version).alias("source_version"),
            )
            new_schema[sheet] = {k: str(v) for k, v in df.schema.items()}
        elif isinstance(dataframe, pd.DataFrame):
            df = dataframe.copy()
            df["ingested_at"] = ingested_at_value
            df["source_url"] = source_url
            df["source_sha256"] = source_sha256
            df["source_version"] = source_version
            new_schema[sheet] = {k: str(v) for k, v in df.dtypes.items()}
        else:
            raise ValueError("Unsupported dataframe type for ingestion metadata.")

        mapping = dict(dataset.column_mapping.get(sheet, {}))
        for name in ["ingested_at", "source_url", "source_sha256", "source_version"]:
            mapping.setdefault(name, name)
        new_mapping[sheet] = mapping
        new_sheets[sheet] = df

    return dataset.model_copy(
        update={
            "sheets": new_sheets,
            "schema_": new_schema,
            "column_mapping": new_mapping,
        }
    )


def _ensure_ingestion_columns_absent(dataframe) -> None:
    existing = set(dataframe.columns)
    for name in ["ingested_at", "source_url", "source_sha256", "source_version"]:
        if name in existing:
            raise ValueError(f"Ingestion column already exists: {name}.")
