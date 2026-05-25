import httpx

from bcra_pagos_minoristas_xlsx_to_parquet.discovery import discover_files
from bcra_pagos_minoristas_xlsx_to_parquet.models import DiscoveryRequest


def test_discovery_selects_highest_version() -> None:
    html = """
    <html>
      <a href="https://example.com/data_v1.xlsx">v1</a>
      <a href="https://example.com/data_v2.xlsx">v2</a>
    </html>
    """

    transport = httpx.MockTransport(lambda request: httpx.Response(200, text=html))
    request = DiscoveryRequest(
        source_url="https://example.com",
        match_rules=[r"\.xlsx$"],
    )
    with httpx.Client(transport=transport) as client:
        result = discover_files(request, client=client)

    assert result.selected.filename == "data_v2.xlsx"


def test_discovery_follows_publications() -> None:
    index_html = """
    <html>
      <a href="/publicaciones/informe-de-pagos-minoristas-enero-de-2026/">enero</a>
      <a href="/publicaciones/informe-de-pagos-minoristas-marzo-de-2026/">marzo</a>
    </html>
    """
    enero_html = """
    <html>
      <a href="/archivos/Pdfs/PublicacionesEstadisticas/informes/series-informe-pagos-minoristas-2026-01.xlsx">xlsx</a>
    </html>
    """
    marzo_html = """
    <html>
      <a href="/archivos/Pdfs/PublicacionesEstadisticas/informes/series-informe-pagos-minoristas-2026-03.xlsx">xlsx</a>
    </html>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == "https://example.com/informe-de-pagos-minoristas":
            return httpx.Response(200, text=index_html)
        if (
            url
            == "https://example.com/publicaciones/informe-de-pagos-minoristas-enero-de-2026/"
        ):
            return httpx.Response(200, text=enero_html)
        if (
            url
            == "https://example.com/publicaciones/informe-de-pagos-minoristas-marzo-de-2026/"
        ):
            return httpx.Response(200, text=marzo_html)
        return httpx.Response(404, text="not found")

    transport = httpx.MockTransport(handler)
    request = DiscoveryRequest(
        source_url="https://example.com/informe-de-pagos-minoristas",
        match_rules=[r"\.xlsx$"],
    )
    with httpx.Client(transport=transport) as client:
        result = discover_files(request, client=client)

    assert result.selected.url.endswith("series-informe-pagos-minoristas-2026-03.xlsx")
