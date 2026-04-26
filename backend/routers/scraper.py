import json
import logging
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel

from database.db import get_db
from database.repository import PropertyRecord, Repository, ScrapeRunRecord, get_repo
from services import scraper_service, image_service
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


def download_images_task(property_id: str, image_urls: list):
    repo = get_repo()
    try:
        paths = image_service.download_images(property_id, image_urls)
        prop = repo.get(property_id)
        if prop:
            prop.local_image_paths = json.dumps(paths)
            try:
                repo.save(prop)
            except Exception as e:
                logger.error("Failed to save image paths for %s: %s", property_id, e)
    except Exception as e:
        logger.error("Image download task failed for %s: %s", property_id, e)


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

    try:
        results = scraper_service.scrape(
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scraping failed: {str(e)}")

    # Phase 1 (C1, H4): use _ensure_source so per-source attribution from the
    # multi-source dispatcher is preserved instead of being overwritten.
    results = scraper_service._ensure_source(results, req.source or "realtor")

    metrics = ScrapeMetrics(total_scraped=len(results))
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

        # Phase 3 (3.1): hard-reject unsalvageable rows instead of saving
        # garbage. validate_and_filter returns (None, reason) for anything
        # missing rent / address or with rent below the floor.
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

    new_scores = [
        p.data_quality_score for p in saved
        if hasattr(p, "data_quality_score") and p.data_quality_score is not None
    ]
    avg_score = round(sum(new_scores) / len(new_scores), 1) if new_scores else None

    # Phase 1.5: persist metrics as JSON in the existing error_message column.
    # Phase 4 will give these proper columns; for now we piggy-back so we can
    # ship observability without a schema migration.
    run = ScrapeRunRecord(
        source=source,
        location=req.location,
        count_total=metrics.total_scraped,
        count_new=metrics.saved,
        avg_score=avg_score,
        error_message=metrics.to_json(),
    )
    repo.add_scrape_run(run)

    return {
        "count": len(saved),
        "properties": [p.to_dict() for p in saved],
        "meta": metrics.to_dict(),
    }
