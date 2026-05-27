# Normalization Specification

## Objective

Generate clean and consistent datasets.

---

# Inputs

```python
class NormalizeRequest:
    dataset: ParsedDataset
```

---

# Outputs

```python
class NormalizedDataset:
    sheets: dict[str, DataFrame]
    schema: dict[str, dict[str, str]]
    column_mapping: dict[str, dict[str, str]]
    row_counts: dict[str, int]
    dropped_rows: dict[str, int]
```

---

# Requirements

## N1
Column names must be lowercase snake_case and must strip accents.

## N2
Column names must be unique.

## N3
Data types must be inferred automatically.

## N4
Dates must be normalized to UTC.

## N5
Numeric values must be sanitized.

## N6
Null values must be standardized.

## N7
Normalization must be deterministic.

## N8
Sheet names must be preserved.

## N9
If a date column exists, preserve the source value in `fecha_original` and create `fecha` as the first day of the month.

## N10
Rows without date and without values at the end of a sheet must be dropped.

---

# Failure Cases

- Duplicate columns after normalization.
- Invalid type coercion.
- Mixed incompatible types.

---

# Logging

Normalization logs must include:
- schema changes
- renamed columns
- dropped rows
- type conversions
