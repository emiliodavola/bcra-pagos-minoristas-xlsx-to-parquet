from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

DataFrame = Any


class DiscoveryRequest(BaseModel):
    source_url: str
    match_rules: list[str]


class DiscoveredFile(BaseModel):
    url: str
    filename: str
    modified_at: datetime | None = None
    version: str | None = None


class DiscoveryResult(BaseModel):
    source_url: str
    selected: DiscoveredFile
    candidates: list[DiscoveredFile]
    discovered_at: datetime
    selection_reason: str


class DownloadRequest(BaseModel):
    url: str
    output_dir: Path
    filename: str | None = None
    expected_sha256: str | None = None
    allow_overwrite: bool = False


class DownloadResult(BaseModel):
    url: str
    path: Path
    size_bytes: int
    sha256: str
    etag: str | None
    last_modified: datetime | None
    downloaded_at: datetime


class ParsingMetadata(BaseModel):
    sheet_names: list[str]
    row_counts: dict[str, int]
    column_counts: dict[str, int]
    inferred_types: dict[str, dict[str, str]]
    header_row_index: dict[str, int]


class ParsedDataset(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    sheets: dict[str, DataFrame]
    metadata: ParsingMetadata


class NormalizedDataset(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    sheets: dict[str, DataFrame]
    schema_: dict[str, dict[str, str]] = Field(alias="schema")
    column_mapping: dict[str, dict[str, str]]
    row_counts: dict[str, int]
    dropped_rows: dict[str, int]
    schema_report: dict[str, dict[str, Any]] = Field(default_factory=dict)


class StorageRequest(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    dataset: NormalizedDataset
    output_path: Path
    format: Literal["parquet", "delta"]
    partition_by: list[str] | None = None
    mode: Literal["append", "overwrite"] = "append"


class StorageResult(BaseModel):
    paths: dict[str, Path]
    format: str
    row_counts: dict[str, int]
    version: int | None = None
