import io
import json
import logging
import os
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


@router.post("/images/watermark-scan")
def watermark_scan(repo: Repository = Depends(get_db)):
    """
    Scan all properties for watermarked photos.
    Downloads up to 4 images per property and runs the branded-overlay detector.
    Returns a list of all properties with at least one flagged image.
    """
    props = repo.list()
    if not props:
        return {"flagged": [], "scanned": 0, "total_flagged": 0}

    results = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(_scan_property_for_watermarks, p): p for p in props}
        for future in as_completed(futures):
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                logger.warning("Watermark scan error: %s", e)

    flagged = [r for r in results if r["watermarked"]]
    flagged.sort(key=lambda r: r.get("address", ""))

    return {
        "flagged": flagged,
        "scanned": len(results),
        "total_flagged": len(flagged),
    }
