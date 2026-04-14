import json
import re
from typing import Any


WATERMARKED_BRAND_TERMS = (
    "firstkey",
    "first key",
    "firstkey homes",
    "first key homes",
    "era real",
    "era realty",
    "coldwell banker",
    "century 21",
    "keller williams",
    "re/max",
    "remax",
    "berkshire hathaway",
    "sotheby",
    "compass realty",
    "exp realty",
    "better homes",
    "howard hanna",
    "long & foster",
    "weichert",
    "exit realty",
    "homes for heroes",
    "invitation homes",
    "tricon",
    "american homes 4 rent",
)

WATERMARK_FIELD_HINTS = (
    "watermark",
    "photo_credit",
    "image_credit",
    "copyright",
    "branding",
    "listed_by",
    "listing_agent",
    "broker_name",
    "agent_name",
    "office_name",
)

BROKER_FIELDS = (
    "advertiser",
    "brokers",
    "agents",
    "offices",
    "branding",
    "builder",
    "listing_agent",
    "office_name",
    "agent_name",
    "broker_name",
)


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _iter_values(value: Any):
    if value is None:
        return
    if isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from _iter_values(item)
        return
    if isinstance(value, (list, tuple, set)):
        for item in value:
            yield from _iter_values(item)
        return
    yield str(value)


def _loads_json(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except Exception:
        return value




SAFE_SKIP_KEYS = frozenset({
    "source", "source_url", "source_listing_id", "original_data",
    "status", "id", "scraped_at", "updated_at", "edited_fields",
    "inferred_features", "missing_fields", "data_quality_score",
})

BRANDED_CONTENT_KEYS = frozenset({
    "description", "title", "text", "remarks", "public_remarks",
    "agent_remarks", "property_description", "notes",
})


def watermark_reasons(data: dict) -> list[str]:
    """
    Only flag a listing as watermarked when a blocked brand name appears in a
    field that is either:
      (a) a branded-content field (description, remarks, title, notes), or
      (b) a watermark-hint field (listing_agent, branding, photo_credit, etc.)

    We deliberately skip metadata-only fields (source, source_url, original_data,
    etc.) to avoid false positives where "realtor" or "remax" appears only because
    it is the platform name or URL, not because the listing is watermarked.
    """
    reasons = []

    for key, raw_value in data.items():
        key_lower = key.lower()

        if key_lower in SAFE_SKIP_KEYS:
            continue

        is_branded_content = key_lower in BRANDED_CONTENT_KEYS
        is_watermark_field = any(hint in key_lower for hint in WATERMARK_FIELD_HINTS)

        if not is_branded_content and not is_watermark_field:
            continue

        parsed = _loads_json(raw_value)
        for item in _iter_values(parsed):
            text = _normalize(item)
            if not text:
                continue
            compact_text = text.replace(" ", "")
            for brand in WATERMARKED_BRAND_TERMS:
                normalized_brand = _normalize(brand)
                compact_brand = normalized_brand.replace(" ", "")
                if normalized_brand in text or compact_brand in compact_text:
                    reason = f"blocked watermark brand: {brand}"
                    if reason not in reasons:
                        reasons.append(reason)

    return reasons


def is_watermarked(data: dict) -> bool:
    return bool(watermark_reasons(data))


def filter_watermarked(properties: list[dict]) -> tuple[list[dict], list[dict]]:
    allowed = []
    blocked = []
    for prop in properties:
        reasons = watermark_reasons(prop)
        if reasons:
            blocked.append({
                "source_listing_id": prop.get("source_listing_id"),
                "address": prop.get("address"),
                "city": prop.get("city"),
                "state": prop.get("state"),
                "reasons": reasons,
            })
        else:
            allowed.append(prop)
    return allowed, blocked
