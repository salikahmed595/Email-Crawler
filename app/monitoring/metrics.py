"""
In-process metrics counters — tracks all key operational metrics.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from threading import Lock


@dataclass
class Metrics:
    """Thread-safe counters for operational metrics."""

    _lock: Lock = field(default_factory=Lock, init=False, repr=False)

    jobs_processed: int = 0
    jobs_failed: int = 0
    jobs_queued: int = 0
    emails_discovered: int = 0
    emails_valid: int = 0
    emails_invalid: int = 0
    emails_duplicate: int = 0
    domains_crawled: int = 0
    domains_failed: int = 0
    pages_crawled: int = 0
    playwright_invocations: int = 0
    pdf_invocations: int = 0
    ocr_invocations: int = 0
    _start_time: float = field(default_factory=time.monotonic, init=False)

    def increment(self, field_name: str, amount: int = 1) -> None:
        with self._lock:
            current = getattr(self, field_name, 0)
            setattr(self, field_name, current + amount)

    def to_dict(self) -> dict:
        elapsed = time.monotonic() - self._start_time
        with self._lock:
            return {
                "uptime_seconds": round(elapsed, 1),
                "jobs_processed": self.jobs_processed,
                "jobs_failed": self.jobs_failed,
                "jobs_queued": self.jobs_queued,
                "emails_discovered": self.emails_discovered,
                "emails_valid": self.emails_valid,
                "emails_invalid": self.emails_invalid,
                "emails_duplicate": self.emails_duplicate,
                "domains_crawled": self.domains_crawled,
                "domains_failed": self.domains_failed,
                "pages_crawled": self.pages_crawled,
                "playwright_invocations": self.playwright_invocations,
                "pdf_invocations": self.pdf_invocations,
                "ocr_invocations": self.ocr_invocations,
                "jobs_per_minute": round(
                    self.jobs_processed / max(elapsed / 60, 1), 2
                ),
            }


# Global metrics singleton
_metrics: Metrics | None = None


def get_metrics() -> Metrics:
    global _metrics
    if _metrics is None:
        _metrics = Metrics()
    return _metrics
