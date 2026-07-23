"""
Tests for ImportService — CSV parsing and sanitization.
"""

from __future__ import annotations

import pytest
from app.services.import_service import ImportService


class TestImportService:
    def setup_method(self) -> None:
        self.service = ImportService()

    @pytest.mark.asyncio
    async def test_basic_csv_import(self) -> None:
        csv = "company_name,website\nTest Corp,testcorp.io\n"
        # Without DB — just test domain detection and normalization
        assert self.service._detect_column(["company_name", "website"], {"website", "domain"}) == "website"

    def test_detect_domain_column_website(self) -> None:
        headers = ["company_name", "website", "phone"]
        result = self.service._detect_column(headers, {"website", "domain", "url"})
        assert result == "website"

    def test_detect_domain_column_domain(self) -> None:
        headers = ["name", "domain", "address"]
        result = self.service._detect_column(headers, {"domain", "website", "url"})
        assert result == "domain"

    def test_detect_name_column(self) -> None:
        headers = ["company_name", "website"]
        result = self.service._detect_column(headers, {"company_name", "name", "business_name"})
        assert result == "company_name"

    def test_sanitize_strips_null_bytes(self) -> None:
        result = self.service._sanitize_string("Test\x00Company")
        assert "\x00" not in result

    def test_sanitize_strips_whitespace(self) -> None:
        result = self.service._sanitize_string("  Company Name  ")
        assert result == "Company Name"

    def test_sanitize_truncates_long_strings(self) -> None:
        long_string = "A" * 1000
        result = self.service._sanitize_string(long_string)
        assert len(result) <= 500

    def test_no_domain_column_raises(self) -> None:
        """CSV with no domain-like column should fail with ValueError."""
        import asyncio
        csv = "company_name,phone\nTest Corp,123456\n"

        async def run():
            with pytest.raises(ValueError, match="domain"):
                await self.service.import_csv(csv)

        asyncio.run(run())
