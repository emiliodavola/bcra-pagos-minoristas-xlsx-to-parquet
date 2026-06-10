# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- (none yet)

### Changed
- (pending changes will go here)

### Fixed
- (pending fixes will go here)

### Removed
- (nothing removed yet)

## [0.1.2] - 2025-06-10

### Added
- **Phase 1: Cleanup and Quality**
  - DRY refactoring: Centralized `_is_blank_value()` into shared `utils.is_blank()` function
  - Fixed mypy errors (3 `schema_` type ignores in `tests/test_storage.py`)
  - Added `@timed` decorator to `logging_utils.py` for timing pipeline stages
  - Added structured `duration_ms` field support to `log_event()`
  - Ruff format applied across all Python files

- **Phase 2: Testing Improvements**
  - Added 10 new tests for Polars parser engine in `tests/test_parser_polars.py`
    - Tests for header detection, double/triple header combining, uniqueness
    - Verifies Polars DataFrame type return and datetime preservation
    - Covers empty workbooks, single-column sheets, inferred types
  - Added 14 integration tests in `tests/test_pipeline.py`
    - `run_fetch()` discovery and download pipeline stage
    - `run_parse()` workbook parsing stage
    - `run_build()` normalize-and-store stage
    - Full end-to-end pipeline test (fetch → parse → normalize → store)
  - Added edge case tests: no candidates, missing files, invalid engine, checksum mismatch
  - Multi-sheet workbook support tests
  - Empty dataframe and build integration tests

### Changed
- Refactored `_is_blank_value()` in `parser.py` and `normalization.py` to use shared `utils.is_blank()`
- Updated test assertions for `StorageResult.paths` as attribute instead of dict key

### Fixed
- Removed unused imports (`pytest`, `hashlib`) from test files
- Fixed linting errors (F401, F841) in test files

## [0.1.3] - 2025-06-10

### Changed
- **Phase 3-4: Cleanup and Documentation**
  - Removed unused `pydantic-settings` dependency from `pyproject.toml`
  - Updated `.gitignore` to ignore entire `data/` directory (XLSX, Parquet, metadata)
  - Added metadata JSON format documentation in README.md
    - Documented fetch.json, parse.json, build.json, run.json structure
    - Added sample formats for parse.json and build.json
  - Updated pyproject.toml description from placeholder to real description

## [0.1.1] - Previous Release

### Added
- Core ETL pipeline: discovery → download → parse → normalize → storage
- CLI with 4 commands: `fetch`, `parse`, `build`, `run`
- TOML-based configuration via `bcra.toml`
- Environment variable overrides with `BCRA__` prefix

### Changed
- (no breaking changes)

## [0.1.0] - Initial Release

### Added
- Initial project structure and scaffolding
- BCRA minor payment data pipeline
- XLSX to Parquet conversion support
- Basic tests for discovery, download, normalization, storage

---

*Note: For full commit history, see the [git log](https://github.com/emiliodavola/bcra-pagos-minoristas-xlsx-to-parquet/commits/dev).*
