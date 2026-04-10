import json
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database.db import get_db
from database.models import Property
from services import scraper_service, image_service
from services.scraper_service import generate_property_id

router = APIRouter()


class ScrapeRequest(BaseModel):
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


def download_images_task(property_id: str, image_urls: list, db_session_factory):
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


@router.post("/scrape")
def scrape_properties(
    req: ScrapeRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
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
        raise HTTPException(status_code=500, detail=f"Scraping failed: {str(e)}")

    saved = []
    for data in results:
        source_listing_id = data.get("source_listing_id")

        existing = None
        if source_listing_id:
            existing = db.query(Property).filter(
                Property.source_listing_id == source_listing_id
            ).first()

        if existing:
            saved.append(existing)
            continue

        prop_id = generate_property_id()
        prop = Property(id=prop_id, **data)
        db.add(prop)
        db.commit()
        db.refresh(prop)
        saved.append(prop)

        image_urls = json.loads(data.get("original_image_urls", "[]"))
        if image_urls:
            from database.db import SessionLocal
            background_tasks.add_task(
                download_images_task, prop_id, image_urls, SessionLocal
            )

    return {"count": len(saved), "properties": [prop_to_dict(p) for p in saved]}


def prop_to_dict(prop: Property) -> dict:
    return {c.name: getattr(prop, c.name) for c in prop.__table__.columns}
