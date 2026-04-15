import logging

from fastapi import APIRouter, Depends, HTTPException

from database.db import get_db
from database.repository import Repository
from services import publisher_service

logger = logging.getLogger(__name__)
router = APIRouter()


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
