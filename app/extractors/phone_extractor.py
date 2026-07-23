"""
Phone number extractor using the `phonenumbers` library.
Returns ExtractedValue objects — never plain strings.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

import phonenumbers
from phonenumbers import NumberParseException, PhoneNumberFormat

from app.logging import get_logger
from app.schemas.email_schema import ExtractedValue

logger = get_logger(__name__)


class PhoneExtractor:
    """Extract and normalize phone numbers from text."""

    def extract(
        self, text: str, source_url: str, default_region: str = "US"
    ) -> list[ExtractedValue]:
        """
        Extract phone numbers from text.
        Returns list of ExtractedValue with E.164 formatted numbers.
        """
        results: list[ExtractedValue] = []
        seen: set[str] = set()

        # Use phonenumbers library's findall
        for match in phonenumbers.PhoneNumberMatcher(text, default_region):
            try:
                number = match.number
                formatted = phonenumbers.format_number(number, PhoneNumberFormat.E164)
                if formatted not in seen:
                    seen.add(formatted)
                    is_valid = phonenumbers.is_valid_number(number)
                    results.append(
                        ExtractedValue(
                            value=formatted,
                            confidence=85 if is_valid else 40,
                            source=source_url,
                            method="phonenumbers_lib",
                            timestamp=datetime.now(timezone.utc),
                        )
                    )
            except NumberParseException:
                continue

        return results
