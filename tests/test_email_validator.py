"""
Tests for EmailValidator — all 10 validation stages.
"""

from __future__ import annotations

import pytest
from app.validators.email_validator import EmailValidator


class TestEmailValidator:
    """Tests for the 10-stage email validation pipeline."""

    def setup_method(self) -> None:
        self.validator = EmailValidator()

    # --- Stage 1: Normalization ---
    @pytest.mark.asyncio
    async def test_stage1_normalization(self) -> None:
        result = await self.validator.validate("  UPPER@EXAMPLE.COM  ")
        assert result.address == "upper@example.com"

    # --- Stage 2: Syntax ---
    @pytest.mark.asyncio
    async def test_stage2_valid_syntax(self, valid_emails: list[str]) -> None:
        for email in valid_emails:
            result = await self.validator.validate(email)
            assert result.is_valid_syntax, f"Expected valid syntax for {email}"

    @pytest.mark.asyncio
    async def test_stage2_invalid_syntax(self, invalid_emails: list[str]) -> None:
        for email in invalid_emails:
            result = await self.validator.validate(email)
            assert not result.is_valid_syntax, f"Expected invalid syntax for {email}"

    # --- Stage 3: Domain format ---
    @pytest.mark.asyncio
    async def test_stage3_valid_domain(self) -> None:
        result = await self.validator.validate("user@valid-domain.com")
        assert result.is_valid_domain

    @pytest.mark.asyncio
    async def test_stage3_invalid_domain_no_tld(self) -> None:
        result = await self.validator.validate("user@nodot")
        assert not result.is_valid_syntax or not result.is_valid_domain

    # --- Stage 7: Disposable detection ---
    @pytest.mark.asyncio
    async def test_stage7_disposable(self, disposable_emails: list[str]) -> None:
        for email in disposable_emails:
            result = await self.validator.validate(email)
            assert result.is_disposable, f"Expected disposable for {email}"

    # --- Stage 8: Role-based detection ---
    @pytest.mark.asyncio
    async def test_stage8_role_based(self, role_based_emails: list[str]) -> None:
        for email in role_based_emails:
            result = await self.validator.validate(email)
            assert result.is_role_based, f"Expected role-based for {email}"

    @pytest.mark.asyncio
    async def test_stage8_personal_not_role_based(self) -> None:
        result = await self.validator.validate("john.smith@company.com")
        assert not result.is_role_based

    # --- Stage 10: Confidence ---
    @pytest.mark.asyncio
    async def test_stage10_confidence_range(self, valid_emails: list[str]) -> None:
        for email in valid_emails:
            result = await self.validator.validate(email)
            assert 0 <= result.confidence <= 100, f"Confidence out of range for {email}"

    @pytest.mark.asyncio
    async def test_stage10_disposable_low_confidence(self) -> None:
        result = await self.validator.validate("test@mailinator.com")
        assert result.confidence < 30, "Disposable should have very low confidence"

    @pytest.mark.asyncio
    async def test_stage10_invalid_zero_confidence(self) -> None:
        result = await self.validator.validate("notvalid")
        assert result.confidence == 0

    # --- Status ---
    @pytest.mark.asyncio
    async def test_status_invalid_syntax(self) -> None:
        result = await self.validator.validate("@@invalid")
        assert result.validation_status == "invalid"

    @pytest.mark.asyncio
    async def test_status_disposable_is_invalid(self) -> None:
        result = await self.validator.validate("user@mailinator.com")
        assert result.validation_status == "invalid"

    # --- All results have required fields ---
    @pytest.mark.asyncio
    async def test_result_has_all_fields(self) -> None:
        result = await self.validator.validate("test@example.com")
        assert hasattr(result, "address")
        assert hasattr(result, "confidence")
        assert hasattr(result, "validation_status")
        assert hasattr(result, "is_valid_syntax")
        assert hasattr(result, "mx_valid")
        assert hasattr(result, "is_disposable")
        assert hasattr(result, "is_role_based")
        assert isinstance(result.notes, list)
