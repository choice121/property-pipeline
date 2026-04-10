import json
from typing import Optional

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
    listing_type: str = "for_rent"
    min_price: Optional[int] = None
    max_price: Optional[int] = None
    bedrooms: Optional[int] = None


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
            min_price=req.min_price,
            max_price=req.max_price,
            bedrooms=req.bedrooms,
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
