# Storage Specification

## Objective

Persist normalized datasets in analytics-oriented formats.

---

# Supported Formats

- parquet
- delta

---

# Inputs

```python
class StorageRequest:
    dataset: NormalizedDataset
    output_path: Path
    format: Literal["parquet", "delta"]
    partition_by: list[str] | None
    mode: Literal["append", "overwrite"]
```

---

# Outputs

```python
class StorageResult:
    paths: dict[str, Path]
    format: str
    row_counts: dict[str, int]
    version: int | None
```

---

# Parquet Requirements

## P1
Must use snappy compression.

## P2
Must support partitioning.

## P3
Must support append mode.

## P4
Must preserve schema consistency.

---

# Delta Lake Requirements

## DLS1
Must support versioning.

## DLS2
Must support schema evolution.

## DLS3
Must support ACID transactions.

---

# General Requirements

## S1
Must write each sheet to a deterministic path.

## S2
Must write atomically per sheet.

## S3
Must surface per-sheet row counts.

---

# Failure Cases

- Invalid schema.
- Write permissions.
- Partition conflicts.

---

# Logging

Storage logs must include:
- output paths
- format
- partition info
- write duration
