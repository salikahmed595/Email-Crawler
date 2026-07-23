"""
Confidence engine — deterministic confidence scoring based on evidence signals.

Inputs: extraction method, validation results, source quality.
Output: integer 0-100 confidence score.

No AI. No randomness. Same inputs always produce the same output.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ConfidenceSignals:
    """
    All positive and negative signals used to calculate confidence.
    Mirrors the framework.md confidence model exactly.
    """

    # Positive signals
    found_via_mailto: bool = False
    found_on_contact_page: bool = False
    found_multiple_times: bool = False
    mx_valid: bool = False
    smtp_valid: bool | None = None
    company_domain_match: bool = False
    found_via_schema: bool = False
    found_via_official_website: bool = False

    # Negative signals
    is_disposable: bool = False
    is_malformed: bool = False
    is_role_based: bool = False
    is_temporary: bool = False
    no_mx_record: bool = False
    unknown_domain: bool = False
    third_party_source: bool = False
    found_via_ocr: bool = False
    found_via_comment: bool = False

    # Extraction method
    extraction_method: str = ""


class ConfidenceEngine:
    """
    Calculates deterministic confidence scores for extracted emails.
    Called after extraction, before storage.
    """

    # Score weights
    _POSITIVE_WEIGHTS = {
        "found_via_mailto": 25,
        "found_on_contact_page": 15,
        "found_multiple_times": 10,
        "mx_valid": 15,
        "smtp_valid_true": 10,
        "company_domain_match": 10,
        "found_via_schema": 10,
        "found_via_official_website": 5,
    }

    _NEGATIVE_WEIGHTS = {
        "is_disposable": -50,
        "is_malformed": -60,
        "is_role_based": -15,
        "is_temporary": -40,
        "no_mx_record": -20,
        "unknown_domain": -15,
        "third_party_source": -10,
        "found_via_ocr": -10,
        "found_via_comment": -5,
    }

    # Method-based base scores
    _METHOD_BASE_SCORES = {
        "mailto": 80,
        "schema_ld": 75,
        "html_regex": 60,
        "footer": 65,
        "header": 55,
        "javascript": 50,
        "base64": 55,
        "cloudflare_decode": 70,
        "unicode_obfuscation": 50,
        "html_comment": 45,
        "pdf_text": 50,
        "ocr": 35,
        "phonenumbers_lib": 70,
    }

    def calculate(self, signals: ConfidenceSignals) -> int:
        """
        Calculate a confidence score from 0-100.
        Deterministic: same inputs → same output.
        """
        # Start from method-based base score
        score = self._METHOD_BASE_SCORES.get(signals.extraction_method, 50)

        # Apply positive signals
        if signals.found_via_mailto:
            score += self._POSITIVE_WEIGHTS["found_via_mailto"]
        if signals.found_on_contact_page:
            score += self._POSITIVE_WEIGHTS["found_on_contact_page"]
        if signals.found_multiple_times:
            score += self._POSITIVE_WEIGHTS["found_multiple_times"]
        if signals.mx_valid:
            score += self._POSITIVE_WEIGHTS["mx_valid"]
        if signals.smtp_valid is True:
            score += self._POSITIVE_WEIGHTS["smtp_valid_true"]
        if signals.company_domain_match:
            score += self._POSITIVE_WEIGHTS["company_domain_match"]
        if signals.found_via_schema:
            score += self._POSITIVE_WEIGHTS["found_via_schema"]
        if signals.found_via_official_website:
            score += self._POSITIVE_WEIGHTS["found_via_official_website"]

        # Apply negative signals
        if signals.is_disposable:
            score += self._NEGATIVE_WEIGHTS["is_disposable"]
        if signals.is_malformed:
            score += self._NEGATIVE_WEIGHTS["is_malformed"]
        if signals.is_role_based:
            score += self._NEGATIVE_WEIGHTS["is_role_based"]
        if signals.is_temporary:
            score += self._NEGATIVE_WEIGHTS["is_temporary"]
        if signals.no_mx_record:
            score += self._NEGATIVE_WEIGHTS["no_mx_record"]
        if signals.unknown_domain:
            score += self._NEGATIVE_WEIGHTS["unknown_domain"]
        if signals.third_party_source:
            score += self._NEGATIVE_WEIGHTS["third_party_source"]
        if signals.found_via_ocr:
            score += self._NEGATIVE_WEIGHTS["found_via_ocr"]
        if signals.found_via_comment:
            score += self._NEGATIVE_WEIGHTS["found_via_comment"]

        return max(0, min(100, score))

    def build_signals_from_extraction(
        self,
        extraction_method: str,
        validation_result: Any,
        domain: str,
        email_address: str,
        occurrence_count: int = 1,
        page_url: str = "",
    ) -> ConfidenceSignals:
        """
        Build ConfidenceSignals from extraction + validation context.
        """
        signals = ConfidenceSignals(extraction_method=extraction_method)

        # Extraction method signals
        signals.found_via_mailto = extraction_method == "mailto"
        signals.found_via_schema = extraction_method in ("schema_ld", "json_ld")
        signals.found_via_ocr = extraction_method == "ocr"
        signals.found_via_comment = extraction_method == "html_comment"

        # Contact page signal
        from app.utils.url_utils import is_contact_page
        if page_url:
            signals.found_on_contact_page = is_contact_page(page_url)

        # Multiple occurrences
        signals.found_multiple_times = occurrence_count > 1

        # Domain match — email is from the same domain as the company
        if "@" in email_address:
            email_domain = email_address.rsplit("@", 1)[-1].lower()
            signals.company_domain_match = email_domain == domain.lower()

        # Validation signals
        if validation_result:
            signals.mx_valid = getattr(validation_result, "mx_valid", False)
            signals.smtp_valid = getattr(validation_result, "smtp_valid", None)
            signals.is_disposable = getattr(validation_result, "is_disposable", False)
            signals.is_role_based = getattr(validation_result, "is_role_based", False)
            signals.is_malformed = not getattr(validation_result, "is_valid_syntax", True)
            signals.no_mx_record = not signals.mx_valid

        return signals
