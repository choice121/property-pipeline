import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database.db import get_db
from database.models import Property

router = APIRouter()


def prop_to_dict(prop: Property) -> dict:
    return {c.name: getattr(prop, c.name) for c in prop.__table__.columns}


@router.get("/properties")
def list_properties(
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    sort: Optional[str] = Query("scraped_at"),
    db: Session = Depends(get_db),
):
    query = db.query(Property)

    if status:
        query = query.filter(Property.status == status)

    if search:
        term = f"%{search}%"
        query = query.filter(
            (Property.address.ilike(term)) | (Property.city.ilike(term))
        )

    sort_map = {
        "scraped_at": Property.scraped_at.desc(),
        "monthly_rent": Property.monthly_rent.asc(),
        "monthly_rent_desc": Property.monthly_rent.desc(),
        "bedrooms": Property.bedrooms.asc(),
    }
    order = sort_map.get(sort, Property.scraped_at.desc())
    query = query.order_by(order)

    props = query.all()
    return [prop_to_dict(p) for p in props]


@router.get("/properties/{id}")
def get_property(id: str, db: Session = Depends(get_db)):
    prop = db.query(Property).filter(Property.id == id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    return prop_to_dict(prop)


@router.put("/properties/{id}")
def update_property(id: str, body: dict, db: Session = Depends(get_db)):
    prop = db.query(Property).filter(Property.id == id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    original = json.loads(prop.original_data or "{}")
    edited_fields = json.loads(prop.edited_fields or "[]")

    for key, value in body.items():
        if key in ("id", "scraped_at", "original_data", "source", "source_listing_id"):
            continue
        if hasattr(prop, key):
            orig_val = original.get(key)
            if str(value) != str(orig_val) and key not in edited_fields:
                edited_fields.append(key)
            setattr(prop, key, value)

    prop.edited_fields = json.dumps(edited_fields)

    if prop.status not in ("ready", "published"):
        if "status" in body:
            prop.status = body["status"]
        else:
            prop.status = "edited"

    prop.updated_at = datetime.utcnow().isoformat()
    db.commit()
    db.refresh(prop)
    return prop_to_dict(prop)


@router.delete("/properties/{id}")
def delete_property(id: str, db: Session = Depends(get_db)):
    prop = db.query(Property).filter(Property.id == id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    db.delete(prop)
    db.commit()
    return {"ok": True}
