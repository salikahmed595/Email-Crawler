"""
Tests for the Confidence Engine — deterministic scoring.
"""

from __future__ import annotations

from app.services.confidence_engine import ConfidenceEngine, ConfidenceSignals


class TestConfidenceEngine:
    def setup_method(self) -> None:
        self.engine = ConfidenceEngine()

    def test_score_in_range(self) -> None:
        signals = ConfidenceSignals(extraction_method="mailto")
        score = self.engine.calculate(signals)
        assert 0 <= score <= 100

    def test_mailto_high_score(self) -> None:
        signals = ConfidenceSignals(
            extraction_method="mailto",
            found_via_mailto=True,
            mx_valid=True,
            company_domain_match=True,
        )
        score = self.engine.calculate(signals)
        assert score >= 80, f"Mailto + MX + domain match should be high confidence, got {score}"

    def test_disposable_low_score(self) -> None:
        signals = ConfidenceSignals(
            extraction_method="html_regex",
            is_disposable=True,
        )
        score = self.engine.calculate(signals)
        assert score < 30, f"Disposable should be low confidence, got {score}"

    def test_ocr_lower_than_mailto(self) -> None:
        ocr_signals = ConfidenceSignals(extraction_method="ocr", found_via_ocr=True)
        mailto_signals = ConfidenceSignals(
            extraction_method="mailto", found_via_mailto=True
        )
        assert self.engine.calculate(mailto_signals) > self.engine.calculate(ocr_signals)

    def test_deterministic(self) -> None:
        """Same inputs must always produce same output."""
        signals = ConfidenceSignals(
            extraction_method="footer",
            mx_valid=True,
            is_role_based=True,
        )
        score1 = self.engine.calculate(signals)
        score2 = self.engine.calculate(signals)
        assert score1 == score2

    def test_no_negative_score(self) -> None:
        signals = ConfidenceSignals(
            extraction_method="ocr",
            is_disposable=True,
            is_malformed=True,
            is_role_based=True,
            no_mx_record=True,
            found_via_ocr=True,
            third_party_source=True,
        )
        score = self.engine.calculate(signals)
        assert score >= 0

    def test_cloudflare_decode_higher_than_comment(self) -> None:
        cf_signals = ConfidenceSignals(extraction_method="cloudflare_decode")
        comment_signals = ConfidenceSignals(extraction_method="html_comment", found_via_comment=True)
        assert self.engine.calculate(cf_signals) > self.engine.calculate(comment_signals)
