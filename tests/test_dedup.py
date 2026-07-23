"""
Tests for the deduplication service.
"""

from __future__ import annotations

from app.services.dedup_service import DedupService


class TestDedupService:
    def test_new_email_not_duplicate(self) -> None:
        dedup = DedupService()
        is_dup, _ = dedup.check_and_mark("unique@example.com")
        assert not is_dup

    def test_same_email_is_duplicate(self) -> None:
        dedup = DedupService()
        dedup.check_and_mark("test@example.com")
        is_dup, _ = dedup.check_and_mark("test@example.com")
        assert is_dup

    def test_different_case_is_duplicate(self) -> None:
        """Normalization: UPPER@EXAMPLE.COM == upper@example.com."""
        dedup = DedupService()
        dedup.check_and_mark("TEST@EXAMPLE.COM")
        is_dup, _ = dedup.check_and_mark("test@example.com")
        assert is_dup

    def test_different_emails_not_duplicate(self) -> None:
        dedup = DedupService()
        dedup.check_and_mark("one@example.com")
        is_dup, _ = dedup.check_and_mark("two@example.com")
        assert not is_dup

    def test_reset_clears_seen(self) -> None:
        dedup = DedupService()
        dedup.check_and_mark("test@example.com")
        dedup.reset()
        is_dup, _ = dedup.check_and_mark("test@example.com")
        assert not is_dup

    def test_hash_is_64_chars(self) -> None:
        dedup = DedupService()
        _, h = dedup.check_and_mark("test@example.com")
        assert len(h) == 64

    def test_seen_count(self) -> None:
        dedup = DedupService()
        dedup.check_and_mark("a@example.com")
        dedup.check_and_mark("b@example.com")
        dedup.check_and_mark("a@example.com")  # duplicate
        assert dedup.seen_count == 2
