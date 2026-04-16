import json
import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional

from database.db import get_db
from database.repository import PropertyRecord, Repository, get_repo, PROPERTY_FIELDS
from services import scraper_service, image_service
from services.scraper_service import generate_property_id, scrape_all_sources, ALL_SOURCES
from services.watermark_filter import filter_watermarked, watermark_reasons

logger = logging.getLogger(__name__)
router = APIRouter()

VALID_COLUMNS = set(PROPERTY_FIELDS)


class SearchRequest(BaseModel):
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


def _download_images_task(property_id: str, image_urls: list):
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


def _enrich_results(results: list, listing_type: str, source: str) -> list:
    enriched = []
    for r in results:
        r["temp_key"] = r.get("source_listing_id") or str(uuid.uuid4())
        r["listing_type"] = r.get("listing_type") or listing_type
        r["list_date"] = r.pop("_list_date", None)
        r["days_on_market"] = r.pop("_days_on_market", None)
        try:
            r["image_urls"] = json.loads(r.get("original_image_urls", "[]"))
        except Exception:
            r["image_urls"] = []
        enriched.append(r)
    return enriched


@router.post("/search")
def search_properties(req: SearchRequest):
    source = (req.source or "realtor").lower()
    source_counts = {}

    if source == "all":
        try:
            results, source_counts = scrape_all_sources(
                location=req.location,
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
                limit=req.limit or 200,
                mls_only=req.mls_only,
                foreclosure=req.foreclosure,
                exclude_pending=req.exclude_pending,
                sort_by=req.sort_by,
                sort_direction=req.sort_direction,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Multi-source search failed: {str(e)}")
    elif source not in ALL_SOURCES:
        raise HTTPException(status_code=400, detail=f"Unknown source '{source}'.")
    else:
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
            raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")
        results = scraper_service._inject_source(results, source)
        source_counts = {source: len(results)}

    filtered_results, blocked_results = filter_watermarked(results)
    enriched = _enrich_results(filtered_results, req.listing_type or "for_rent", source)

    return {
        "count":                   len(enriched),
        "results":                 enriched,
        "blocked_watermark_count": len(blocked_results),
        "blocked_watermarks":      blocked_results,
        "source_counts":           source_counts,
    }


@router.post("/save-property")
def save_property(
    data: dict,
    background_tasks: BackgroundTasks,
    repo: Repository = Depends(get_db),
):
    reasons = watermark_reasons(data)
    if reasons:
        raise HTTPException(
            status_code=400,
            detail="Property blocked because it appears to contain watermarked images: " + "; ".join(reasons)
        )

    source_listing_id = data.get("source_listing_id")

    if source_listing_id:
        existing = repo.get_by_source_listing_id(source_listing_id)
        if existing:
            return {"already_exists": True, "id": existing.id}

    save_data = {
        k: v for k, v in data.items()
        if k in VALID_COLUMNS and k != "id" and not k.startswith("_")
    }

    prop_id = generate_property_id()
    prop = PropertyRecord(id=prop_id, **save_data)
    try:
        repo.save(prop)
    except Exception as e:
        logger.error("Failed to save property %s: %s", prop_id, e)
        raise HTTPException(status_code=500, detail="Failed to save property")

    image_urls = []
    try:
        image_urls = json.loads(data.get("original_image_urls", "[]"))
    except Exception:
        pass

    if image_urls:
        background_tasks.add_task(_download_images_task, prop_id, image_urls)

    return {"already_exists": False, "id": prop_id}
