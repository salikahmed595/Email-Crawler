"""
run_export.py — Export all crawled results to JSON.

Usage:
    python scripts/run_export.py
    python scripts/run_export.py --output output/results.json --min-confidence 50
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def main(output_path: str | None, min_confidence: int) -> None:
    from app.logging import configure_logging
    configure_logging()

    from app.services.export_service import ExportService
    export_service = ExportService()

    print(f"Exporting results (min_confidence={min_confidence})...")
    path = await export_service.export_to_json(
        output_path=output_path,
        min_confidence=min_confidence,
    )
    print(f"Export complete: {path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export crawl results to JSON")
    parser.add_argument("--output", help="Output file path (default: output/export_<timestamp>.json)")
    parser.add_argument("--min-confidence", type=int, default=0, help="Minimum confidence score to include")
    args = parser.parse_args()

    asyncio.run(main(args.output, args.min_confidence))
