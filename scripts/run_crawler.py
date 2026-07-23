"""
run_crawler.py — Import a CSV and run the crawler standalone.

Usage:
    python scripts/run_crawler.py --input sample_data/small.csv
    python scripts/run_crawler.py --input my_companies.csv --workers 4
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def main(csv_path: str, workers: int, no_queue: bool) -> None:
    from app.logging import configure_logging
    configure_logging()

    from app.logging import get_logger
    logger = get_logger("run_crawler")

    # Read CSV
    with open(csv_path, "r", encoding="utf-8") as f:
        csv_content = f.read()

    logger.info("Starting crawler", input=csv_path, workers=workers)

    if no_queue:
        # Direct mode: crawl without Redis queue (for small datasets / testing)
        from app.storage.database import init_db
        await init_db()

        from app.services.import_service import ImportService
        import_service = ImportService()
        summary = await import_service.import_csv(
            csv_content=csv_content,
            source_file=os.path.basename(csv_path),
            queue_manager=None,  # No queue — creates companies only
        )
        logger.info("Companies imported", **{k: v for k, v in summary.items() if k != "errors"})

        # Now crawl directly
        from app.storage.database import get_session
        from app.storage.repositories.company_repo import CompanyRepository
        from app.services.crawl_service import CrawlService

        crawl_service = CrawlService()
        async with get_session() as session:
            repo = CompanyRepository(session)
            companies = await repo.list_by_status("pending", limit=1000)

        logger.info("Crawling companies", count=len(companies))

        semaphore = asyncio.Semaphore(workers)

        async def crawl_one(company) -> None:
            async with semaphore:
                try:
                    await crawl_service.process_company(company.id, company.domain)
                except Exception as exc:
                    logger.error("Crawl failed", domain=company.domain, error=str(exc))

        tasks = [asyncio.create_task(crawl_one(c)) for c in companies]
        await asyncio.gather(*tasks)
        await crawl_service.close()

        logger.info("Crawl complete")

    else:
        # Queue mode: import and enqueue for workers
        from app.queue.queue_manager import QueueManager
        from app.storage.database import init_db
        await init_db()

        queue_manager = await QueueManager.create()
        try:
            from app.services.import_service import ImportService
            import_service = ImportService()
            summary = await import_service.import_csv(
                csv_content=csv_content,
                source_file=os.path.basename(csv_path),
                queue_manager=queue_manager,
            )
            print("\n" + "=" * 50)
            print("Import Summary:")
            for k, v in summary.items():
                if k != "errors":
                    print(f"  {k}: {v}")
            print("=" * 50)
            print(f"\nJobs queued! Start workers with: python scripts/run_worker.py")
        finally:
            await queue_manager.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import CSV and crawl companies")
    parser.add_argument("--input", required=True, help="Path to CSV file")
    parser.add_argument("--workers", type=int, default=4, help="Number of concurrent workers")
    parser.add_argument(
        "--no-queue",
        action="store_true",
        help="Run directly without Redis queue (dev mode)",
    )
    args = parser.parse_args()

    asyncio.run(main(args.input, args.workers, args.no_queue))
