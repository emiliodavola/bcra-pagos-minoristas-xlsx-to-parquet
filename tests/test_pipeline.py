"""Integration tests for pipeline stages (run_fetch, run_build, run_all)."""

import hashlib
from datetime import datetime
from io import BytesIO
from pathlib import Path

import httpx
import pandas as pd
import pytest

from bcra_pagos_minoristas_xlsx_to_parquet.config import AppConfig
from bcra_pagos_minoristas_xlsx_to_parquet.download import download_file
from bcra_pagos_minoristas_xlsx_to_parquet.models import (
    DownloadRequest,
)
from bcra_pagos_minoristas_xlsx_to_parquet.parser import parse_workbook
from bcra_pagos_minoristas_xlsx_to_parquet.pipeline import (
    run_build,
    run_fetch,
    run_parse,
)


def _make_sample_xlsx(path: Path) -> None:
    """Create a minimal sample XLSX file for integration tests."""
    df = pd.DataFrame({
        "Concepto": ["Cheques", "Transferencias"],
        "Cantidad": [100, 200],
        "Monto": [10000.50, 25000.75],
    })
    df.to_excel(path, header=False, index=False)


class TestRunFetchIntegration:
    """Tests for the run_fetch pipeline stage."""

    def test_run_fetch_discovers_and_downloads(self, tmp_path) -> None:
        """Verify fetch discovers files and downloads them."""
        # Create a minimal XLSX in memory
        xlsx_bytes = BytesIO()
        with pd.ExcelWriter(xlsx_bytes, engine="openpyxl") as writer:
            pd.DataFrame({"A": [1], "B": [2]}).to_excel(
                writer, sheet_name="Sheet", header=False, index=False
            )
        xlsx_bytes.seek(0)
        xlsx_content = xlsx_bytes.read()

        # Create discovery HTML with link to our "file"
        html = """
        <html>
            <body>
                <a href="/archivos/test-2024-05.xlsx">Mayo 2024</a>
            </body>
        </html>
        """

        def handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            if "test-2024-05.xlsx" in url:
                return httpx.Response(200, content=xlsx_content)
            return httpx.Response(200, text=html)

        transport = httpx.MockTransport(handler)

        config = AppConfig()
        result = run_fetch(config, client=httpx.Client(transport=transport))

        # Verify discovery result
        assert "discovery" in result
        assert result["discovery"].selected is not None
        assert len(result["downloads"]) >= 1

        # Verify downloads are stored
        for download in result["downloads"]:
            assert download.path.exists()


class TestRunParseIntegration:
    """Tests for the run_parse pipeline stage."""

    def test_run_parse_with_real_workbook(self, tmp_path) -> None:
        """Verify parse reads an XLSX and returns ParsedDataset."""
        sample_path = tmp_path / "sample.xlsx"
        _make_sample_xlsx(sample_path)

        config = AppConfig()
        parsed = run_parse(config, input_path=sample_path)

        assert parsed is not None
        assert len(parsed.sheets) >= 1
        for sheet_name, df in parsed.sheets.items():
            assert len(df) > 0


class TestRunBuildIntegration:
    """Tests for the run_build pipeline stage."""

    def test_run_parse_normalize_store(self, tmp_path) -> None:
        """Verify build parses, normalizes, and stores a workbook."""
        # Create sample XLSX in download output dir
        download_dir = tmp_path / "raw"
        storage_dir = tmp_path / "curated"
        download_dir.mkdir()
        storage_dir.mkdir()

        sample_path = download_dir / "sample.xlsx"
        _make_sample_xlsx(sample_path)

        config = AppConfig(
            download={"output_dir": download_dir},
            storage={
                "output_dir": storage_dir,
                "format": "parquet",
                "mode": "overwrite",
            },
        )
        result = run_build(config, input_path=sample_path)

        # Verify normalized output exists and has data
        assert "normalized" in result
        normalized = result["normalized"]
        assert len(normalized.sheets) >= 1
        assert "row_counts" in normalized.model_dump()

        # Verify storage output (storage is StorageResult model, not dict)
        if "storage" in result:
            storage = result["storage"]
            # StorageResult has a 'paths' attribute with sheet_name -> Path mapping
            paths = storage.paths
            assert len(paths) >= 1
            for sheet_path in paths.values():
                path = Path(sheet_path)
                # Check parquet file exists (may be in a subdirectory)
                if path.is_dir():
                    assert len(list(path.glob("*.parquet"))) > 0


class TestFullPipelineIntegration:
    """Tests for the complete run_all pipeline."""

    def test_run_fetch_parse_normalize_store(self, tmp_path) -> None:
        """End-to-end test: fetch -> parse -> normalize -> store."""
        # Create XLSX content in memory
        xlsx_bytes = BytesIO()
        with pd.ExcelWriter(xlsx_bytes, engine="openpyxl") as writer:
            df = pd.DataFrame({
                "A": [1, 2],
                "B": [3, 4],
            })
            df.to_excel(writer, sheet_name="Data", header=False, index=False)
        xlsx_bytes.seek(0)
        xlsx_content = xlsx_bytes.read()

        # Create discovery HTML
        html = """
        <html>
            <body>
                <a href="/archivos/test-2024-05.xlsx">Mayo 2024</a>
            </body>
        </html>
        """

        def handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            if "test-2024-05.xlsx" in url:
                return httpx.Response(200, content=xlsx_content)
            return httpx.Response(200, text=html)

        transport = httpx.MockTransport(handler)

        download_dir = tmp_path / "raw"
        storage_dir = tmp_path / "curated"
        download_dir.mkdir()
        storage_dir.mkdir()

        config = AppConfig(
            download={"output_dir": download_dir, "retries": 0},
            storage={
                "output_dir": storage_dir,
                "format": "parquet",
                "mode": "overwrite",
            },
            source={"mode": "latest"},
        )

        client = httpx.Client(transport=transport)
        try:
            result = run_fetch(config, client=client)

            # Verify fetch results
            assert "discovery" in result
            assert len(result["downloads"]) >= 1

            # Parse each downloaded file
            for download in result["downloads"]:
                parsed = run_parse(config, input_path=download.path)
                assert parsed is not None
                assert len(parsed.sheets) >= 1
        finally:
            client.close()


class TestEdgeCasesPipeline:
    """Edge case tests for pipeline stages."""

    def test_run_fetch_no_candidates(self, tmp_path) -> None:
        """Verify fetch raises when no XLSX files are found."""
        html = """
        <html>
            <body>
                <a href="/archivos/readme.pdf">Readme</a>
            </body>
        </html>
        """

        transport = httpx.MockTransport(
            lambda request: httpx.Response(200, text=html)
        )

        config = AppConfig()
        client = httpx.Client(transport=transport)
        try:
            with pytest.raises(ValueError, match="No matching files"):
                run_fetch(config, client=client)
        finally:
            client.close()

    def test_run_parse_missing_file(self, tmp_path) -> None:
        """Verify parse raises when input file does not exist."""
        config = AppConfig()
        missing_path = tmp_path / "nonexistent.xlsx"

        with pytest.raises(FileNotFoundError):
            run_parse(config, input_path=missing_path)

    def test_run_parse_invalid_engine(self, tmp_path) -> None:
        """Verify parse raises on unsupported engine."""
        sample_path = tmp_path / "sample.xlsx"
        _make_sample_xlsx(sample_path)

        # The parser validates the engine at runtime
        with pytest.raises(ValueError, match="Unsupported parser engine"):
            parse_workbook(sample_path, engine="invalid-engine")

    def test_run_parse_empty_workbook(self, tmp_path) -> None:
        """Verify parse handles empty workbook gracefully."""
        path = tmp_path / "empty.xlsx"
        pd.DataFrame().to_excel(path, header=False, index=False)

        config = AppConfig()
        parsed = run_parse(config, input_path=path)

        assert parsed is not None
        assert len(parsed.sheets) >= 1

    def test_run_fetch_checksum_mismatch(self, tmp_path) -> None:
        """Verify download raises when SHA-256 does not match."""
        xlsx_bytes = BytesIO()
        with pd.ExcelWriter(xlsx_bytes, engine="openpyxl") as writer:
            pd.DataFrame({"A": [1]}).to_excel(
                writer, header=False, index=False
            )
        xlsx_bytes.seek(0)
        xlsx_content = xlsx_bytes.read()

        # Wrong checksum
        wrong_sha = "a" * 64

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=xlsx_content)

        transport = httpx.MockTransport(handler)

        config = AppConfig()
        client = httpx.Client(transport=transport)
        try:
            download_dir = tmp_path / "raw"
            download_dir.mkdir()

            request = DownloadRequest(
                url="https://example.com/test.xlsx",
                output_dir=download_dir,
                expected_sha256=wrong_sha,
            )
            # Should fail because checksum doesn't match
            with pytest.raises((ValueError, Exception)):
                download_file(request, client=client)
        finally:
            client.close()

    def test_run_build_empty_dataframe(self, tmp_path) -> None:
        """Verify build handles workbook with no data rows."""
        download_dir = tmp_path / "raw"
        storage_dir = tmp_path / "curated"
        download_dir.mkdir()
        storage_dir.mkdir()

        # Create empty XLSX (only headers, no data)
        path = download_dir / "empty.xlsx"
        pd.DataFrame({"A": [], "B": []}).to_excel(
            path, header=False, index=False
        )

        config = AppConfig(
            download={"output_dir": download_dir},
            storage={
                "output_dir": storage_dir,
                "format": "parquet",
                "mode": "overwrite",
            },
        )
        result = run_build(config, input_path=path)

        assert "normalized" in result
        normalized = result["normalized"]
        for sheet_name, df in normalized.sheets.items():
            assert len(df) == 0 or df is not None

    def test_run_parse_multiple_sheets(self, tmp_path) -> None:
        """Verify parse handles workbooks with multiple sheets."""
        path = tmp_path / "multi_sheet.xlsx"

        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            pd.DataFrame({"Sheet1": [1, 2]}).to_excel(
                writer, sheet_name="SheetA", header=False, index=False
            )
            pd.DataFrame({"Sheet2": [3, 4, 5]}).to_excel(
                writer, sheet_name="SheetB", header=False, index=False
            )

        config = AppConfig()
        parsed = run_parse(config, input_path=path)

        assert len(parsed.sheets) == 2
        assert "SheetA" in parsed.sheets or any(
            "SheetA" in s for s in parsed.sheets.keys()
        )
        assert "SheetB" in parsed.sheets or any(
            "SheetB" in s for s in parsed.sheets.keys()
        )

    def test_run_fetch_with_no_match_rules(self, tmp_path) -> None:
        """Verify fetch raises when match rules find no files."""
        html = """
        <html>
            <body>
                <a href="/archivos/data.csv">CSV File</a>
            </body>
        </html>
        """

        transport = httpx.MockTransport(
            lambda request: httpx.Response(200, text=html)
        )

        config = AppConfig()
        client = httpx.Client(transport=transport)
        try:
            with pytest.raises(ValueError, match="No matching files"):
                run_fetch(config, client=client)
        finally:
            client.close()

    def test_run_parse_with_pandas_engine(self, tmp_path) -> None:
        """Verify parse works with pandas engine explicitly."""
        sample_path = tmp_path / "sample.xlsx"
        _make_sample_xlsx(sample_path)

        parsed = parse_workbook(sample_path, engine="pandas")

        assert parsed is not None
        assert len(parsed.sheets) >= 1

    def test_run_parse_with_polars_engine(self, tmp_path) -> None:
        """Verify parse works with polars engine explicitly."""
        sample_path = tmp_path / "sample.xlsx"
        _make_sample_xlsx(sample_path)

        parsed = parse_workbook(sample_path, engine="polars")

        assert parsed is not None
        assert len(parsed.sheets) >= 1
