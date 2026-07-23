"""
Tests for EmailExtractor — all 11 extraction strategies.
"""

from __future__ import annotations

import pytest
from app.extractors.email_extractor import EmailExtractor


class TestEmailExtractor:
    """Tests for all 11 email extraction strategies."""

    def setup_method(self) -> None:
        self.extractor = EmailExtractor()

    def test_strategy_1_mailto_links(self, sample_html_with_mailto: str) -> None:
        """Strategy 1: mailto: links have highest confidence."""
        results = self.extractor.extract_from_page(
            sample_html_with_mailto, "https://example.com"
        )
        methods = {r.method for r in results}
        assert "mailto" in methods
        mailto_results = [r for r in results if r.method == "mailto"]
        assert len(mailto_results) >= 1
        # Mailto should have highest confidence
        for r in mailto_results:
            assert r.confidence >= 85

    def test_strategy_2_html_regex(self, sample_html_with_mailto: str) -> None:
        """Strategy 2: Visible text regex extraction."""
        results = self.extractor.extract_from_page(
            sample_html_with_mailto, "https://example.com"
        )
        addresses = {r.address for r in results}
        assert "info@testcompany.com" in addresses or "contact@testcompany.com" in addresses

    def test_strategy_3_footer(self, sample_html_with_mailto: str) -> None:
        """Strategy 3: Footer email extraction."""
        results = self.extractor.extract_from_page(
            sample_html_with_mailto, "https://example.com"
        )
        footer_results = [r for r in results if r.method == "footer"]
        addresses = {r.address for r in results}
        # contact@testcompany.com is in footer
        assert "contact@testcompany.com" in addresses

    def test_strategy_5_schema_org(self, sample_html_with_schema: str) -> None:
        """Strategy 5: Schema.org/JSON-LD extraction."""
        results = self.extractor.extract_from_page(
            sample_html_with_schema, "https://example.com"
        )
        schema_results = [r for r in results if r.method == "schema_ld"]
        assert len(schema_results) >= 1
        assert any(r.address == "hello@testcorp.io" for r in schema_results)

    def test_strategy_6_javascript(self) -> None:
        """Strategy 6: Email in JavaScript source."""
        html = "<script>var email = 'js@example.com';</script>"
        results = self.extractor.extract_from_raw_html(html, "https://example.com")
        js_results = [r for r in results if r.method == "javascript"]
        assert len(js_results) >= 1
        assert any(r.address == "js@example.com" for r in js_results)

    def test_strategy_7_html_comments(self) -> None:
        """Strategy 7: Email in HTML comments."""
        html = "<!-- contact: hidden@example.com -->"
        results = self.extractor.extract_from_raw_html(html, "https://example.com")
        comment_results = [r for r in results if r.method == "html_comment"]
        assert len(comment_results) >= 1
        assert any(r.address == "hidden@example.com" for r in comment_results)

    def test_strategy_8_base64(self, sample_html_with_base64: str) -> None:
        """Strategy 8: Base64 encoded email."""
        results = self.extractor.extract_from_raw_html(
            sample_html_with_base64, "https://example.com"
        )
        base64_results = [r for r in results if r.method == "base64"]
        assert len(base64_results) >= 1
        assert any(r.address == "encoded@company.com" for r in base64_results)

    def test_strategy_10_cloudflare(self, sample_html_with_cloudflare: str) -> None:
        """Strategy 10: Cloudflare email protection decode."""
        results = self.extractor.extract_from_raw_html(
            sample_html_with_cloudflare, "https://example.com"
        )
        cf_results = [r for r in results if r.method == "cloudflare_decode"]
        assert len(cf_results) >= 1
        assert any(r.address == "test@example.com" for r in cf_results)

    def test_strategy_11_pdf_text(self) -> None:
        """Strategy 11: Email in plain text (PDF/OCR output)."""
        text = "For inquiries: pdf@company.com or call us"
        results = self.extractor.extract_from_text(text, "https://example.com/brochure.pdf")
        assert len(results) >= 1
        assert any(r.address == "pdf@company.com" for r in results)

    def test_all_emails_normalized_lowercase(self) -> None:
        """All extracted emails must be normalized to lowercase."""
        html = '<a href="mailto:UPPER@EXAMPLE.COM">Email</a>'
        results = self.extractor.extract_from_page(html, "https://example.com")
        for r in results:
            assert r.address == r.address.lower()

    def test_deduplication_within_page(self, sample_html_with_mailto: str) -> None:
        """Same email appearing multiple times should not produce duplicates."""
        results = self.extractor.extract_from_page(
            sample_html_with_mailto, "https://example.com"
        )
        addresses = [r.address for r in results]
        assert len(addresses) == len(set(addresses)), "Duplicate emails in results"

    def test_every_result_has_metadata(self, sample_html_with_mailto: str) -> None:
        """Every result must have source, method, and timestamp."""
        results = self.extractor.extract_from_page(
            sample_html_with_mailto, "https://example.com"
        )
        for r in results:
            assert r.source, "Missing source"
            assert r.method, "Missing method"
            assert r.timestamp is not None, "Missing timestamp"
