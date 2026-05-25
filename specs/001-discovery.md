# Discovery Specification

## Objective

Automatically discover XLSX files published by BCRA, even if filenames or URLs change.

---

# Inputs

```python
class DiscoveryRequest:
    source_url: str
    match_rules: list[str]
```

---

# Outputs

```python
class DiscoveredFile:
    url: str
    filename: str
    modified_at: datetime | None
    version: str | None
```

```python
class DiscoveryResult:
    source_url: str
    selected: DiscoveredFile
    candidates: list[DiscoveredFile]
    discovered_at: datetime
    selection_reason: str
```

---

# Requirements

## R1
Must support regex matching.

## R2
Must resolve relative URLs.

## R3
Must support multiple candidate files.

## R4
Must support HTML parsing.

## R5
Must select a file deterministically.

- Prefer highest version when version can be extracted from the filename.
- Otherwise prefer latest modified_at.
- Tie-break with stable sort on URL.

Version extraction should handle numeric dates (YYYY-MM or YYYY-MM-DD) and month names in Spanish.

## R6
Must expose discovery metadata (candidates, selection_reason, timestamps).

## R7
Must allow discovery without downloading any content.

## R8
If the source page lists publication pages, follow those pages (one level) to find matching XLSX links.

---

# Failure Cases

- No matching files found.
- Invalid source URL.
- HTTP errors.
- Ambiguous candidates with no deterministic tie-breaker.

---

# Logging

Discovery logs must include:
- source URL
- number of candidates
- selected file
- selection reason
- duration
