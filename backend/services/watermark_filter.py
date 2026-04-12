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
    "progress residential",
    "tricon",
    "american homes 4 rent",
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
    "agent",
    "office",
    "realty",
    "realtor",
    "listed_by",
    "listing_agent",
    "branding",
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


def _check_original_data(data: dict) -> list[str]:
    """Scan original_data JSON for broker/agent brand names in known fields."""
    reasons = []
    raw = data.get("original_data")
    if not raw:
        return reasons
    try:
        original = json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        return reasons

    def extract_text_from(obj, depth=0):
        if depth > 6 or obj is None:
            return []
        texts = []
        if isinstance(obj, str):
            texts.append(obj.lower())
        elif isinstance(obj, dict):
            for k, v in obj.items():
                if any(f in k.lower() for f in BROKER_FIELDS):
                    texts.extend(extract_text_from(v, depth + 1))
                else:
                    texts.extend(extract_text_from(v, depth + 1))
        elif isinstance(obj, list):
            for item in obj:
                texts.extend(extract_text_from(item, depth + 1))
        return texts

    all_text = " ".join(extract_text_from(original))
    for brand in WATERMARKED_BRAND_TERMS:
        normalized = _normalize(brand)
        compact = normalized.replace(" ", "")
        norm_text = _normalize(all_text)
        if normalized in norm_text or compact in norm_text.replace(" ", ""):
            reason = f"blocked watermark brand in listing data: {brand}"
            if reason not in reasons:
                reasons.append(reason)

    return reasons


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

    reasons.extend(_check_original_data(data))

    deduped = []
    seen_brands = set()
    for r in reasons:
        brand_key = r.split(":")[-1].strip()
        if brand_key not in seen_brands:
            seen_brands.add(brand_key)
            deduped.append(r)

    return deduped


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
