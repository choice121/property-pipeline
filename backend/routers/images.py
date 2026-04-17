import io
import json
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from database.db import get_db
from database.repository import Repository
from services import image_service

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Watermark flag persistence ─────────────────────────────────────────────────
_WM_FLAGS_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "data", "watermark_flags.json")
_WM_FLAGS_FILE = os.path.normpath(_WM_FLAGS_FILE)
_wm_file_lock = threading.Lock()


def _load_wm_flags() -> dict:
    """Load persisted watermark flags from disk. Returns {prop_id: flag_data}."""
    try:
        if os.path.exists(_WM_FLAGS_FILE):
            with open(_WM_FLAGS_FILE, "r") as f:
                return json.load(f)
    except Exception as e:
        logger.warning("Could not load watermark flags: %s", e)
    return {}


def _save_wm_flags(flags: dict) -> None:
    """Persist watermark flags dict to disk."""
    try:
        os.makedirs(os.path.dirname(_WM_FLAGS_FILE), exist_ok=True)
        with _wm_file_lock:
            with open(_WM_FLAGS_FILE, "w") as f:
                json.dump(flags, f)
    except Exception as e:
        logger.warning("Could not save watermark flags: %s", e)


def _merge_wm_flags(new_results: list) -> None:
    """Merge a list of scan result dicts into the persisted flags file."""
    flags = _load_wm_flags()
    for r in new_results:
        pid = str(r.get("id", ""))
        if not pid:
            continue
        flags[pid] = {
            "id": pid,
            "address": r.get("address", ""),
            "city": r.get("city", ""),
            "state": r.get("state", ""),
            "flagged": r.get("flagged", 0),
            "checked": r.get("checked", 0),
            "total_images": r.get("total_images", 0),
            "status": r.get("status", ""),
            "scanned_at": r.get("scanned_at") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
    _save_wm_flags(flags)


# ── Watermark scan background job state ───────────────────────────────────────
_wm_state = {
    "running": False,
    "total": 0,
    "scanned": 0,
    "flagged": [],
    "started_at": None,
    "finished_at": None,
    "error": None,
}
_wm_lock = threading.Lock()

REFERER_MAP = {
    "rdcpix.com":       "https://www.realtor.com/",
    "realtor.com":      "https://www.realtor.com/",
    "zillowstatic.com": "https://www.zillow.com/",
    "zillow.com":       "https://www.zillow.com/",
    "cdn-redfin.com":   "https://www.redfin.com/",
    "redfin.com":       "https://www.redfin.com/",
    "trulia.com":       "https://www.trulia.com/",
    "cloudinary.com":   None,
    "amazonaws.com":    None,
}


def _get_referer(url: str) -> str | None:
    try:
        hostname = urlparse(url).hostname or ""
        for domain, referer in REFERER_MAP.items():
            if hostname.endswith(domain):
                return referer
    except Exception:
        pass
    return None


def _is_allowed_domain(url: str) -> bool:
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        hostname = parsed.hostname or ""
        for domain in REFERER_MAP:
            if hostname.endswith(domain):
                return True
    except Exception:
        pass
    return False


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORAGE_DIR = os.path.realpath(os.path.join(BASE_DIR, "storage", "images"))


@router.get("/proxy-image")
def proxy_image(url: str = Query(..., description="External image URL to proxy")):
    if not _is_allowed_domain(url):
        raise HTTPException(status_code=400, detail="Domain not allowed for proxying")

    referer = _get_referer(url)
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Sec-Fetch-Dest": "image",
        "Sec-Fetch-Mode": "no-cors",
        "Sec-Fetch-Site": "same-site",
    }
    if referer:
        headers["Referer"] = referer
        headers["Origin"] = referer.rstrip("/")

    try:
        with httpx.Client(timeout=20, follow_redirects=True) as client:
            resp = client.get(url, headers=headers)
    except Exception as e:
        logger.warning("Proxy fetch failed for %s: %s", url, e)
        raise HTTPException(status_code=502, detail="Failed to fetch image")

    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail="Image not available")

    content_type = resp.headers.get("content-type", "image/jpeg")
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=502, detail="Response is not an image")

    return Response(
        content=resp.content,
        media_type=content_type,
        headers={
            "Cache-Control": "public, max-age=86400",
            "Access-Control-Allow-Origin": "*",
        },
    )


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
def delete_image(id: str, index: int, repo: Repository = Depends(get_db)):
    prop = repo.get(id)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    new_paths = image_service.delete_image(id, index)
    prop.local_image_paths = json.dumps(new_paths)
    try:
        repo.save(prop)
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to update image list")
    return prop.to_dict()


class ReorderRequest(BaseModel):
    order: List[int]


@router.put("/properties/{id}/images/reorder")
def reorder_images(id: str, body: ReorderRequest, repo: Repository = Depends(get_db)):
    prop = repo.get(id)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    new_paths = image_service.reorder_images(id, body.order)
    prop.local_image_paths = json.dumps(new_paths)
    try:
        repo.save(prop)
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to save new image order")
    return prop.to_dict()


# ── Watermark Scan ─────────────────────────────────────────────────────────────

_SCAN_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
}

_REFERER_DOMAINS = {
    "rdcpix.com":       "https://www.realtor.com/",
    "realtor.com":      "https://www.realtor.com/",
    "zillowstatic.com": "https://www.zillow.com/",
    "zillow.com":       "https://www.zillow.com/",
    "cdn-redfin.com":   "https://www.redfin.com/",
    "redfin.com":       "https://www.redfin.com/",
}


def _referer_for(url: str) -> str | None:
    try:
        host = urlparse(url).hostname or ""
        for domain, ref in _REFERER_DOMAINS.items():
            if host.endswith(domain):
                return ref
    except Exception:
        pass
    return None


def _fetch_image_bytes(url: str, timeout: int = 8) -> bytes | None:
    try:
        headers = dict(_SCAN_HEADERS)
        ref = _referer_for(url)
        if ref:
            headers["Referer"] = ref
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            resp = client.get(url, headers=headers)
        if resp.status_code != 200:
            return None
        ct = resp.headers.get("content-type", "")
        if not ct.startswith("image/"):
            return None
        if len(resp.content) < 5 * 1024:
            return None
        return resp.content
    except Exception:
        return None


def _scan_property_for_watermarks(prop) -> dict:
    """
    Download the first 4 images for a property and check each for watermarks.
    Returns a result dict with flagged image count and property metadata.
    """
    try:
        urls = json.loads(prop.original_image_urls or "[]")
    except Exception:
        urls = []

    if not urls:
        return {"id": str(prop.id), "watermarked": False, "flagged": 0, "checked": 0}

    sample = urls[:4]
    flagged = 0
    checked = 0

    for url in sample:
        data = _fetch_image_bytes(url)
        if data is None:
            continue
        checked += 1
        if image_service._has_branded_overlay(data):
            flagged += 1

    return {
        "id": str(prop.id),
        "address": prop.address or "(no address)",
        "city": prop.city or "",
        "state": prop.state or "",
        "watermarked": flagged > 0,
        "flagged": flagged,
        "checked": checked,
        "total_images": len(urls),
        "status": prop.status or "unknown",
    }


def _wm_scan_worker():
    """Background thread: fetch all properties, scan for watermarks, update _wm_state."""
    from database.repository import get_repo
    repo = get_repo()

    try:
        props = repo.list()

        with _wm_lock:
            _wm_state.update({
                "running": True,
                "total": len(props),
                "scanned": 0,
                "flagged": [],
                "started_at": time.time(),
                "finished_at": None,
                "error": None,
            })

        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {executor.submit(_scan_property_for_watermarks, p): p for p in props}
            for future in as_completed(futures):
                try:
                    result = future.result()
                except Exception as e:
                    logger.warning("Watermark scan worker error: %s", e)
                    result = None

                with _wm_lock:
                    _wm_state["scanned"] += 1
                    if result and result.get("watermarked"):
                        _wm_state["flagged"].append(result)

    except Exception as e:
        with _wm_lock:
            _wm_state["error"] = str(e)
        logger.error("Watermark scan worker crashed: %s", e)
    finally:
        with _wm_lock:
            _wm_state["flagged"].sort(key=lambda r: r.get("address", ""))
            _wm_state["running"] = False
            _wm_state["finished_at"] = time.time()
            finished_flagged = list(_wm_state["flagged"])

        # Persist: replace all flags with the new scan's results (full rescan overwrites)
        # First clear all existing flags, then write the new ones
        _save_wm_flags({})
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        new_flags = {}
        for r in finished_flagged:
            pid = str(r.get("id", ""))
            if pid:
                new_flags[pid] = {**r, "id": pid, "scanned_at": ts}
        _save_wm_flags(new_flags)
        logger.info("Watermark scan complete — persisted %d flags", len(new_flags))


@router.post("/wm-scan/start")
def watermark_scan_start():
    """
    Start a background watermark scan of all properties.
    Returns immediately — poll /wm-scan/status for progress.
    """
    with _wm_lock:
        if _wm_state["running"]:
            return {"ok": False, "message": "Scan already running.", "state": dict(_wm_state)}

    t = threading.Thread(target=_wm_scan_worker, daemon=True)
    t.start()
    return {"ok": True, "message": "Watermark scan started in background."}


@router.get("/wm-scan/status")
def watermark_scan_status():
    """Return current watermark scan progress and results."""
    with _wm_lock:
        state = dict(_wm_state)
        state["flagged"] = list(state["flagged"])
        state["total_flagged"] = len(state["flagged"])
    return state


@router.post("/images/watermark-scan")
def watermark_scan(repo: Repository = Depends(get_db)):
    """Legacy blocking scan — kept for backward compatibility."""
    props = repo.list()
    if not props:
        return {"flagged": [], "scanned": 0, "total_flagged": 0}

    results = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(_scan_property_for_watermarks, p): p for p in props}
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception as e:
                logger.warning("Watermark scan error: %s", e)

    flagged = sorted([r for r in results if r["watermarked"]], key=lambda r: r.get("address", ""))
    return {"flagged": flagged, "scanned": len(results), "total_flagged": len(flagged)}


@router.get("/wm-scan/flagged")
def watermark_get_flagged(repo: Repository = Depends(get_db)):
    """
    Return all persistently flagged watermark properties, enriched with full property data.
    Results survive browser refresh and server restarts.
    """
    flags = _load_wm_flags()
    if not flags:
        return {"flagged": [], "total": 0, "scanned_at": None}

    # Enrich flags with latest full property data where available
    prop_ids = list(flags.keys())
    enriched = []
    last_scanned_at = None

    for pid in prop_ids:
        flag = flags[pid]
        if not last_scanned_at or (flag.get("scanned_at", "") > last_scanned_at):
            last_scanned_at = flag.get("scanned_at")
        try:
            prop = repo.get(pid)
        except Exception:
            prop = None

        if prop:
            entry = prop.to_dict()
            entry["_wm"] = flag
        else:
            # Property was deleted — skip it and remove from flags
            continue
        enriched.append(entry)

    # Prune flags for deleted properties
    valid_ids = {e["id"] for e in enriched}
    if len(valid_ids) < len(flags):
        pruned = {k: v for k, v in flags.items() if k in valid_ids}
        _save_wm_flags(pruned)

    enriched.sort(key=lambda p: (p.get("address") or ""))
    return {"flagged": enriched, "total": len(enriched), "scanned_at": last_scanned_at}


@router.post("/wm-scan/unflag/{prop_id}")
def watermark_unflag(prop_id: str):
    """Remove a single property from the persisted watermark flags (Unmark action)."""
    flags = _load_wm_flags()
    if prop_id in flags:
        del flags[prop_id]
        _save_wm_flags(flags)
        return {"ok": True, "remaining": len(flags)}
    return {"ok": True, "remaining": len(flags)}


@router.delete("/wm-scan/flags")
def watermark_clear_flags():
    """Clear all persisted watermark flags (dismiss results panel without deleting properties)."""
    _save_wm_flags({})
    return {"ok": True}
