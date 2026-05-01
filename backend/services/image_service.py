import io
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Tuple

import httpx

from services.http_utils import random_headers

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORAGE_DIR = os.path.join(BASE_DIR, "storage", "images")


def get_property_dir(property_id: str) -> str:
    return os.path.join(STORAGE_DIR, property_id)


def _has_branded_overlay(image_bytes: bytes) -> bool:
    """
    Detect branded text watermarks burned into property photos.
    Checks for high-contrast semi-transparent overlay bands in the bottom
    quarter of the image — the typical placement for real estate logo watermarks.
    Returns True if a suspicious overlay pattern is found.
    """
    try:
        from PIL import Image, ImageFilter
        import statistics

        img = Image.open(io.BytesIO(image_bytes)).convert("L")
        width, height = img.size
        if width < 100 or height < 100:
            return False

        band_top = int(height * 0.72)
        band_bottom = int(height * 0.92)
        band_width = int(width * 0.60)

        region = img.crop((0, band_top, band_width, band_bottom))
        pixels = list(region.getdata())

        if len(pixels) < 50:
            return False

        mean = sum(pixels) / len(pixels)
        variance = sum((p - mean) ** 2 for p in pixels) / len(pixels)
        std_dev = variance ** 0.5

        bright = sum(1 for p in pixels if p > 200)
        bright_ratio = bright / len(pixels)

        if std_dev > 38 and bright_ratio > 0.12:
            return True

        return False
    except Exception as e:
        logger.debug("Watermark image check failed: %s", e)
        return False


def _is_quality_image(content: bytes) -> tuple[bool, str]:
    """
    Check image dimensions and detect near-blank/solid-color placeholders.
    Returns (is_valid, reason).
    """
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(content))
        w, h = img.size

        if w < 200 or h < 150:
            return False, "too_small_dimensions"

        if w / h > 5 or h / w > 5:
            return False, "extreme_aspect_ratio"

        if img.mode in ("RGB", "RGBA"):
            img_small = img.resize((20, 20)).convert("RGB")
            pixels = list(img_small.getdata())
            r_vals = [p[0] for p in pixels]
            if max(r_vals) - min(r_vals) < 15:
                return False, "near_blank"

        return True, "ok"
    except Exception:
        return False, "cannot_decode"


_TRANSIENT_DOWNLOAD_EXC = (
    httpx.ConnectError,
    httpx.ReadTimeout,
    httpx.WriteTimeout,
    httpx.PoolTimeout,
    httpx.RemoteProtocolError,
)


def _download_one(url: str, filepath: str) -> tuple[bool, str]:
    """Download a single image. Returns (success, reason).

    Phase 2 (2.4): retry once on transport-level errors only. Quality/content-
    type/watermark rejections are deterministic — retrying them is wasted I/O.
    Reason codes: ok | http_<code> | not_image | too_small | low_quality |
                  watermarked | transient | error
    """
    last_reason = "error"
    for attempt in (1, 2):
        try:
            with httpx.Client(timeout=20, follow_redirects=True) as client:
                resp = client.get(url, headers=random_headers())
            if resp.status_code != 200:
                return False, f"http_{resp.status_code}"
            content_type = resp.headers.get("content-type", "")
            if not content_type.startswith("image/"):
                return False, "not_image"
            if len(resp.content) < 5 * 1024:
                return False, "too_small"
            valid, reason = _is_quality_image(resp.content)
            if not valid:
                logger.debug("Skipping image %s: %s", url, reason)
                return False, "low_quality"
            if _has_branded_overlay(resp.content):
                logger.info("Skipping watermarked image: %s", url)
                return False, "watermarked"
            with open(filepath, "wb") as f:
                f.write(resp.content)
            return True, "ok"
        except _TRANSIENT_DOWNLOAD_EXC as exc:
            last_reason = "transient"
            if attempt == 1:
                logger.debug("Transient download error for %s (%s) — retrying", url, type(exc).__name__)
                continue
        except Exception as exc:
            logger.debug("Download error for %s: %s", url, exc)
            return False, "error"
    return False, last_reason


def download_images(property_id: str, image_urls: list) -> Tuple[List[str], dict]:
    """Download images for a property.

    Returns:
      (final_paths, reason_counts) — Phase 2 (2.5): callers now receive the
      per-reason breakdown so they can persist it alongside the image paths.
      reason_counts keys: 'ok' | 'http_N' | 'not_image' | 'too_small' |
                          'low_quality' | 'watermarked' | 'transient' | 'error'
    """
    prop_dir = get_property_dir(property_id)
    os.makedirs(prop_dir, exist_ok=True)

    indexed = list(enumerate(image_urls, start=1))

    def fetch(args):
        index, url = args
        filepath = os.path.join(prop_dir, f"{index}.jpg")
        success, reason = _download_one(url, filepath)
        return index, success, reason

    results = {}
    reason_counts: dict[str, int] = {}
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(fetch, item): item[0] for item in indexed}
        for future in as_completed(futures):
            index, success, reason = future.result()
            results[index] = success
            reason_counts[reason] = reason_counts.get(reason, 0) + 1

    if reason_counts:
        logger.info(
            "download_images[%s]: requested=%d %s",
            property_id, len(image_urls),
            " ".join(f"{k}={v}" for k, v in sorted(reason_counts.items())),
        )

    saved_indices = sorted(i for i, ok in results.items() if ok)

    final_paths = []
    for new_pos, old_index in enumerate(saved_indices, start=1):
        old_path = os.path.join(prop_dir, f"{old_index}.jpg")
        new_path = os.path.join(prop_dir, f"{new_pos}.jpg")
        if old_path != new_path and os.path.exists(old_path):
            os.rename(old_path, new_path)
        final_paths.append(f"storage/images/{property_id}/{new_pos}.jpg")

    return final_paths, reason_counts


def delete_image(property_id: str, index: int) -> List[str]:
    prop_dir = get_property_dir(property_id)
    target = os.path.join(prop_dir, f"{index}.jpg")

    if os.path.exists(target):
        os.remove(target)

    def _parse_img_index(fname: str) -> int | None:
        """Return the integer index from '3.jpg', or None for non-integer names."""
        try:
            return int(fname.rsplit(".", 1)[0])
        except (ValueError, IndexError):
            return None

    existing = sorted(
        [f for f in os.listdir(prop_dir) if f.endswith(".jpg") and _parse_img_index(f) is not None],
        key=lambda x: _parse_img_index(x)
    )

    for i, fname in enumerate(existing, start=1):
        old_path = os.path.join(prop_dir, fname)
        new_path = os.path.join(prop_dir, f"{i}.jpg")
        if old_path != new_path:
            os.rename(old_path, new_path)

    total = len(existing)
    return [f"storage/images/{property_id}/{i}.jpg" for i in range(1, total + 1)]


def reorder_images(property_id: str, new_order: List[int]) -> List[str]:
    prop_dir = get_property_dir(property_id)

    temp_names = []
    for i, original_index in enumerate(new_order):
        src = os.path.join(prop_dir, f"{original_index}.jpg")
        tmp = os.path.join(prop_dir, f"tmp_{i}.jpg")
        if os.path.exists(src):
            os.rename(src, tmp)
            temp_names.append((i + 1, tmp))

    new_paths = []
    for final_index, tmp_path in temp_names:
        dest = os.path.join(prop_dir, f"{final_index}.jpg")
        os.rename(tmp_path, dest)
        new_paths.append(f"storage/images/{property_id}/{final_index}.jpg")

    return new_paths
