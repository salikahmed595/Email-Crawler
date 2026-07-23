"""Repositories package."""
from app.storage.repositories.company_repo import CompanyRepository
from app.storage.repositories.email_repo import EmailRepository

__all__ = ["CompanyRepository", "EmailRepository"]
