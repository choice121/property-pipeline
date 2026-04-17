"""
Rate-controlled enrichment queue — Phase 3B.

When a large scrape returns many properties, all their enrichment background
tasks fire at once and hammer the DeepSeek API simultaneously. This module
provides a global threading.Lock that serializes all enrichment calls so only
one property is being enriched at a time, with a configurable pause between
each — identical to the 750ms inter-batch delay used in bulk_scan/bulk_clean.

Usage (in scraper.py):
    from services.enrichment_queue import enqueue_enrichment
    background_tasks.add_task(enqueue_enrichment, prop_id)
"""

import logging
import threading
import time

from services.ai_enricher import enrich_property
from database.repository import get_repo

logger = logging.getLogger(__name__)

_enrichment_lock = threading.Lock()

INTER_ENRICHMENT_DELAY = 1.0


def enqueue_enrichment(property_id: str) -> None:
    """
    Acquire the global enrichment lock, run the full enrichment pipeline for
    one property, then sleep before releasing. Any other background enrichment
    tasks that arrive while the lock is held will queue up and wait — meaning
    at most one property is enriched at any given moment, with at least
    INTER_ENRICHMENT_DELAY seconds between completions.

    Replaces direct calls to enrichment_background_task in scraper.py.
    """
    with _enrichment_lock:
        repo = get_repo()
        try:
            from services.enrichment_service import geocode_property, run_rule_based_enrichment
            from services.detail_fetcher import fetch_missing_fields
            from services.scraper_service import _calculate_weighted_quality
            import json

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
            logger.error("Enrichment queue task failed for %s: %s", property_id, e)
        finally:
            time.sleep(INTER_ENRICHMENT_DELAY)


# ── Async Batch Processing (New) ─────────────────────────────────────────────

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import List

# Configuration for parallel processing
MAX_CONCURRENT_ENRICHMENTS = 3  # Process up to 3 properties simultaneously
ENRICHMENT_DELAY = 0.5  # 500ms delay between starting new enrichments
BATCH_SIZE = 10  # Process in batches of 10

_enrichment_semaphore = asyncio.Semaphore(MAX_CONCURRENT_ENRICHMENTS)
_executor = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_ENRICHMENTS, thread_name_prefix="enrichment")


async def _enrich_single_property_async(property_id: str) -> None:
    """Async wrapper for property enrichment."""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(_executor, _enrich_single_property_sync, property_id)


def _enrich_single_property_sync(property_id: str) -> None:
    """Synchronous property enrichment (runs in thread pool)."""
    repo = get_repo()
    try:
        from services.enrichment_service import geocode_property, run_rule_based_enrichment
        from services.detail_fetcher import fetch_missing_fields
        from services.scraper_service import _calculate_weighted_quality
        import json

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
            logger.info("Async enrichment complete for %s — final score %d", property_id, score)
        except Exception as e:
            logger.error("Failed to update score after async enrichment for %s: %s", property_id, e)

    except Exception as e:
        logger.error("Async enrichment queue task failed for %s: %s", property_id, e)


async def enqueue_enrichment_batch(property_ids: List[str]) -> None:
    """
    Process multiple properties in parallel with rate limiting.
    Uses semaphore to limit concurrent operations and adds delays between batches.
    """
    if not property_ids:
        return

    logger.info("Starting batch enrichment of %d properties", len(property_ids))

    # Process in batches to avoid overwhelming the API
    for i in range(0, len(property_ids), BATCH_SIZE):
        batch = property_ids[i:i + BATCH_SIZE]
        logger.info("Processing batch %d-%d of %d properties",
                   i + 1, min(i + BATCH_SIZE, len(property_ids)), len(property_ids))

        # Create tasks for this batch
        tasks = []
        for prop_id in batch:
            task = asyncio.create_task(_enrich_single_property_async(prop_id))
            tasks.append(task)
            await asyncio.sleep(ENRICHMENT_DELAY)  # Rate limiting between starts

        # Wait for all tasks in this batch to complete
        await asyncio.gather(*tasks, return_exceptions=True)

        # Brief pause between batches
        if i + BATCH_SIZE < len(property_ids):
            await asyncio.sleep(1.0)

    logger.info("Completed batch enrichment of %d properties", len(property_ids))


async def enqueue_enrichment_async(property_id: str) -> None:
    """
    Single property enrichment with semaphore-based concurrency control.
    Async version for new code.
    """
    async with _enrichment_semaphore:
        await _enrich_single_property_async(property_id)
        await asyncio.sleep(ENRICHMENT_DELAY)
