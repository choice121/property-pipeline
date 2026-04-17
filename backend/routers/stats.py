import json
import logging
import os
import threading

from fastapi import APIRouter, BackgroundTasks, Body, Depends

from database.db import get_db
from database.repository import Repository
from services import image_service

logger = logging.getLogger(__name__)
router = APIRouter()

_bulk_img_state: dict = {"running": False, "total": 0, "done": 0, "failed": 0}
_bulk_img_lock = threading.Lock()


@router.get("/stats/quality")
def quality_stats(repo: Repository = Depends(get_db)):
    return repo.quality_stats_by_source()


@router.get("/stats/scrape-runs")
def scrape_runs(limit: int = 50, repo: Repository = Depends(get_db)):
    return repo.list_scrape_runs(limit=limit)


@router.get("/img-batch/status")
def bulk_download_status():
    return dict(_bulk_img_state)


@router.post("/img-batch/start")
def start_bulk_download(
    background_tasks: BackgroundTasks,
    repo: Repository = Depends(get_db),
    force: bool = Body(default=False),
):
    with _bulk_img_lock:
        if _bulk_img_state["running"]:
            return {"ok": False, "message": "Already running", "state": dict(_bulk_img_state)}

    all_props = repo.list()

    if force:
        # Include properties with no local paths OR paths that no longer exist on disk (migration case)
        needs = [
            p for p in all_props
            if json.loads(p.original_image_urls or "[]") and (
                not json.loads(p.local_image_paths or "[]") or
                any(
                    not os.path.exists(f)
                    for f in json.loads(p.local_image_paths or "[]")
                )
            )
        ]
    else:
        needs = [
            p for p in all_props
            if json.loads(p.original_image_urls or "[]")
            and not json.loads(p.local_image_paths or "[]")
        ]

    if not needs:
        return {"ok": True, "message": "All properties already have downloaded images.", "state": dict(_bulk_img_state)}

    with _bulk_img_lock:
        _bulk_img_state.update(running=True, total=len(needs), done=0, failed=0)

    background_tasks.add_task(_run_bulk_download, needs)
    return {"ok": True, "queued": len(needs), "state": dict(_bulk_img_state)}


@router.post("/library/restore")
def restore_library(
    background_tasks: BackgroundTasks,
    repo: Repository = Depends(get_db),
):
    """
    Full library restore: force re-download all images from original URLs
    (including stale paths from migration) and run AI enrichment on every property.
    """
    from services.enrichment_queue import enqueue_enrichment

    all_props = repo.list()

    # Image restore: target properties with no local paths OR stale paths (files missing on disk)
    needs_images = [
        p for p in all_props
        if json.loads(p.original_image_urls or "[]") and (
            not json.loads(p.local_image_paths or "[]") or
            any(
                not os.path.exists(f)
                for f in json.loads(p.local_image_paths or "[]")
            )
        )
    ]

    images_queued = 0
    with _bulk_img_lock:
        if not _bulk_img_state["running"] and needs_images:
            _bulk_img_state.update(running=True, total=len(needs_images), done=0, failed=0)
            background_tasks.add_task(_run_bulk_download, needs_images)
            images_queued = len(needs_images)

    # AI enrichment: queue every property (force mode)
    for prop in all_props:
        background_tasks.add_task(enqueue_enrichment, prop.id)

    return {
        "ok": True,
        "images_queued": images_queued,
        "enrichment_queued": len(all_props),
        "message": (
            f"Restoring {images_queued} properties' photos and running AI enrichment "
            f"on all {len(all_props)} properties. This runs in the background — "
            f"refresh in a few minutes to see results."
        ),
    }


def _run_bulk_download(props: list):
    from database.repository import get_repo
    repo = get_repo()

    for p in props:
        prop_id = p.id
        urls = json.loads(p.original_image_urls or "[]")
        try:
            paths = image_service.download_images(prop_id, urls)
            record = repo.get(prop_id)
            if record:
                record.local_image_paths = json.dumps(paths)
                try:
                    repo.save(record)
                except Exception as e:
                    logger.error("Failed to save image paths for %s: %s", prop_id, e)
            with _bulk_img_lock:
                if paths:
                    _bulk_img_state["done"] += 1
                else:
                    _bulk_img_state["failed"] += 1
        except Exception as e:
            logger.error("Bulk image download failed for %s: %s", prop_id, e)
            with _bulk_img_lock:
                _bulk_img_state["failed"] += 1

    with _bulk_img_lock:
        _bulk_img_state["running"] = False
    logger.info(
        "Bulk image download complete: %d done, %d failed",
        _bulk_img_state["done"], _bulk_img_state["failed"]
    )
