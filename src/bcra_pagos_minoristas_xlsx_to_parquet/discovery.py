from __future__ import annotations

import re
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin, urlparse

import httpx

from .logging_utils import get_logger, log_event
from .models import DiscoveredFile, DiscoveryRequest, DiscoveryResult

_LOGGER = get_logger(__name__)


class _LinkCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        for key, value in attrs:
            if key.lower() == "href" and value:
                self.links.append(value)


def discover_files(
    request: DiscoveryRequest,
    *,
    client: httpx.Client | None = None,
) -> DiscoveryResult:
    link_collector = _LinkCollector()
    close_client = False
    if client is None:
        client = httpx.Client(follow_redirects=True)
        close_client = True
    try:
        response = client.get(request.source_url)
        response.raise_for_status()
        link_collector.feed(response.text)

        candidates = _build_candidates(
            request.source_url, link_collector.links, request.match_rules
        )
        publication_links = _publication_links(request.source_url, link_collector.links)
        for publication in publication_links:
            publication_response = client.get(publication)
            publication_response.raise_for_status()
            publication_collector = _LinkCollector()
            publication_collector.feed(publication_response.text)
            candidates.extend(
                _build_candidates(
                    publication,
                    publication_collector.links,
                    request.match_rules,
                )
            )
    finally:
        if close_client:
            client.close()

    candidates = _dedupe_candidates(candidates)
    if not candidates:
        raise ValueError("No matching files found for discovery request.")

    selected = _select_candidate(candidates)
    selection_reason = _selection_reason(selected)
    result = DiscoveryResult(
        source_url=request.source_url,
        selected=selected,
        candidates=candidates,
        discovered_at=datetime.utcnow(),
        selection_reason=selection_reason,
    )
    log_event(
        _LOGGER,
        "discovery.completed",
        source_url=request.source_url,
        candidate_count=len(candidates),
        selected_url=selected.url,
        selection_reason=selection_reason,
    )
    return result


def _build_candidates(
    source_url: str,
    links: Iterable[str],
    match_rules: Iterable[str],
) -> list[DiscoveredFile]:
    patterns = [re.compile(rule, re.IGNORECASE) for rule in match_rules]
    candidates: list[DiscoveredFile] = []
    for link in links:
        resolved = urljoin(source_url, link)
        filename = Path(urlparse(resolved).path).name
        if not filename:
            continue
        if not any(
            pattern.search(filename) or pattern.search(resolved) for pattern in patterns
        ):
            continue
        candidates.append(
            DiscoveredFile(
                url=resolved,
                filename=filename,
                version=_extract_version(filename),
            )
        )
    return candidates


def _publication_links(source_url: str, links: Iterable[str]) -> list[str]:
    publications: list[str] = []
    for link in links:
        resolved = urljoin(source_url, link)
        if "/publicaciones/" in urlparse(resolved).path:
            publications.append(resolved)
    return sorted(set(publications))


def _dedupe_candidates(candidates: list[DiscoveredFile]) -> list[DiscoveredFile]:
    unique: dict[str, DiscoveredFile] = {}
    for candidate in candidates:
        unique.setdefault(candidate.url, candidate)
    return list(unique.values())


def _extract_version(filename: str) -> str | None:
    date_match = re.search(r"(\d{4})[._-]?(\d{2})(?:[._-]?(\d{2}))?", filename)
    if date_match:
        year, month, day = date_match.group(1), date_match.group(2), date_match.group(3)
        if day:
            return f"{year}.{month}.{day}"
        return f"{year}.{month}"
    month_match = _spanish_month_version(filename)
    if month_match:
        return month_match
    version_match = re.search(r"(\d+(?:\.\d+)+)", filename)
    if version_match:
        return version_match.group(1)
    numeric_match = re.search(r"(\d{2,})", filename)
    if numeric_match:
        return numeric_match.group(1)
    return None


def _spanish_month_version(filename: str) -> str | None:
    months = {
        "enero": 1,
        "febrero": 2,
        "marzo": 3,
        "abril": 4,
        "mayo": 5,
        "junio": 6,
        "julio": 7,
        "agosto": 8,
        "septiembre": 9,
        "setiembre": 9,
        "octubre": 10,
        "noviembre": 11,
        "diciembre": 12,
    }
    lowered = filename.lower()
    match = re.search(
        r"(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre)[^0-9]{0,6}(\d{4})",
        lowered,
    )
    if match:
        month = months[match.group(1)]
        year = int(match.group(2))
        return f"{year}.{month:02d}"
    match = re.search(
        r"(\d{4})[^a-z0-9]{0,6}(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre)",
        lowered,
    )
    if match:
        year = int(match.group(1))
        month = months[match.group(2)]
        return f"{year}.{month:02d}"
    return None


def _version_key(version: str | None) -> tuple[int, ...]:
    if not version:
        return ()
    parts = re.split(r"[.-]", version)
    numbers: list[int] = []
    for part in parts:
        if part.isdigit():
            numbers.append(int(part))
    return tuple(numbers)


def _select_candidate(candidates: list[DiscoveredFile]) -> DiscoveredFile:
    return sort_candidates(candidates, descending=True)[0]


def sort_candidates(
    candidates: list[DiscoveredFile],
    *,
    descending: bool = False,
) -> list[DiscoveredFile]:
    return sorted(
        candidates,
        key=lambda candidate: (
            _version_key(candidate.version),
            candidate.modified_at or datetime.min,
            candidate.url,
        ),
        reverse=descending,
    )


def _selection_reason(candidate: DiscoveredFile) -> str:
    if candidate.version:
        return "version"
    if candidate.modified_at:
        return "modified_at"
    return "url"
