"""
Rate-controlled enrichment queue — Phase 3B / Phase 5.4.

Phase 5.4 upgrade: the background work is now handled by a dedicated daemon
thread that consumes from a stdlib queue.Queue. FastAPI's request handler
returns as soon as it calls enqueue_enrichment() — the actual enrichment work
(geocoding, detail-fetching, AI enrichment, quality scoring) happens off the
request thread and never blocks uvicorn workers.

Concurrency model
─────────────────
• One dedicated thread (`enrichment-worker`) processes IDs one at a time.
• INTER_ENRICHMENT_DELAY between completions prevents API hammering.
• The queue is unbounded; the system gracefully absorbs bursts.
• The daemon thread exits automatically when the process exits.
"""

import json
import logging
import os
import queue
import threading
import time
from typing import List

from services.ai_enricher import enrich_property
from database.repository import get_repo

logger = logging.getLogger(__name__)

# Phase 4 (4.5): env-driven so operators can tune without a code change.
_delay_ms = os.environ.get("PIPELINE_ENRICHMENT_DELAY_MS")
INTER_ENRICHMENT_DELAY: float = float(_delay_ms) / 1000.0 if _delay_ms else 1.0

# Phase 5.4: the real queue
_enrichment_q: queue.Queue = queue.Queue()


def _do_enrich(property_id: str) -> None:
    """Full enrichment pipeline for one property (runs inside the daemon thread)."""
    repo = get_repo()
    try:
        from services.enrichment_service import geocode_property, run_rule_based_enrichment
        from services.detail_fetcher import fetch_missing_fields
        from services.scraper_service import _calculate_weighted_quality

        geocode_property(property_id, repo)
        fetch_missing_fields(property_id, repo)
        enrich_property(property_id, repo)

        prop = repo.get(property_id)
        if not prop:
            return

        image_urls = []
        try:
            image_urls = json.loads(prop.original_image_urls or "[]")
        except Exception:
            pass

        prop_dict = {
            "address":        prop.address,
            "city":           prop.city,
            "state":          prop.state,
            "zip":            prop.zip,
            "monthly_rent":   prop.monthly_rent,
            "bedrooms":       prop.bedrooms,
            "bathrooms":      prop.bathrooms or prop.total_bathrooms,
            "description":    prop.description,
            "property_type":  prop.property_type,
            "available_date": prop.available_date,
            "amenities":      prop.amenities,
            "appliances":     prop.appliances,
        }
        score, missing = _calculate_weighted_quality(prop_dict, image_urls)
        prop.data_quality_score = score
        prop.missing_fields = json.dumps(missing)
        try:
            repo.save(prop)
            logger.info("Enrichment complete for %s — final score %d", property_id, score)
        except Exception as e:
            logger.error("Failed to update score after enrichment for %s: %s", property_id, e)

    except Exception as e:
        logger.error("Enrichment failed for %s: %s", property_id, e)


def _worker() -> None:
    """Daemon thread: consume property IDs from the queue and enrich them one at a time."""
    logger.info("enrichment-worker started (delay=%.2fs)", INTER_ENRICHMENT_DELAY)
    while True:
        try:
            property_id = _enrichment_q.get(block=True, timeout=5)
        except queue.Empty:
            continue
        try:
            _do_enrich(property_id)
        finally:
            _enrichment_q.task_done()
            time.sleep(INTER_ENRICHMENT_DELAY)


# Start the daemon thread once at module import time.
_worker_thread = threading.Thread(
    target=_worker,
    name="enrichment-worker",
    daemon=True,
)
_worker_thread.start()


def enqueue_enrichment(property_id: str) -> None:
    """
    Phase 5.4: enqueue a property for enrichment and return immediately.

    The actual work (geocoding, AI enrichment, quality scoring) happens in the
    dedicated enrichment-worker daemon thread. FastAPI's request handler is
    freed as soon as this function returns.
    """
    _enrichment_q.put(property_id)
    logger.debug("Queued enrichment for %s (queue depth: %d)", property_id, _enrichment_q.qsize())


# ── Async / Batch helpers (kept for backward compatibility) ──────────────────

import asyncio
from concurrent.futures import ThreadPoolExecutor

MAX_CONCURRENT_ENRICHMENTS = 3
ENRICHMENT_DELAY = 0.5
BATCH_SIZE = 10

_enrichment_semaphore = asyncio.Semaphore(MAX_CONCURRENT_ENRICHMENTS)
_executor = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_ENRICHMENTS, thread_name_prefix="enrichment")


async def _enrich_single_property_async(property_id: str) -> None:
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(_executor, _do_enrich, property_id)


async def enqueue_enrichment_batch(property_ids: List[str]) -> None:
    """Process multiple properties in parallel with rate limiting."""
    if not property_ids:
        return

    logger.info("Starting batch enrichment of %d properties", len(property_ids))

    for i in range(0, len(property_ids), BATCH_SIZE):
        batch = property_ids[i:i + BATCH_SIZE]
        logger.info("Processing batch %d-%d of %d",
                    i + 1, min(i + BATCH_SIZE, len(property_ids)), len(property_ids))

        tasks = []
        for prop_id in batch:
            task = asyncio.create_task(_enrich_single_property_async(prop_id))
            tasks.append(task)
            await asyncio.sleep(ENRICHMENT_DELAY)

        await asyncio.gather(*tasks, return_exceptions=True)

        if i + BATCH_SIZE < len(property_ids):
            await asyncio.sleep(1.0)

    logger.info("Completed batch enrichment of %d properties", len(property_ids))


async def enqueue_enrichment_async(property_id: str) -> None:
    """Single property enrichment with semaphore-based concurrency control."""
    async with _enrichment_semaphore:
        await _enrich_single_property_async(property_id)
        await asyncio.sleep(ENRICHMENT_DELAY)
