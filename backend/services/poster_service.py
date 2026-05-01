"""Poster Attribution Service — Phase 8

Resolves scraped agent/broker names to landlord profiles in public.landlords.
Deduplicates by normalised name, uploads avatars to ImageKit, and caches
results in-process so repeat lookups cost zero DB round-trips.
"""
import logging
import os
import re
import unicodedata
from typing import Optional
import httpx

logger = logging.getLogger(__name__)

# ── In-process cache: normalised_name → landlord_id (or None) ────────────────
_name_cache: dict[str, Optional[str]] = {}
_id_cache:   dict[str, dict]          = {}   # landlord_id → full row


def _get_supabase():
    from supabase import create_client
    url = os.environ["SUPABASE_URL"].rstrip("/")
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"].strip()
    return create_client(url, key)


def _get_imagekit():
    from imagekitio import ImageKit
    return ImageKit(private_key=os.environ["IMAGEKIT_PRIVATE_KEY"])


def _normalise(name: Optional[str]) -> str:
    """Lower-case, strip accents, collapse whitespace, strip punctuation."""
    if not name:
        return ""
    name = unicodedata.normalize("NFKD", name)
    name = name.encode("ascii", "ignore").decode()
    name = re.sub(r"[^\w\s]", "", name)
    name = re.sub(r"\s+", " ", name).strip().lower()
    return name


def _safe_avatar(row: dict) -> Optional[str]:
    """Return a clean string avatar URL, handling JSON-encoded strings."""
    val = row.get("avatar_url")
    if not val:
        return None
    if isinstance(val, str):
        stripped = val.strip()
        if stripped.startswith('"') and stripped.endswith('"'):
            try:
                import json
                stripped = json.loads(stripped)
            except Exception:
                pass
        return stripped if stripped.startswith("http") else None
    return None


def _upload_avatar(agent_image_url: str, landlord_id: str) -> Optional[str]:
    """Download agent photo and upload to ImageKit. Returns CDN URL or None."""
    try:
        response = httpx.get(agent_image_url, timeout=10, follow_redirects=True)
        response.raise_for_status()
        ext = "jpg"
        ct = response.headers.get("content-type", "")
        if "png" in ct:
            ext = "png"
        elif "webp" in ct:
            ext = "webp"
        ik = _get_imagekit()
        result = ik.files.upload(
            file=response.content,
            file_name=f"poster_{landlord_id}.{ext}",
            folder="/posters",
        )
        logger.info("Uploaded avatar for landlord %s: %s", landlord_id, result.url)
        return result.url
    except Exception as e:
        logger.warning("Avatar upload failed for %s: %s", landlord_id, e)
        return None


def _find_existing(client, norm_name: str) -> Optional[dict]:
    """Search public.landlords for a row whose normalised name matches."""
    try:
        result = client.table("landlords").select("*").execute()
        for row in (result.data or []):
            contact = _normalise(row.get("contact_name"))
            business = _normalise(row.get("business_name"))
            if norm_name and (norm_name == contact or norm_name == business):
                return row
    except Exception as e:
        logger.warning("Landlord lookup failed: %s", e)
    return None


def _try_create_landlord(client, contact_name: str, avatar_url: Optional[str]) -> Optional[dict]:
    """Attempt to insert a new landlord row. Returns row or None on failure."""
    try:
        payload: dict = {
            "contact_name": contact_name,
            "account_type": "landlord",
            "verified": False,
            "plan": "free",
        }
        if avatar_url:
            payload["avatar_url"] = avatar_url
        result = client.table("landlords").insert(payload).execute()
        if result.data:
            return result.data[0]
    except Exception as e:
        logger.warning("Could not create landlord for '%s': %s", contact_name, e)
    return None


def resolve_poster_landlord(
    agent_name: Optional[str],
    broker_name: Optional[str],
    agent_image_url: Optional[str] = None,
) -> Optional[str]:
    """
    Main entry point called from the scraper after enrichment.

    Returns a landlord UUID to store in pipeline_properties.poster_landlord_id,
    or None if no match/creation was possible.
    """
    primary = agent_name or broker_name
    norm = _normalise(primary)
    if not norm:
        return None

    if norm in _name_cache:
        return _name_cache[norm]

    client = _get_supabase()

    row = _find_existing(client, norm)

    if not row:
        avatar_cdn = None
        if agent_image_url:
            temp_id = "new"
            avatar_cdn = _upload_avatar(agent_image_url, temp_id)
        row = _try_create_landlord(client, primary, avatar_cdn)

    if not row:
        _name_cache[norm] = None
        return None

    landlord_id = row["id"]

    if agent_image_url and not _safe_avatar(row):
        cdn_url = _upload_avatar(agent_image_url, landlord_id)
        if cdn_url:
            try:
                client.table("landlords").update({"avatar_url": cdn_url}).eq("id", landlord_id).execute()
                row["avatar_url"] = cdn_url
            except Exception as e:
                logger.warning("Could not update avatar_url for landlord %s: %s", landlord_id, e)

    _name_cache[norm] = landlord_id
    _id_cache[landlord_id] = row
    logger.info("Poster resolved: '%s' → landlord %s", primary, landlord_id)
    return landlord_id


def get_all_posters(client=None) -> list[dict]:
    """Return all landlords that have been used as posters (have properties referencing them)."""
    if client is None:
        client = _get_supabase()
    try:
        result = client.table("landlords").select("*").order("created_at", desc=True).execute()
        rows = result.data or []
        for row in rows:
            row["avatar_url"] = _safe_avatar(row)
        return rows
    except Exception as e:
        logger.error("get_all_posters failed: %s", e)
        return []


def get_poster_by_id(landlord_id: str, client=None) -> Optional[dict]:
    """Return a single landlord row by ID."""
    if landlord_id in _id_cache:
        return _id_cache[landlord_id]
    if client is None:
        client = _get_supabase()
    try:
        result = client.table("landlords").select("*").eq("id", landlord_id).single().execute()
        row = result.data
        if row:
            row["avatar_url"] = _safe_avatar(row)
            _id_cache[landlord_id] = row
        return row
    except Exception as e:
        logger.warning("get_poster_by_id(%s) failed: %s", landlord_id, e)
        return None


def recalculate_all(pipeline_client, public_client=None) -> dict:
    """
    Walk every pipeline property that has agent_name/broker_name but no
    poster_landlord_id and attempt to resolve/create the landlord.

    Returns a summary dict.
    """
    if public_client is None:
        public_client = _get_supabase()

    resolved = 0
    skipped = 0
    failed = 0

    try:
        result = pipeline_client.table("pipeline_properties").select(
            "id,agent_name,broker_name,agent_image_url,poster_landlord_id"
        ).execute()
        rows = result.data or []
    except Exception as e:
        logger.error("recalculate_all: failed to fetch properties: %s", e)
        return {"resolved": 0, "skipped": 0, "failed": 1, "error": str(e)}

    for row in rows:
        if row.get("poster_landlord_id"):
            skipped += 1
            continue
        agent = row.get("agent_name")
        broker = row.get("broker_name")
        if not agent and not broker:
            skipped += 1
            continue
        landlord_id = resolve_poster_landlord(
            agent_name=agent,
            broker_name=broker,
            agent_image_url=row.get("agent_image_url"),
        )
        if landlord_id:
            try:
                pipeline_client.table("pipeline_properties").update(
                    {"poster_landlord_id": landlord_id}
                ).eq("id", row["id"]).execute()
                resolved += 1
            except Exception as e:
                logger.warning("Could not update poster_landlord_id for %s: %s", row["id"], e)
                failed += 1
        else:
            failed += 1

    return {"resolved": resolved, "skipped": skipped, "failed": failed}


def clear_cache():
    """Flush the in-process caches (useful for testing or after bulk updates)."""
    global _name_cache, _id_cache
    _name_cache = {}
    _id_cache = {}
    logger.info("Poster cache cleared.")
