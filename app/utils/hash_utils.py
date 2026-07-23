"""
Hash utilities for deduplication.
Uses SHA-256 to generate stable, deterministic hashes.
"""

from __future__ import annotations

import hashlib


def sha256_hex(value: str) -> str:
    """
    Return the SHA-256 hex digest of a string.
    Used for email deduplication — normalizes before hashing.
    """
    normalized = value.strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def email_hash(address: str) -> str:
    """
    Compute a deduplication hash for an email address.
    Normalizes to lowercase before hashing.
    """
    return sha256_hex(address.strip().lower())


def domain_hash(domain: str) -> str:
    """
    Compute a deduplication hash for a domain.
    """
    return sha256_hex(domain.strip().lower())


def content_hash(content: str) -> str:
    """
    Compute a hash of HTML/text content for caching.
    """
    return sha256_hex(content)
