"""
Tests for URL and domain validators.
"""

from __future__ import annotations

import pytest
from app.validators.url_validator import UrlValidator
from app.validators.domain_validator import DomainValidator


class TestUrlValidator:
    def setup_method(self) -> None:
        self.validator = UrlValidator()

    def test_valid_https_url(self) -> None:
        valid, err = self.validator.validate("https://example.com")
        assert valid, err

    def test_valid_http_url(self) -> None:
        valid, err = self.validator.validate("http://example.com/path?q=1")
        assert valid, err

    def test_rejects_localhost(self) -> None:
        valid, _ = self.validator.validate("http://localhost:8080")
        assert not valid

    def test_rejects_private_ip(self) -> None:
        valid, _ = self.validator.validate("http://192.168.1.1/admin")
        assert not valid

    def test_rejects_aws_metadata(self) -> None:
        valid, _ = self.validator.validate("http://169.254.169.254/latest/meta-data/")
        assert not valid

    def test_rejects_ftp(self) -> None:
        valid, _ = self.validator.validate("ftp://files.example.com")
        assert not valid

    def test_rejects_directory_traversal(self) -> None:
        valid, _ = self.validator.validate("https://example.com/../etc/passwd")
        assert not valid

    def test_rejects_null_byte(self) -> None:
        valid, _ = self.validator.validate("https://example.com/path\x00")
        assert not valid

    def test_empty_url(self) -> None:
        valid, _ = self.validator.validate("")
        assert not valid


class TestDomainValidator:
    def setup_method(self) -> None:
        self.validator = DomainValidator()

    def test_valid_domain(self) -> None:
        # Note: example.com is deliberately blocklisted (RFC 2606 placeholder),
        # see test_rejects_placeholder — use a real-looking domain here instead.
        valid, _ = self.validator.validate("acme-widgets.com")
        assert valid

    def test_valid_subdomain(self) -> None:
        valid, _ = self.validator.validate("sub.example.co.uk")
        assert valid

    def test_rejects_placeholder(self) -> None:
        valid, _ = self.validator.validate("example.com")
        # example.com is in blocked list
        assert not valid

    def test_rejects_no_tld(self) -> None:
        valid, _ = self.validator.validate("nodotdomain")
        assert not valid

    def test_normalize_strips_protocol(self) -> None:
        # example.org is deliberately blocklisted (RFC 2606 placeholder) —
        # use a real-looking domain so normalize() doesn't reject it.
        result = self.validator.normalize("https://www.acme-widgets.org/path")
        assert result == "acme-widgets.org"

    def test_normalize_strips_www(self) -> None:
        result = self.validator.normalize("www.company.com")
        assert result == "company.com"
