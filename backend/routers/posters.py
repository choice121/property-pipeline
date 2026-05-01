"""Poster Attribution Router — Phase 8

Endpoints for browsing and managing landlord poster profiles.
"""
import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException

from database.supabase_client import get_supabase, get_pipeline_schema
from services import poster_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/posters", tags=["posters"])


@router.get("")
def list_posters():
    """Return all landlord profiles used as listing posters, with property counts."""
    client = get_supabase()
    pipeline = get_pipeline_schema()

    landlords = poster_service.get_all_posters(client)

    try:
        props_result = pipeline.table("pipeline_properties").select(
            "poster_landlord_id"
        ).not_.is_("poster_landlord_id", "null").execute()
        prop_rows = props_result.data or []
    except Exception as e:
        logger.warning("Could not fetch property counts: %s", e)
        prop_rows = []

    count_map: dict[str, int] = {}
    for r in prop_rows:
        lid = r.get("poster_landlord_id")
        if lid:
            count_map[lid] = count_map.get(lid, 0) + 1

    for l in landlords:
        l["property_count"] = count_map.get(l["id"], 0)

    return landlords


@router.get("/{landlord_id}")
def get_poster(landlord_id: str):
    """Return a single landlord profile with associated pipeline properties."""
    client = get_supabase()
    pipeline = get_pipeline_schema()

    poster = poster_service.get_poster_by_id(landlord_id, client)
    if not poster:
        raise HTTPException(status_code=404, detail="Poster not found")

    try:
        props_result = pipeline.table("pipeline_properties").select(
            "id,title,address,city,state,status,data_quality_score,choice_property_id"
        ).eq("poster_landlord_id", landlord_id).execute()
        poster["properties"] = props_result.data or []
    except Exception as e:
        logger.warning("Could not fetch properties for poster %s: %s", landlord_id, e)
        poster["properties"] = []

    return poster


def _run_recalculate():
    pipeline = get_pipeline_schema()
    public = get_supabase()
    result = poster_service.recalculate_all(pipeline, public)
    logger.info("Recalculate posters complete: %s", result)


@router.post("/recalculate")
def recalculate_posters(background_tasks: BackgroundTasks):
    """
    Walk all pipeline properties with agent/broker names and resolve/create
    poster landlord profiles. Runs in the background.
    """
    background_tasks.add_task(_run_recalculate)
    return {"ok": True, "message": "Recalculation started in background."}


@router.delete("/cache")
def clear_poster_cache():
    """Flush the in-process poster name cache."""
    poster_service.clear_cache()
    return {"ok": True, "message": "Poster cache cleared."}
