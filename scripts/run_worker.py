"""
run_worker.py — Start crawl workers to process the Redis queue.

Usage:
    python scripts/run_worker.py
    python scripts/run_worker.py --workers 4
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def main(num_workers: int) -> None:
    from app.logging import configure_logging
    configure_logging()

    from app.logging import get_logger
    logger = get_logger("run_worker")

    from app.queue.queue_manager import QueueManager
    from app.workers.crawl_worker import CrawlWorker

    logger.info("Starting crawl workers", count=num_workers)

    workers = []
    for i in range(num_workers):
        qm = await QueueManager.create()
        worker = CrawlWorker(queue_manager=qm, worker_id=f"worker-{i+1}")
        workers.append((worker, qm))

    tasks = [asyncio.create_task(w.start()) for w, _ in workers]

    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        pass
    finally:
        for _, qm in workers:
            await qm.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Start crawl workers")
    parser.add_argument("--workers", type=int, default=4, help="Number of workers")
    args = parser.parse_args()
    asyncio.run(main(args.workers))
