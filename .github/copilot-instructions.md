# Copilot instructions

## Build, test, lint
- No build, test, or lint commands are configured in `pyproject.toml` yet.

## High-level architecture
- The intended pipeline is **Discovery → Downloader → Parser → Normalizer → Storage (Parquet/Delta Lake)**. See the specs in `specs/001-discovery.md` through `specs/005-storage.md` for required inputs/outputs and failure cases.
- The CLI is specified in `specs/006-cli.md` with commands `fetch`, `parse`, `build`, and `run`, and should be wired to the pipeline stages above.
- Configuration is TOML-based (`specs/007-config.md`) and is expected to drive source URLs, parser engine, and storage format.

## Key conventions
- **Python version**: `pyproject.toml` requires Python `>=3.10`.
- **Tooling**: use `uv` for environment/dependency management and running commands (avoid direct `pip`/`venv` usage).
- **CLI entrypoint**: `pyproject.toml` defines the console script `bcra-pagos-minoristas-xlsx-to-parquet = bcra-pagos-minoristas-xlsx-to-parquet:main`.
- **Branching**: use Gitflow for organizing branches and releases.
- **Normalization rules** (`specs/004-normalization.md`): column names are lowercase `snake_case`, unique, deterministic; dates normalized to UTC; numeric/null values sanitized consistently.
- **Storage rules** (`specs/005-storage.md`): Parquet uses snappy compression and supports partitioning/append; schemas must remain consistent.
- **Testing rules** (`specs/008-testing.md`): tests must be deterministic and offline, use local fixtures, and include golden snapshots for Parquet output.
