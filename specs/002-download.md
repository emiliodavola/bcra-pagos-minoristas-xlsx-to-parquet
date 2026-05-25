# Download Specification

## Objective

Download remote files reliably and reproducibly.

---

# Inputs

```python
class DownloadRequest:
    url: str
    output_dir: Path
    filename: str | None
    expected_sha256: str | None
    allow_overwrite: bool
```

---

# Outputs

```python
class DownloadResult:
    url: str
    path: Path
    size_bytes: int
    sha256: str
    etag: str | None
    last_modified: datetime | None
    downloaded_at: datetime
```

---

# Requirements

## D1
Must support HTTP and HTTPS downloads.

## D2
Must follow redirects.

## D3
Must support configurable retries with backoff.

## D4
Must write files atomically (download to temp then rename).

## D5
Must be idempotent: if the target file exists and its checksum matches, reuse it.

## D6
Must compute and expose SHA-256 checksums.

## D7
Must capture ETag and Last-Modified when available.

## D8
Must expose download metadata required for traceability.

---

# Failure Cases

- Network or HTTP errors.
- Insufficient permissions or disk space.
- Checksum mismatch.
- Output directory missing.

---

# Logging

Download logs must include:
- source URL
- destination path
- size and checksum
- duration
- cache hit or miss
