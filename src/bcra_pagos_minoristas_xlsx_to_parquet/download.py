from __future__ import annotations

import hashlib
import tempfile
import time
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx

from .logging_utils import get_logger, log_event
from .models import DownloadRequest, DownloadResult

_LOGGER = get_logger(__name__)


def download_file(
    request: DownloadRequest,
    *,
    client: httpx.Client | None = None,
    retries: int = 0,
    timeout_seconds: int | None = None,
) -> DownloadResult:
    request.output_dir.mkdir(parents=True, exist_ok=True)
    filename = request.filename or Path(urlparse(request.url).path).name
    if not filename:
        raise ValueError("Download request URL does not contain a filename.")

    target_path = request.output_dir / filename
    if target_path.exists() and not request.allow_overwrite:
        existing_hash = _sha256_file(target_path)
        if request.expected_sha256 is None or existing_hash == request.expected_sha256:
            result = DownloadResult(
                url=request.url,
                path=target_path,
                size_bytes=target_path.stat().st_size,
                sha256=existing_hash,
                etag=None,
                last_modified=None,
                downloaded_at=datetime.utcnow(),
            )
            log_event(
                _LOGGER,
                "download.cache_hit",
                url=request.url,
                path=str(target_path),
                sha256=existing_hash,
            )
            return result
        raise ValueError("Existing file checksum does not match expected SHA-256.")

    close_client = False
    if client is None:
        client = httpx.Client(timeout=timeout_seconds, follow_redirects=True)
        close_client = True
    try:
        attempts = max(1, retries + 1)
        for attempt in range(1, attempts + 1):
            try:
                with client.stream("GET", request.url) as response:
                    response.raise_for_status()
                    etag = response.headers.get("ETag")
                    last_modified = _parse_last_modified(
                        response.headers.get("Last-Modified")
                    )
                    sha256 = hashlib.sha256()
                    with tempfile.NamedTemporaryFile(
                        mode="wb",
                        delete=False,
                        dir=request.output_dir,
                        prefix=f".{filename}.",
                    ) as tmp:
                        for chunk in response.iter_bytes():
                            tmp.write(chunk)
                            sha256.update(chunk)
                        temp_path = Path(tmp.name)
                    digest = sha256.hexdigest()
                    if request.expected_sha256 and digest != request.expected_sha256:
                        temp_path.unlink(missing_ok=True)
                        raise ValueError(
                            "Downloaded file checksum does not match expected SHA-256."
                        )
                    temp_path.replace(target_path)
                    result = DownloadResult(
                        url=request.url,
                        path=target_path,
                        size_bytes=target_path.stat().st_size,
                        sha256=digest,
                        etag=etag,
                        last_modified=last_modified,
                        downloaded_at=datetime.utcnow(),
                    )
                    log_event(
                        _LOGGER,
                        "download.completed",
                        url=request.url,
                        path=str(target_path),
                        sha256=digest,
                        size_bytes=result.size_bytes,
                    )
                    return result
            except httpx.HTTPError:
                if attempt == attempts:
                    raise
                time.sleep(min(2 ** (attempt - 1), 8))
        raise RuntimeError("Download attempts exhausted.")
    finally:
        if close_client:
            client.close()


def _sha256_file(path: Path) -> str:
    sha256 = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def _parse_last_modified(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
