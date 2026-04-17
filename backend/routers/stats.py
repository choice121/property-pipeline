import json
import logging
import threading

from fastapi import APIRouter, BackgroundTasks, Depends

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
def start_bulk_download(background_tasks: BackgroundTasks, repo: Repository = Depends(get_db)):
    with _bulk_img_lock:
        if _bulk_img_state["running"]:
            return {"ok": False, "message": "Already running", "state": dict(_bulk_img_state)}

    all_props = repo.list()
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
