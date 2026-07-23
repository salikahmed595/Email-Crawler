"""
Deduplication service — prevents duplicate email storage.
Uses SHA-256 hashing for O(1) dedup checks.
"""

from __future__ import annotations

from app.logging import get_logger
from app.utils.hash_utils import email_hash

logger = get_logger(__name__)


class DedupService:
    """
    Manages email deduplication within a single crawl session.
    DB-level dedup is enforced by the unique constraint on (address_hash, company_id).
    This service provides in-memory dedup to avoid redundant DB writes.
    """

    def __init__(self) -> None:
        self._seen: set[str] = set()

    def is_duplicate(self, address: str) -> bool:
        """Check if an email address has been seen in this session."""
        h = email_hash(address)
        return h in self._seen

    def mark_seen(self, address: str) -> str:
        """
        Mark an email as seen and return its hash.
        Returns the hash for storage.
        """
        h = email_hash(address)
        self._seen.add(h)
        return h

    def check_and_mark(self, address: str) -> tuple[bool, str]:
        """
        Check if duplicate AND mark as seen atomically.
        Returns (is_duplicate, hash).
        """
        h = email_hash(address)
        if h in self._seen:
            return True, h
        self._seen.add(h)
        return False, h

    def reset(self) -> None:
        """Clear the seen set (e.g., between company crawls)."""
        self._seen.clear()

    @property
    def seen_count(self) -> int:
        return len(self._seen)
