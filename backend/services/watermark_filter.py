import json
import re
from typing import Any


WATERMARKED_BRAND_TERMS = (
    "firstkey",
    "first key",
    "firstkey homes",
    "first key homes",
)

WATERMARK_FIELD_HINTS = (
    "watermark",
    "photo_credit",
    "image_credit",
    "copyright",
    "broker",
    "advertiser",
    "provider",
    "source",
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


def watermark_reasons(data: dict) -> list[str]:
    reasons = []
    searchable_values = []

    for key, value in data.items():
        key_text = _normalize(str(key))
        parsed = _loads_json(value)
        for item in _iter_values(parsed):
            text = _normalize(item)
            if not text:
                continue
            searchable_values.append((key_text, text))

    for brand in WATERMARKED_BRAND_TERMS:
        normalized_brand = _normalize(brand)
        compact_brand = normalized_brand.replace(" ", "")
        for key_text, text in searchable_values:
            compact_text = text.replace(" ", "")
            if normalized_brand in text or compact_brand in compact_text:
                if any(hint in key_text for hint in WATERMARK_FIELD_HINTS) or normalized_brand in text or compact_brand in compact_text:
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