# Configuration Specification

## Objective

Provide declarative project configuration.

---

# Format

TOML

---

# Schema (minimum)

```toml
[source]
url = "https://www.bcra.gob.ar"
match_rules = ["\\.xlsx$"]

[download]
output_dir = "data/raw"
retries = 3
timeout_seconds = 30

[parser]
engine = "polars"

[storage]
format = "parquet"
output_dir = "data/curated"
partition_by = []
mode = "append"
```

---

# Requirements

## CFG1
Configuration must support environment overrides.

## CFG2
Configuration must be validated.

## CFG3
Configuration errors must fail fast.

## CFG4
Default values must be applied when optional keys are missing.

---

# Environment Overrides

Use `BCRA__SECTION__KEY` naming (uppercase, double underscores). Example:

```
BCRA__PARSER__ENGINE=pandas
```

---

# Failure Cases

- Missing required fields.
- Invalid values.
- Unsupported formats.
