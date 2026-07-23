"""
Initial database migration — creates all tables.
Migration ID: 001
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -----------------------------------------------------------------
    # companies
    # -----------------------------------------------------------------
    op.create_table(
        "companies",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(500), nullable=True),
        sa.Column("domain", sa.String(255), nullable=False),
        sa.Column("website", sa.String(2048), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("retry_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("industry", sa.String(255), nullable=True),
        sa.Column("category", sa.String(255), nullable=True),
        sa.Column("address", postgresql.JSONB, nullable=True),
        sa.Column("phone_numbers", postgresql.JSONB, nullable=True),
        sa.Column("social_links", postgresql.JSONB, nullable=True),
        sa.Column("technologies", postgresql.JSONB, nullable=True),
        sa.Column("services", postgresql.JSONB, nullable=True),
        sa.Column("opening_hours", postgresql.JSONB, nullable=True),
        sa.Column("team_members", postgresql.JSONB, nullable=True),
        sa.Column("source_file", sa.String(500), nullable=True),
        sa.Column("source_row", sa.Integer, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("domain", name="uq_companies_domain"),
    )
    op.create_index("ix_companies_domain", "companies", ["domain"])
    op.create_index("ix_companies_name", "companies", ["name"])
    op.create_index("ix_companies_status", "companies", ["status"])
    op.create_index("ix_companies_status_domain", "companies", ["status", "domain"])

    # -----------------------------------------------------------------
    # emails
    # -----------------------------------------------------------------
    op.create_table(
        "emails",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("address", sa.String(500), nullable=False),
        sa.Column("address_hash", sa.String(64), nullable=False),
        sa.Column("source", sa.String(2048), nullable=False),
        sa.Column("method", sa.String(100), nullable=False),
        sa.Column("page", sa.String(2048), nullable=True),
        sa.Column("discovered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confidence", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_valid_syntax", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_valid_domain", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("mx_valid", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("smtp_valid", sa.Boolean, nullable=True),
        sa.Column("is_disposable", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_role_based", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_duplicate", sa.Boolean, nullable=False, server_default="false"),
        sa.Column(
            "validation_status",
            sa.String(50),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_emails_address", "emails", ["address"])
    op.create_index("ix_emails_company_id", "emails", ["company_id"])
    op.create_index(
        "ix_emails_hash_company",
        "emails",
        ["address_hash", "company_id"],
        unique=True,
    )
    op.create_index("ix_emails_address_company", "emails", ["address", "company_id"])
    op.create_index("ix_emails_confidence", "emails", ["confidence"])
    op.create_index("ix_emails_valid", "emails", ["validation_status"])

    # -----------------------------------------------------------------
    # crawl_results
    # -----------------------------------------------------------------
    op.create_table(
        "crawl_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("final_url", sa.String(2048), nullable=True),
        sa.Column("engine_used", sa.String(50), nullable=False),
        sa.Column("status_code", sa.Integer, nullable=True),
        sa.Column("content_type", sa.String(255), nullable=True),
        sa.Column("content_length", sa.Integer, nullable=True),
        sa.Column("crawl_duration_ms", sa.Float, nullable=True),
        sa.Column("crawled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("success", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("emails_found", sa.Integer, nullable=False, server_default="0"),
        sa.Column("redirect_chain", postgresql.JSONB, nullable=True),
        sa.Column("tech_stack", postgresql.JSONB, nullable=True),
        sa.Column("response_headers", postgresql.JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_crawl_results_company_id", "crawl_results", ["company_id"])
    op.create_index(
        "ix_crawl_results_company_url",
        "crawl_results",
        ["company_id", "url"],
    )
    op.create_index("ix_crawl_results_engine", "crawl_results", ["engine_used"])


def downgrade() -> None:
    op.drop_table("crawl_results")
    op.drop_table("emails")
    op.drop_table("companies")
