"""
Test fixtures — mock HTTP server, in-memory DB, mock Redis.
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

# Use SQLite for tests (no PostgreSQL needed)
os.environ.setdefault(
    "DATABASE_URL", "sqlite+aiosqlite:///./test_db.sqlite"
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/1")
os.environ.setdefault("APP_ENV", "testing")
os.environ.setdefault("PLAYWRIGHT_ENABLED", "false")
os.environ.setdefault("PDF_ENABLED", "false")
os.environ.setdefault("OCR_ENABLED", "false")
os.environ.setdefault("SMTP_VALIDATION_ENABLED", "false")
os.environ.setdefault("MX_VALIDATION_ENABLED", "false")
os.environ.setdefault("LOG_LEVEL", "WARNING")


@pytest.fixture
def sample_html_with_mailto() -> str:
    return """
    <html>
    <head><title>Test Company</title></head>
    <body>
        <header><a href="mailto:support@testcompany.com">Email Us</a></header>
        <main>
            <p>Contact us at <a href="mailto:sales@testcompany.com">sales@testcompany.com</a></p>
            <p>Or reach info@testcompany.com directly</p>
        </main>
        <footer>
            <p>© 2024 Test Company | contact@testcompany.com</p>
        </footer>
    </body>
    </html>
    """


@pytest.fixture
def sample_html_with_schema() -> str:
    return """
    <html>
    <script type="application/ld+json">
    {
        "@type": "Organization",
        "name": "Test Corp",
        "email": "hello@testcorp.io",
        "address": {
            "@type": "PostalAddress",
            "streetAddress": "123 Main St",
            "addressLocality": "San Francisco",
            "addressRegion": "CA",
            "postalCode": "94105"
        }
    }
    </script>
    <body><p>Test Corp</p></body>
    </html>
    """


@pytest.fixture
def sample_html_with_cloudflare() -> str:
    # Cloudflare-protected email: test@example.com encoded
    # Key=0x14, encoded: 14 + (ord(c) ^ 0x14 for c in "test@example.com")
    email = "test@example.com"
    key = 0x14
    encoded = bytes([key] + [ord(c) ^ key for c in email]).hex()
    return f"""
    <html>
    <body>
        <a href="/cdn-cgi/l/email-protection" class="__cf_email__"
           data-cfemail="{encoded}">[email protected]</a>
    </body>
    </html>
    """


@pytest.fixture
def sample_html_obfuscated() -> str:
    return """
    <html>
    <body>
        <p>Contact us: admin [at] company [dot] org</p>
        <p>Also: billing at example dot com</p>
    </body>
    </html>
    """


@pytest.fixture
def sample_html_with_base64() -> str:
    import base64
    email_encoded = base64.b64encode(b"encoded@company.com").decode()
    return f"""
    <html>
    <body>
        <script>var e = "{email_encoded}";</script>
    </body>
    </html>
    """


@pytest.fixture
def valid_emails() -> list[str]:
    return [
        "user@example.com",
        "firstname.lastname@company.org",
        "user+tag@domain.co.uk",
        "test123@sub.domain.com",
    ]


@pytest.fixture
def invalid_emails() -> list[str]:
    return [
        "notanemail",
        "@nodomain.com",
        "noatsign.com",
        "double@@domain.com",
        "",
        "toolong" + "a" * 300 + "@domain.com",
    ]


@pytest.fixture
def disposable_emails() -> list[str]:
    return [
        "user@mailinator.com",
        "test@guerrillamail.com",
        "temp@10minutemail.com",
        "foo@yopmail.com",
    ]


@pytest.fixture
def role_based_emails() -> list[str]:
    return [
        "info@company.com",
        "support@company.com",
        "noreply@company.com",
        "admin@company.com",
        "sales@company.com",
    ]
