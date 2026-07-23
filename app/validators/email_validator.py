"""
Email validator — 10-stage validation pipeline.

Stage 1:  Normalization
Stage 2:  Syntax check (RFC 5322)
Stage 3:  Domain format
Stage 4:  DNS resolution
Stage 5:  MX record check
Stage 6:  SMTP handshake (opt-in)
Stage 7:  Disposable email detection
Stage 8:  Role-based detection
Stage 9:  Duplicate detection
Stage 10: Confidence calculation

Each stage is independent and replaceable.
"""

from __future__ import annotations

import asyncio
import re
import smtplib
import socket
from typing import Any

from app.config import get_settings
from app.logging import get_logger
from app.schemas.email_schema import EmailValidationResult

logger = get_logger(__name__)

# RFC 5322 email syntax pattern
_SYNTAX_RE = re.compile(
    r"^[a-zA-Z0-9!#$%&'*+/=?^_`{|}~\-]+"
    r"(?:\.[a-zA-Z0-9!#$%&'*+/=?^_`{|}~\-]+)*"
    r"@"
    r"[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?"
    r"(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*"
    r"\.[a-zA-Z]{2,63}$"
)

# Role-based email prefixes
_ROLE_PREFIXES = frozenset({
    "info", "contact", "hello", "hi", "support", "help", "admin", "administrator",
    "webmaster", "postmaster", "hostmaster", "abuse", "noreply", "no-reply",
    "donotreply", "do-not-reply", "sales", "marketing", "billing", "accounts",
    "finance", "hr", "jobs", "careers", "press", "media", "pr", "legal",
    "privacy", "security", "team", "office", "general", "enquiries", "enquiry",
    "queries", "feedback", "newsletter", "subscriptions", "unsubscribe",
    "notifications", "alerts", "service", "services", "customerservice",
    "customer", "care", "reception", "shop", "store", "orders",
})

# Common disposable email domains (subset — expand as needed)
_DISPOSABLE_DOMAINS = frozenset({
    "mailinator.com", "guerrillamail.com", "10minutemail.com", "tempmail.com",
    "throwaway.email", "yopmail.com", "sharklasers.com", "guerrillamailblock.com",
    "grr.la", "guerrillamail.info", "guerrillamail.biz", "guerrillamail.de",
    "guerrillamail.net", "guerrillamail.org", "spam4.me", "trashmail.com",
    "trashmail.me", "trashmail.net", "dispostable.com", "fakeinbox.com",
    "mailnull.com", "spamgourmet.com", "spamgourmet.net", "spamgourmet.org",
    "maildrop.cc", "discard.email", "nospamfor.us", "throwam.com",
    "getnada.com", "mohmal.com", "inboxbear.com", "tempinbox.com",
    "tempr.email", "temp-mail.org", "mailtemp.net", "emailtemporario.com.br",
})

# RFC 2606 reserved/placeholder domains — these turn up constantly in demo
# code, docs, and test fixtures shipped in a site's live JS bundle (e.g.
# "jane.diaz@example.com"). They are never a real contact address, so they
# must never be reported as a discovered lead.
_PLACEHOLDER_DOMAINS = frozenset({
    "example.com", "example.org", "example.net", "example.edu",
    "test.com", "test.org", "domain.com", "yourdomain.com",
    "your-domain.com", "website.com", "mywebsite.com", "placeholder.com",
    "invalid.com", "localhost.com",
})


class EmailValidator:
    """
    10-stage email validation pipeline.
    Each stage can be toggled independently via config.
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._dns_cache: dict[str, bool] = {}
        self._mx_cache: dict[str, list[str]] = {}

    async def validate(self, address: str) -> EmailValidationResult:
        """
        Run the full 10-stage validation pipeline on an email address.
        Returns EmailValidationResult with all stage results and confidence.
        """
        result = EmailValidationResult(address=address)

        # Stage 1: Normalization
        address = self._stage1_normalize(address)
        result.address = address

        # Stage 2: Syntax
        result.is_valid_syntax = self._stage2_syntax(address)
        if not result.is_valid_syntax:
            result.validation_status = "invalid"
            result.notes.append("Failed syntax check")
            result.confidence = 0
            return result

        # Extract domain
        parts = address.rsplit("@", 1)
        if len(parts) != 2:
            result.validation_status = "invalid"
            return result
        local_part, domain = parts[0], parts[1].lower()

        # Stage 3: Domain format
        result.is_valid_domain = self._stage3_domain_format(domain)
        if not result.is_valid_domain:
            result.validation_status = "invalid"
            result.notes.append("Invalid domain format")
            result.confidence = 5
            return result

        # Stage 4: DNS
        dns_ok = await self._stage4_dns(domain)
        if not dns_ok:
            result.notes.append("DNS resolution failed")

        # Stage 5: MX record
        mx_checked = self._settings.mx_validation_enabled
        if mx_checked:
            result.mx_valid = await self._stage5_mx(domain)
            if not result.mx_valid:
                result.notes.append("No MX record")
        else:
            # Not actually checked — don't let downstream scoring treat this
            # as a confirmed-valid signal.
            result.mx_valid = True

        # Stage 6: SMTP (opt-in only)
        if self._settings.smtp_validation_enabled and result.mx_valid:
            result.smtp_valid = await self._stage6_smtp(address, domain)
            if result.smtp_valid is False:
                result.notes.append("SMTP rejected")
        else:
            result.smtp_valid = None  # Not checked

        # Stage 7: Disposable detection
        result.is_disposable = self._stage7_disposable(domain)
        if result.is_disposable:
            result.notes.append("Disposable email domain")

        # Stage 8: Role-based detection
        result.is_role_based = self._stage8_role_based(local_part)
        if result.is_role_based:
            result.notes.append("Role-based address")

        # Stage 9: Duplicate detection is done at DB level (by address_hash)
        # Stage 10: Confidence calculation
        result.confidence = self._stage10_confidence(result, mx_checked=mx_checked)
        result.validation_status = self._determine_status(result)

        return result

    # -------------------------------------------------------------------------
    # Stages
    # -------------------------------------------------------------------------

    def _stage1_normalize(self, address: str) -> str:
        """Stage 1: Normalize — strip whitespace, lowercase."""
        return address.strip().lower()

    def _stage2_syntax(self, address: str) -> bool:
        """Stage 2: Syntax check against RFC 5322 pattern."""
        if not address or len(address) > 320:
            return False
        local_part = address.rsplit("@", 1)[0]
        if len(local_part) > 64:  # RFC 5321 local-part length limit
            return False
        return bool(_SYNTAX_RE.match(address))

    def _stage3_domain_format(self, domain: str) -> bool:
        """Stage 3: Domain format validation."""
        if not domain or len(domain) > 253:
            return False
        if "." not in domain:
            return False
        parts = domain.split(".")
        for part in parts:
            if not part or len(part) > 63:
                return False
            if not re.match(r"^[a-zA-Z0-9\-]+$", part):
                return False
            if part.startswith("-") or part.endswith("-"):
                return False
        tld = parts[-1]
        return len(tld) >= 2

    async def _stage4_dns(self, domain: str) -> bool:
        """Stage 4: DNS resolution check."""
        if domain in self._dns_cache:
            return self._dns_cache[domain]
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None, socket.getaddrinfo, domain, None
            )
            self._dns_cache[domain] = True
            return True
        except (socket.gaierror, OSError):
            self._dns_cache[domain] = False
            return False
        except Exception:
            self._dns_cache[domain] = False
            return False

    async def _stage5_mx(self, domain: str) -> bool:
        """Stage 5: MX record check using dnspython."""
        if domain in self._mx_cache:
            return bool(self._mx_cache[domain])
        try:
            import dns.asyncresolver
            import dns.exception

            resolver = dns.asyncresolver.Resolver()
            resolver.lifetime = self._settings.dns_timeout
            answers = await resolver.resolve(domain, "MX")
            mx_hosts = [str(r.exchange).rstrip(".") for r in answers]
            self._mx_cache[domain] = mx_hosts
            return len(mx_hosts) > 0
        except Exception:
            self._mx_cache[domain] = []
            return False

    async def _stage6_smtp(self, address: str, domain: str) -> bool | None:
        """
        Stage 6: SMTP handshake validation (opt-in only).
        Connects to MX server and checks RCPT TO.
        Returns True/False/None (None = inconclusive).
        """
        mx_hosts = self._mx_cache.get(domain, [])
        if not mx_hosts:
            return None

        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None, self._smtp_check, address, mx_hosts[0]
            )
        except Exception:
            return None

    def _smtp_check(self, address: str, mx_host: str) -> bool | None:
        """Synchronous SMTP check — runs in executor."""
        try:
            with smtplib.SMTP(mx_host, timeout=self._settings.smtp_timeout) as smtp:
                smtp.helo("verify.local")
                smtp.mail("verify@verify.local")
                code, _ = smtp.rcpt(address)
                return code == 250
        except smtplib.SMTPRecipientsRefused:
            return False
        except Exception:
            return None

    def _stage7_disposable(self, domain: str) -> bool:
        """
        Stage 7: Check against known disposable and RFC 2606 placeholder
        domain lists. Placeholder domains (example.com, etc.) are treated
        the same as disposable — neither is ever a real contact address.
        """
        domain = domain.lower()
        return domain in _DISPOSABLE_DOMAINS or domain in _PLACEHOLDER_DOMAINS

    def _stage8_role_based(self, local_part: str) -> bool:
        """Stage 8: Check if this is a role-based address."""
        return local_part.lower() in _ROLE_PREFIXES

    def _stage10_confidence(self, result: EmailValidationResult, mx_checked: bool) -> int:
        """
        Stage 10: Calculate deterministic confidence score (0-100).
        Based on evidence — never AI-generated.
        """
        score = 50  # baseline

        # Positive signals
        if result.is_valid_syntax:
            score += 10
        if result.is_valid_domain:
            score += 10
        if mx_checked and result.mx_valid:
            score += 15
        if result.smtp_valid is True:
            score += 10

        # Negative signals
        if result.is_role_based:
            score -= 15
        if not result.is_valid_syntax:
            score = 0
        if not result.is_valid_domain:
            score = max(score - 30, 0)
        if mx_checked and not result.mx_valid:
            score = max(score - 20, 0)
        if result.smtp_valid is False:
            score = max(score - 25, 0)

        # Disposable/temporary domains are a hard negative signal — cap
        # the score low regardless of other positive signals.
        if result.is_disposable:
            score = min(score, 20)

        return max(0, min(100, score))

    def _determine_status(self, result: EmailValidationResult) -> str:
        """Determine overall validation status from all stage results."""
        if not result.is_valid_syntax or not result.is_valid_domain:
            return "invalid"
        if result.is_disposable:
            return "invalid"
        if result.smtp_valid is False:
            return "invalid"
        if result.mx_valid and result.confidence >= 60:
            return "valid"
        if result.confidence >= 40:
            return "uncertain"
        return "invalid"
