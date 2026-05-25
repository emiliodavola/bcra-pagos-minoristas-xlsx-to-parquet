# Parser Specification

## Objective

Transform XLSX files into typed tabular datasets.

---

# Inputs

```python
class ParseRequest:
    path: Path
    engine: Literal["polars", "pandas"]
    sheet_names: list[str] | None
```

---

# Outputs

```python
class ParsingMetadata:
    sheet_names: list[str]
    row_counts: dict[str, int]
    column_counts: dict[str, int]
    inferred_types: dict[str, dict[str, str]]
    header_row_index: dict[str, int]
```

```python
class ParsedDataset:
    sheets: dict[str, DataFrame]
    metadata: ParsingMetadata
```

---

# Requirements

## P1
Must support multiple sheets.

## P2
Must detect dynamic headers.

## P3
Must remove fully empty rows.

## P4
Must support polars and pandas engines.

## P5
Must preserve column ordering.

## P6
Must expose parsing metadata.

## P7
Must allow selecting a subset of sheets.

## P8
Must support multi-row headers (2–3 rows) by concatenating group + subheaders (e.g., "Tarjetas de credito" + "Un pago" + "Cantidad").

---

# Failure Cases

- Invalid XLSX structure.
- Empty workbook.
- Unsupported sheet format.
- Unsupported engine.

---

# Logging

Parsing logs must include:
- input path
- engine
- sheet count
- duration
