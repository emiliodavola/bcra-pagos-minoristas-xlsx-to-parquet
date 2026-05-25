import httpx

from bcra_pagos_minoristas_xlsx_to_parquet.download import download_file
from bcra_pagos_minoristas_xlsx_to_parquet.models import DownloadRequest


def test_download_cache_hit(tmp_path) -> None:
    content = b"fixture-content"
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, content=content)
    )

    with httpx.Client(transport=transport) as client:
        request = DownloadRequest(
            url="https://example.com/data.xlsx",
            output_dir=tmp_path,
        )
        first = download_file(request, client=client)

    with httpx.Client(transport=transport) as client:
        cached_request = DownloadRequest(
            url="https://example.com/data.xlsx",
            output_dir=tmp_path,
            expected_sha256=first.sha256,
        )
        second = download_file(cached_request, client=client)

    assert second.sha256 == first.sha256
    assert second.path.exists()
