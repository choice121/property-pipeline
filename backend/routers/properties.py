import json
import logging
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query

from database.db import get_db
from database.repository import Repository, PropertyRecord
from services import publisher_service

logger = logging.getLogger(__name__)
router = APIRouter()


def _auto_sync_to_live(prop, repo):
    try:
        publisher_service.sync_fields(prop, repo)
        logger.info('Auto-synced property %s to live site', prop.id)
    except Exception as e:
        logger.warning('Auto-sync failed for property %s: %s', prop.id, e)


@router.post("/properties")
def create_property(body: dict, repo: Repository = Depends(get_db)):
    prop_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    allowed = {
        "title", "property_type", "address", "city", "state", "zip", "county",
        "bedrooms", "bathrooms", "half_bathrooms", "total_bathrooms", "square_footage",
        "lot_size_sqft", "year_built", "floors", "unit_number", "total_units",
        "monthly_rent", "security_deposit", "last_months_rent", "application_fee",
        "pet_deposit", "admin_fee", "parking_fee", "move_in_special",
        "parking", "garage_spaces", "pets_allowed", "pet_details", "pet_types_allowed",
        "pet_weight_limit", "smoking_allowed", "description", "virtual_tour_url",
        "available_date", "lease_terms", "minimum_lease_months", "showing_instructions",
        "amenities", "appliances", "utilities_included", "flooring",
        "heating_type", "cooling_type", "laundry_type",
        "has_basement", "has_central_air",
    }

    fields = {k: v for k, v in body.items() if k in allowed and v not in (None, "", [])}

    prop = PropertyRecord(
        id=prop_id,
        source="manual",
        status="draft",
        scraped_at=now,
        updated_at=now,
        original_data="{}",
        **fields,
    )

    try:
        repo.save(prop)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create property: {e}")

    return prop.to_dict()


@router.get("/properties")
def list_properties(
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    sort: Optional[str] = Query("scraped_at"),
    repo: Repository = Depends(get_db),
):
    props = repo.list(status=status, search=search, sort=sort)
    return [p.to_dict() for p in props]


@router.get("/properties/{id}")
def get_property(id: str, repo: Repository = Depends(get_db)):
    prop = repo.get(id)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    return prop.to_dict()


@router.put("/properties/{id}")
def update_property(id: str, body: dict, background_tasks: BackgroundTasks, repo: Repository = Depends(get_db)):
    prop = repo.get(id)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    try:
        original = json.loads(prop.original_data or "{}")
    except Exception:
        original = {}
    try:
        edited_fields = json.loads(prop.edited_fields or "[]")
    except Exception:
        edited_fields = []

    log_updates = []
    for key, value in body.items():
        if key in ("id", "scraped_at", "original_data", "source", "source_listing_id"):
            continue
        if hasattr(prop, key):
            orig_val = original.get(key)
            if str(value) != str(orig_val) and key not in edited_fields:
                edited_fields.append(key)
                log_entry = repo.get_enrichment_log(id, key, was_overridden=False)
                if log_entry:
                    log_updates.append((log_entry, str(value)))
            setattr(prop, key, value)

    for log_entry, human_val in log_updates:
        log_entry.was_overridden = True
        log_entry.human_value = human_val
        repo.update_log(log_entry)

    prop.edited_fields = json.dumps(edited_fields)

    if prop.status not in ("ready", "published"):
        if "status" in body:
            prop.status = body["status"]
        else:
            prop.status = "edited"

    prop.updated_at = datetime.utcnow().isoformat()
    try:
        repo.save(prop)
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to save property")

    if prop.choice_property_id:
        background_tasks.add_task(_auto_sync_to_live, prop, repo)

    return prop.to_dict()


@router.delete("/properties/{id}")
def delete_property(id: str, repo: Repository = Depends(get_db)):
    prop = repo.get(id)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    try:
        repo.delete(id)
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to delete property")
    return {"ok": True}


@router.post("/properties/bulk-action")
def bulk_action(body: dict, repo: Repository = Depends(get_db)):
    ids = body.get("ids", [])
    action = body.get("action", "")
    valid_actions = {"ready", "delete", "archive", "sync"}

    if not ids:
        raise HTTPException(status_code=400, detail="No property IDs provided")
    if action not in valid_actions:
        raise HTTPException(status_code=400, detail=f"Invalid action '{action}'. Must be one of: {', '.join(sorted(valid_actions))}")

    results = {"success": 0, "failed": 0, "errors": []}
    for prop_id in ids:
        try:
            prop = repo.get(prop_id)
            if not prop:
                results["failed"] += 1
                results["errors"].append(f"{prop_id}: not found")
                continue

            if action == "ready":
                prop.status = "ready"
                prop.updated_at = datetime.utcnow().isoformat()
                repo.save(prop)
            elif action == "delete":
                repo.delete(prop_id)
            elif action == "archive":
                prop.status = "archived"
                prop.updated_at = datetime.utcnow().isoformat()
                repo.save(prop)
            elif action == "sync":
                if not prop.choice_property_id:
                    results["failed"] += 1
                    results["errors"].append(f"{prop_id}: not published yet")
                    continue
                publisher_service.sync_fields(prop, repo)

            results["success"] += 1
        except Exception as e:
            results["failed"] += 1
            results["errors"].append(f"{prop_id}: {str(e)}")

    return results
