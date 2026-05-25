# Testing Specification

## Objective

Ensure reproducibility and correctness.

---

# Test Types

## Unit Tests

Must cover:
- discovery
- download
- parser
- normalization
- storage

---

## Integration Tests

Must cover:
- end-to-end pipeline
- parquet generation
- delta generation

---

## Golden Tests

Must validate:
- parquet snapshots
- schema consistency

---

# Requirements

## T1
Tests must be deterministic.

## T2
Tests must not depend on live BCRA endpoints.

## T3
Tests must support local fixtures.

## T4
Golden files must be versioned and stable across runs.

---

# Fixtures

Fixtures should include:
- sample XLSX files
- malformed files
- multi-sheet workbooks
