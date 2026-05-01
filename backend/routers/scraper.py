import hashlib
import json
import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel

from database.db import get_db
from database.repository import PropertyRecord, Repository, ScrapeRunRecord, get_repo
from services import scraper_service, image_service
from services import poster_service
from services.enrichment_queue import enqueue_enrichment
from services.enrichment_service import run_rule_based_enrichment
from services.scraper_service import (
    _calculate_weighted_quality,
    generate_property_id,
    ALL_SOURCES,
    ScrapeMetrics,
)
from services.validator import validate_and_filter
from services.watermark_filter import watermark_reasons

logger = logging.getLogger(__name__)
router = APIRouter()


def _resolve_poster_task(prop_id: str, agent_name, broker_name, agent_image_url, repo: Repository):
    """Background task: resolve poster landlord and write back to pipeline DB."""
    try:
        landlord_id = poster_service.resolve_poster_landlord(
            agent_name=agent_name,
            broker_name=broker_name,
            agent_image_url=agent_image_url,
        )
        if landlord_id:
            prop = repo.get(prop_id)
            if prop:
                prop.poster_landlord_id = landlord_id
                repo.save(prop)
                logger.info("Poster assigned: %s → %s", prop_id, landlord_id)
    except Exception as e:
        logger.warning("Poster resolution failed for %s: %s", prop_id, e)

# Phase 2 (2.3): wall-clock cap on the scrape() call.
# Single-source scrapes get 90 s; multi-source ("all") gets 120 s.
_SINGLE_SOURCE_TIMEOUT = int(__import__("os").environ.get("PIPELINE_SCRAPE_TIMEOUT_SINGLE", "90"))
_ALL_SOURCE_TIMEOUT    = int(__import__("os").environ.get("PIPELINE_SCRAPE_TIMEOUT_ALL",    "120"))


class ScrapeRequest(BaseModel):
    location: str
    source: Optional[str] = "realtor"
    listing_type: Optional[str] = "for_rent"
    property_type: Optional[List[str]] = None

    min_price: Optional[int] = None
    max_price: Optional[int] = None

    beds_min: Optional[int] = None
    beds_max: Optional[int] = None

    baths_min: Optional[float] = None
    baths_max: Optional[float] = None

    sqft_min: Optional[int] = None
    sqft_max: Optional[int] = None

    lot_sqft_min: Optional[int] = None
    lot_sqft_max: Optional[int] = None

    year_built_min: Optional[int] = None
    year_built_max: Optional[int] = None

    past_days: Optional[int] = None
    past_hours: Optional[int] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None

    radius: Optional[float] = None
    limit: Optional[int] = 200
    mls_only: Optional[bool] = False
    foreclosure: Optional[bool] = None
    exclude_pending: Optional[bool] = False

    sort_by: Optional[str] = None
    sort_direction: Optional[str] = "desc"


def _merge_download_stats(existing_json: str, reason_counts: dict) -> str:
    """Phase 2 (2.5): merge image download reason_counts into inferred_features JSON.

    inferred_features is a JSON-encoded list of strings used for display. We
    append one entry per non-ok reason so the UI can see download health without
    a schema migration.
    """
    try:
        features = json.loads(existing_json or "[]")
        if not isinstance(features, list):
            features = []
    except Exception:
        features = []

    total = sum(reason_counts.values())
    ok = reason_counts.get("ok", 0)
    failed = total - ok
    if total:
        summary = f"_img_ok={ok} _img_failed={failed}"
        if failed:
            detail = " ".join(f"_img_{k}={v}" for k, v in reason_counts.items() if k != "ok" and v)
            summary += f" ({detail})"
        # Remove any previous _img_ summary entries so we don't accumulate duplicates
        features = [f for f in features if not (isinstance(f, str) and f.startswith("_img_"))]
        features.append(summary)

    return json.dumps(features)


def download_images_task(property_id: str, image_urls: list):
    """Background task: download images and persist download stats (Phase 2.5)."""
    repo = get_repo()
    try:
        paths, reason_counts = image_service.download_images(property_id, image_urls)
        prop = repo.get(property_id)
        if prop:
            prop.local_image_paths = json.dumps(paths)
            # Phase 2 (2.5): persist download stats into inferred_features
            prop.inferred_features = _merge_download_stats(
                prop.inferred_features or "[]", reason_counts
            )
            try:
                repo.save(prop)
            except Exception as e:
                logger.error("Failed to save image paths for %s: %s", property_id, e)
    except Exception as e:
        logger.error("Image download task failed for %s: %s", property_id, e)


def _make_idempotency_key(req: ScrapeRequest) -> str:
    """Phase 5 (5.3): stable hash over the fields that define a distinct scrape."""
    canonical = json.dumps({
        "location":     (req.location or "").strip().lower(),
        "source":       (req.source or "realtor").lower(),
        "listing_type": (req.listing_type or "for_rent").lower(),
        "min_price":    req.min_price,
        "max_price":    req.max_price,
        "beds_min":     req.beds_min,
        "beds_max":     req.beds_max,
    }, sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()[:24]


@router.post("/scrape")
def scrape_properties(
    req: ScrapeRequest,
    background_tasks: BackgroundTasks,
    repo: Repository = Depends(get_db),
):
    source = (req.source or "realtor").lower()
    if source not in ALL_SOURCES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported source '{source}'. Supported: {', '.join(sorted(ALL_SOURCES))}."
        )

    # Phase 5 (5.3): idempotency — reject duplicate requests within 30 s.
    idem_key = _make_idempotency_key(req)
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=30)
    recent_runs = repo.list_scrape_runs(limit=20)
    for run in recent_runs:
        run_key = run.get("idempotency_key") if isinstance(run, dict) else getattr(run, "idempotency_key", None)
        run_at_raw = run.get("completed_at") if isinstance(run, dict) else getattr(run, "completed_at", None)
        if run_key == idem_key and run_at_raw:
            try:
                run_at = datetime.fromisoformat(run_at_raw.replace("Z", "+00:00"))
                if run_at >= cutoff:
                    raise HTTPException(
                        status_code=409,
                        detail={
                            "message": "Duplicate scrape request — identical run completed within the last 30 seconds.",
                            "idempotency_key": idem_key,
                            "existing_run": run if isinstance(run, dict) else run.to_dict(),
                        },
                    )
            except HTTPException:
                raise
            except Exception:
                pass

    # Phase 2 (2.3): wall-clock cap on the scrape call.
    timeout_s = _ALL_SOURCE_TIMEOUT if source == "all" else _SINGLE_SOURCE_TIMEOUT
    metrics = ScrapeMetrics()

    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(
                scraper_service.scrape,
                location=req.location,
                source=source,
                listing_type=req.listing_type,
                property_type=req.property_type,
                min_price=req.min_price,
                max_price=req.max_price,
                beds_min=req.beds_min,
                beds_max=req.beds_max,
                baths_min=req.baths_min,
                baths_max=req.baths_max,
                sqft_min=req.sqft_min,
                sqft_max=req.sqft_max,
                lot_sqft_min=req.lot_sqft_min,
                lot_sqft_max=req.lot_sqft_max,
                year_built_min=req.year_built_min,
                year_built_max=req.year_built_max,
                past_days=req.past_days,
                past_hours=req.past_hours,
                date_from=req.date_from,
                date_to=req.date_to,
                radius=req.radius,
                limit=req.limit,
                mls_only=req.mls_only,
                foreclosure=req.foreclosure,
                exclude_pending=req.exclude_pending,
                sort_by=req.sort_by,
                sort_direction=req.sort_direction,
            )
            results = future.result(timeout=timeout_s)
    except FuturesTimeoutError:
        msg = f"scrape_timeout:{timeout_s}s"
        metrics.errors.append(msg)
        metrics.partial = True
        logger.warning("Scrape timed out after %ds for %s/%s", timeout_s, source, req.location)
        results = []
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scraping failed: {str(e)}")

    # Phase 1 (C1, H4): preserve per-source attribution.
    results = scraper_service._ensure_source(results, req.source or "realtor")

    metrics.total_scraped = len(results)
    for r in results:
        src = r.get("source") or source
        metrics.per_source_counts[src] = metrics.per_source_counts.get(src, 0) + 1

    saved = []
    for data in results:
        reasons = watermark_reasons(data)
        if reasons:
            metrics.watermarked_dropped += 1
            logger.info(
                "Skipping watermarked property %s: %s",
                data.get("source_listing_id") or data.get("address"),
                "; ".join(reasons),
            )
            continue

        source_listing_id = data.get("source_listing_id")

        existing = None
        if source_listing_id:
            existing = repo.get_by_source_listing_id(source_listing_id)

        if existing:
            metrics.duplicate_skipped += 1
            saved.append(existing)
            continue

        # Phase 3 (3.1): hard-reject unsalvageable rows.
        data, reject_reason = validate_and_filter(data)
        if reject_reason:
            metrics.validation_rejected += 1
            metrics.errors.append(f"validation_rejected:{reject_reason}")
            logger.info(
                "Rejected property %s: %s",
                source_listing_id or "?", reject_reason,
            )
            continue
        data = run_rule_based_enrichment(data)

        image_urls = []
        try:
            image_urls = json.loads(data.get("original_image_urls", "[]"))
        except Exception:
            pass

        score, missing = _calculate_weighted_quality(data, image_urls)
        data["data_quality_score"] = score
        data["missing_fields"] = json.dumps(missing)

        prop_id = generate_property_id()
        from database.repository import PROPERTY_FIELDS
        valid_cols = set(PROPERTY_FIELDS)
        prop_data = {k: v for k, v in data.items() if k in valid_cols}
        prop = PropertyRecord(id=prop_id, **prop_data)
        try:
            repo.save(prop)
        except Exception as e:
            metrics.errors.append(f"save_failed:{prop_id}:{e}")
            logger.error("Failed to save property %s: %s", prop_id, e)
            continue
        saved.append(prop)
        metrics.saved += 1

        if image_urls:
            metrics.image_download_queued += len(image_urls)
            background_tasks.add_task(download_images_task, prop_id, image_urls)
        background_tasks.add_task(enqueue_enrichment, prop_id)

        agent_name = data.get("agent_name")
        broker_name = data.get("broker_name")
        agent_image_url = data.get("agent_image_url")
        if agent_name or broker_name:
            background_tasks.add_task(
                _resolve_poster_task,
                prop_id, agent_name, broker_name, agent_image_url, repo,
            )

    new_scores = [
        p.data_quality_score for p in saved
        if hasattr(p, "data_quality_score") and p.data_quality_score is not None
    ]
    avg_score = round(sum(new_scores) / len(new_scores), 1) if new_scores else None

    # Phase 2 (2.3): set partial=True whenever any source had errors.
    if metrics.errors and not metrics.partial:
        metrics.partial = True

    run = ScrapeRunRecord(
        source=source,
        location=req.location,
        count_total=metrics.total_scraped,
        count_new=metrics.saved,
        avg_score=avg_score,
        error_message=metrics.to_json(),
        count_watermarked=metrics.watermarked_dropped,
        count_duplicate=metrics.duplicate_skipped,
        count_validation_rejected=metrics.validation_rejected,
        count_image_failed=0,
        meta_json=metrics.to_json(),
        idempotency_key=idem_key,
    )
    repo.add_scrape_run(run)

    return {
        "count": len(saved),
        "properties": [p.to_dict() for p in saved],
        "meta": metrics.to_dict(),
    }


@router.post("/properties/{id}/redownload-images")
def redownload_images_endpoint(
    id: str,
    background_tasks: BackgroundTasks,
    repo: Repository = Depends(get_db),
):
    """Re-download images for a single property from its original source URLs.

    Wipes the current local image cache for the property and re-fetches all
    images from the scraped source URLs.  The download runs as a background
    task so the response is immediate.
    """
    prop = repo.get(id)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    urls = json.loads(prop.original_image_urls or "[]")
    if not urls:
        raise HTTPException(
            status_code=400,
            detail="No source image URLs found for this property. Re-scrape it to get fresh URLs.",
        )

    prop_dir = image_service.get_property_dir(id)
    import shutil, os
    if os.path.isdir(prop_dir):
        shutil.rmtree(prop_dir)
    os.makedirs(prop_dir, exist_ok=True)

    prop.local_image_paths = "[]"
    try:
        repo.save(prop)
    except Exception as e:
        logger.warning("Could not clear local_image_paths before redownload for %s: %s", id, e)

    background_tasks.add_task(download_images_task, id, urls)

    logger.info("Redownload queued for %s — %d source URLs", id, len(urls))
    return {
        "ok": True,
        "queued": len(urls),
        "message": f"Re-downloading up to {len(urls)} images in the background.",
    }
