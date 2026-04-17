import logging
import threading
import time

from fastapi import APIRouter, Depends, HTTPException

from database.db import get_db
from database.repository import Repository
from services import publisher_service

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Bulk publish state ────────────────────────────────────────────────────────
_bulk_state = {
    "running": False,
    "total": 0,
    "done": 0,
    "failed": 0,
    "skipped": 0,
    "current": None,
    "errors": [],
    "started_at": None,
    "finished_at": None,
}
_bulk_lock = threading.Lock()


def _bulk_publish_worker(ids: list[str]):
    global _bulk_state
    with _bulk_lock:
        _bulk_state.update({
            "running": True,
            "total": len(ids),
            "done": 0,
            "failed": 0,
            "skipped": 0,
            "current": None,
            "errors": [],
            "started_at": time.time(),
            "finished_at": None,
        })

    from database.repository import get_repo

    for prop_id in ids:
        with _bulk_lock:
            _bulk_state["current"] = prop_id

        try:
            repo = get_repo()
            prop = repo.get(prop_id)

            if prop is None:
                with _bulk_lock:
                    _bulk_state["skipped"] += 1
                continue

            if prop.choice_property_id:
                with _bulk_lock:
                    _bulk_state["skipped"] += 1
                continue

            publisher_service.publish(prop, repo)
            with _bulk_lock:
                _bulk_state["done"] += 1

        except Exception as e:
            logger.warning("Bulk publish failed for %s: %s", prop_id, e)
            with _bulk_lock:
                _bulk_state["failed"] += 1
                _bulk_state["errors"].append({"id": prop_id, "error": str(e)[:120]})

    with _bulk_lock:
        _bulk_state["running"] = False
        _bulk_state["current"] = None
        _bulk_state["finished_at"] = time.time()


@router.post("/publish/{id}")
def publish_property(id: str, repo: Repository = Depends(get_db)):
    prop = repo.get(id)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    if prop.choice_property_id:
        raise HTTPException(
            status_code=400,
            detail=f"Property is already published (ID: {prop.choice_property_id})"
        )

    try:
        result = publisher_service.publish(prop, repo)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except KeyError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Missing environment variable: {e}. Check that all credentials are configured."
        )
    except Exception as e:
        logger.exception("Unexpected error publishing property %s", id)
        raise HTTPException(status_code=500, detail=f"Publish failed: {str(e)}")

    return result


@router.post("/publish/{id}/refresh-images")
def refresh_published_images(id: str, repo: Repository = Depends(get_db)):
    prop = repo.get(id)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    if not prop.choice_property_id:
        raise HTTPException(status_code=400, detail="Property has not been published yet")

    try:
        result = publisher_service.refresh_images(prop, repo)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except KeyError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Missing environment variable: {e}. Check that all credentials are configured."
        )
    except Exception as e:
        logger.exception("Unexpected error refreshing images for property %s", id)
        raise HTTPException(status_code=500, detail=f"Image refresh failed: {str(e)}")

    return result


@router.post("/publish/{id}/sync-fields")
def sync_published_fields(id: str, repo: Repository = Depends(get_db)):
    prop = repo.get(id)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    if not prop.choice_property_id:
        raise HTTPException(status_code=400, detail="Property has not been published yet")

    try:
        result = publisher_service.sync_fields(prop, repo)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except KeyError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Missing environment variable: {e}. Check that all credentials are configured."
        )
    except Exception as e:
        logger.exception("Unexpected error syncing fields for property %s", id)
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")

    return result


@router.post("/publish/{id}/set-listing-status")
def set_listing_status(id: str, body: dict, repo: Repository = Depends(get_db)):
    prop = repo.get(id)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    status = body.get("status", "")
    try:
        result = publisher_service.set_listing_status(prop, status, repo)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except KeyError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Missing environment variable: {e}. Check that all credentials are configured."
        )
    except Exception as e:
        logger.exception("Unexpected error setting listing status for property %s", id)
        raise HTTPException(status_code=500, detail=f"Status update failed: {str(e)}")

    return result


@router.post("/bulk-publish/start")
def start_bulk_publish(body: dict = None, repo: Repository = Depends(get_db)):
    global _bulk_state
    with _bulk_lock:
        if _bulk_state["running"]:
            return {"ok": False, "message": "Bulk publish is already running.", "state": dict(_bulk_state)}

    ids = (body or {}).get("ids") or None

    if ids is None:
        from database.supabase_client import get_supabase
        sb = get_supabase()
        result = (
            sb.table("pipeline_properties")
            .select("id, local_image_paths")
            .is_("choice_property_id", "null")
            .not_.in_("status", ["published", "archived", "rented"])
            .execute()
        )
        ids = [
            row["id"] for row in (result.data or [])
            if row.get("local_image_paths") and row["local_image_paths"] not in ("[]", "null", "", None)
        ]

    if not ids:
        return {"ok": False, "message": "No eligible unpublished properties with downloaded images found.", "state": dict(_bulk_state)}

    t = threading.Thread(target=_bulk_publish_worker, args=(ids,), daemon=True)
    t.start()

    return {"ok": True, "total": len(ids), "state": dict(_bulk_state)}


@router.get("/bulk-publish/status")
def get_bulk_publish_status():
    with _bulk_lock:
        return dict(_bulk_state)
