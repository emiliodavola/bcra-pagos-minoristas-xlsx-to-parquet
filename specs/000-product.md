# bcra-pagos-minoristas-xlsx-to-parquet

## Vision

`bcra-pagos-minoristas-xlsx-to-parquet` is a Python package for discovering, downloading,
normalizing and storing datasets published by the BCRA.

The package transforms XLSX files into analytics-oriented datasets
using Parquet and optionally Delta Lake.

---

# Goals

## Functional Goals

The system must:

1. Discover XLSX files automatically.
2. Download files even if filenames change.
3. Detect new versions.
4. Parse Excel files.
5. Normalize tabular structures.
6. Export datasets to:
   - parquet
   - delta lake
7. Maintain ingestion metadata.
8. Provide a CLI interface.
9. Provide a Python API.

---

## Non Functional Goals

### Performance

- Must support large XLSX files.
- Must minimize memory usage.

### Reproducibility

- Same input → same output.

### Extensibility

- New datasets should be pluggable.

### Idempotency

- Re-running ingestion must not duplicate data.

### Observability

- Structured logs.
- Download traceability.

---

# Architecture

            ┌──────────────┐
            │   BCRA Web   │
            └──────┬───────┘
                   │
                   ▼
          ┌─────────────────┐
          │   Discovery     │
          └────────┬────────┘
                   │
                   ▼
          ┌─────────────────┐
          │   Downloader    │
          └────────┬────────┘
                   │
                   ▼
          ┌─────────────────┐
          │     Parser      │
          └────────┬────────┘
                   │
                   ▼
          ┌─────────────────┐
          │   Normalizer    │
          └────────┬────────┘
                   │
        ┌──────────┴──────────┐
        ▼                     ▼
┌──────────────┐     ┌────────────────┐
│   Parquet    │     │   Delta Lake   │
└──────────────┘     └────────────────┘

---

# Tech Stack

## Core

- Python 3.10+
- polars
- pyarrow
- httpx
- typer
- pydantic

## Optional

- deltalake
- duckdb
- prefect

---

# Engineering Principles

1. Simplicity first.
2. Strong typing.
3. Declarative pipelines.
4. Immutable raw data.
5. Reproducible outputs.
6. Analytics-first storage.