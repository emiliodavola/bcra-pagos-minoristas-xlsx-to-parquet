# Ingestion Table Specification

## Objective

Define the structure expected when ingesting BCRA monthly time-series tables.

---

## Scope

Applies to all tabular datasets ingested from XLSX sheets whose rows represent monthly observations.

---

## Required Shape

Each table must contain:

- one canonical date column
- one or more numeric measure columns
- no trailing garbage rows
- no fully empty columns

---

## Date Rules

### D1

Each table must expose a `fecha_original` column with the source date value.

### D2

Each table must expose a canonical `fecha` column normalized to the first day of the month.

### D3

The source date may represent either month start (`MS`) or month end (`ME`).

### D4

Both `MS` and `ME` inputs must normalize to the same monthly bucket in `fecha`.

### D5

Date values must be parsed deterministically and treated as monthly periods, not daily facts.

---

## Measure Rules

### M1

All non-date measures must be numeric when possible.

### M2

Columns with monthly balances, counts, totals, or rates must remain separate and preserve source ordering.

### M3

Columns produced only by header artifacts or merged-cell carryover and containing only nulls must be dropped.

---

## Header Rules

### H1

Tables may have one, two, or three header rows.

### H2

Multirow headers must be concatenated from top to bottom, preserving the original left-to-right order.

### H3

Repeated header labels must be made unique deterministically.

### H4

Incomplete header rows with sparse titles must still be recognized as part of the header block.

---

## Row Cleanup Rules

### R1

Trailing rows containing no data, or only a single stray cell, must be removed.

### R2

Rows that are structurally blank after normalization must not be kept.

### R3

No ingested table should end with a malformed footer row.

---

## Failure Cases

- ambiguous date column naming
- malformed multirow header blocks
- duplicated columns from merged cells
- trailing sparse footer rows
