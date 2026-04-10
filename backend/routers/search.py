import json
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional

from database.db import get_db
from database.models import Property
from services import scraper_service, image_service
from services.scraper_service import generate_property_id

router = APIRouter()

VALID_COLUMNS = None


def get_valid_columns():
    global VALID_COLUMNS
    if VALID_COLUMNS is None:
        VALID_COLUMNS = set(c.name for c in Property.__table__.columns)
    return VALID_COLUMNS


class SearchRequest(BaseModel):
    location: str
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


def _download_images_task(property_id: str, image_urls: list, db_session_factory):
    db = db_session_factory()
    try:
        paths = image_service.download_images(property_id, image_urls)
        prop = db.query(Property).filter(Property.id == property_id).first()
        if prop:
            prop.local_image_paths = json.dumps(paths)
            db.commit()
    except Exception:
        pass
    finally:
        db.close()


@router.post("/search")
def search_properties(req: SearchRequest):
    try:
        results = scraper_service.scrape(
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
            limit=req.limit,
            mls_only=req.mls_only,
            foreclosure=req.foreclosure,
            exclude_pending=req.exclude_pending,
            sort_by=req.sort_by,
            sort_direction=req.sort_direction,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

    enriched = []
    for r in results:
        r["temp_key"] = r.get("source_listing_id") or str(uuid.uuid4())
        try:
            r["image_urls"] = json.loads(r.get("original_image_urls", "[]"))
        except Exception:
            r["image_urls"] = []
        enriched.append(r)

    return {"count": len(enriched), "results": enriched}


@router.post("/save-property")
def save_property(
    data: dict,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    source_listing_id = data.get("source_listing_id")

    if source_listing_id:
        existing = db.query(Property).filter(
            Property.source_listing_id == source_listing_id
        ).first()
        if existing:
            return {"already_exists": True, "id": existing.id}

    valid_cols = get_valid_columns()
    save_data = {
        k: v for k, v in data.items()
        if k in valid_cols and k != "id"
    }

    prop_id = generate_property_id()
    prop = Property(id=prop_id, **save_data)
    db.add(prop)
    db.commit()
    db.refresh(prop)

    image_urls = []
    try:
        image_urls = json.loads(data.get("original_image_urls", "[]"))
    except Exception:
        pass

    if image_urls:
        from database.db import SessionLocal
        background_tasks.add_task(
            _download_images_task, prop_id, image_urls, SessionLocal
        )

    return {"already_exists": False, "id": prop_id}
