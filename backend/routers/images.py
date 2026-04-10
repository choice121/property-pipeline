import json
import os
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database.db import get_db
from database.models import Property
from services import image_service

router = APIRouter()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORAGE_DIR = os.path.realpath(os.path.join(BASE_DIR, "storage", "images"))


def prop_to_dict(prop: Property) -> dict:
    return {c.name: getattr(prop, c.name) for c in prop.__table__.columns}


@router.get("/images/{property_id}/{filename}")
def serve_image(property_id: str, filename: str):
    safe_storage = STORAGE_DIR
    requested = os.path.realpath(os.path.join(safe_storage, property_id, filename))
    if not requested.startswith(safe_storage + os.sep):
        raise HTTPException(status_code=400, detail="Invalid image path")
    if not os.path.isfile(requested):
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(requested)


@router.delete("/properties/{id}/images/{index}")
def delete_image(id: str, index: int, db: Session = Depends(get_db)):
    prop = db.query(Property).filter(Property.id == id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    new_paths = image_service.delete_image(id, index)
    prop.local_image_paths = json.dumps(new_paths)
    try:
        db.commit()
        db.refresh(prop)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to update image list")
    return prop_to_dict(prop)


class ReorderRequest(BaseModel):
    order: List[int]


@router.put("/properties/{id}/images/reorder")
def reorder_images(id: str, body: ReorderRequest, db: Session = Depends(get_db)):
    prop = db.query(Property).filter(Property.id == id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    new_paths = image_service.reorder_images(id, body.order)
    prop.local_image_paths = json.dumps(new_paths)
    try:
        db.commit()
        db.refresh(prop)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to save new image order")
    return prop_to_dict(prop)
