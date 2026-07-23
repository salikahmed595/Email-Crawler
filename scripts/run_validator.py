"""
run_validator.py — Validate a list of email addresses standalone.

Usage:
    python scripts/run_validator.py --emails test@example.com info@google.com
    python scripts/run_validator.py --file emails.txt
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def main(emails: list[str]) -> None:
    from app.logging import configure_logging
    configure_logging()

    from app.validators.email_validator import EmailValidator
    validator = EmailValidator()

    results = []
    for address in emails:
        result = await validator.validate(address)
        results.append({
            "address": result.address,
            "confidence": result.confidence,
            "status": result.validation_status,
            "is_valid_syntax": result.is_valid_syntax,
            "mx_valid": result.mx_valid,
            "is_disposable": result.is_disposable,
            "is_role_based": result.is_role_based,
            "notes": result.notes,
        })

    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate email addresses")
    parser.add_argument("--emails", nargs="+", help="Email addresses to validate")
    parser.add_argument("--file", help="File with one email per line")
    args = parser.parse_args()

    emails: list[str] = []
    if args.emails:
        emails.extend(args.emails)
    if args.file:
        with open(args.file) as f:
            emails.extend(line.strip() for line in f if line.strip())

    if not emails:
        print("No emails provided. Use --emails or --file")
        sys.exit(1)

    asyncio.run(main(emails))
