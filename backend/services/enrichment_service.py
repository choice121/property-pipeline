import json
import logging
import time
from datetime import date

import httpx

logger = logging.getLogger(__name__)


def _add_inferred(prop: dict, feature: str):
    try:
        existing = json.loads(prop.get("inferred_features") or "[]")
    except Exception:
        existing = []
    existing.append(feature)
    prop["inferred_features"] = json.dumps(existing)


def infer_title(prop: dict) -> dict:
    if prop.get("title"):
        return prop
    parts = []
    if prop.get("bedrooms"):
        parts.append(f"{prop['bedrooms']}BR")
    ptype = (prop.get("property_type") or "Property").replace("_", " ").title()
    parts.append(ptype)
    if prop.get("city"):
        parts.append(f"in {prop['city']}")
    prop["title"] = " ".join(parts)
    _add_inferred(prop, "title_inferred")
    return prop


def infer_available_date(prop: dict) -> dict:
    if prop.get("available_date"):
        return prop
    if prop.get("_list_date"):
        prop["available_date"] = prop["_list_date"]
        _add_inferred(prop, "available_date_from_list_date")
    else:
        prop["available_date"] = date.today().isoformat()
        _add_inferred(prop, "available_date_default_today")
    return prop


def infer_security_deposit(prop: dict) -> dict:
    if prop.get("security_deposit"):
        return prop
    rent = prop.get("monthly_rent")
    if not rent:
        return prop
    prop["security_deposit"] = rent
    _add_inferred(prop, "security_deposit_1x_rent")
    return prop


def infer_pet_policy(prop: dict) -> dict:
    if prop.get("pets_allowed") is not None:
        return prop
    text = (prop.get("description") or "").lower()
    no_keywords = ["no pets", "no animals", "pet-free", "pets not allowed", "no dogs allowed", "no cats allowed"]
    yes_keywords = ["pets ok", "pet friendly", "pets welcome", "dogs allowed", "cats allowed", "pets allowed", "pet-friendly"]
    if any(k in text for k in no_keywords):
        prop["pets_allowed"] = False
        _add_inferred(prop, "pets_denied_from_text")
    elif any(k in text for k in yes_keywords):
        prop["pets_allowed"] = True
        _add_inferred(prop, "pets_allowed_from_text")
    return prop


def run_rule_based_enrichment(prop: dict) -> dict:
    prop = infer_title(prop)
    prop = infer_available_date(prop)
    prop = infer_security_deposit(prop)
    prop = infer_pet_policy(prop)
    return prop


def geocode_property(prop_id: str, repo) -> None:
    prop = repo.get(prop_id)
    if not prop:
        return
    if prop.lat and prop.lng:
        return

    address = " ".join(filter(None, [prop.address, prop.city, prop.state, prop.zip]))
    if not address.strip():
        return

    # Phase 2 (2.6): process-global token bucket — concurrent enrichment workers
    # cannot now collectively exceed Nominatim's 1 req/s policy. The previous
    # `time.sleep(1)` at function exit only protected serial callers.
    from services.http_utils import nominatim_limiter
    nominatim_limiter.acquire()

    try:
        with httpx.Client(timeout=8) as client:
            r = client.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": address, "format": "json", "limit": 1},
                headers={"User-Agent": "ChoiceProperties/1.0 (internal-tool@choiceproperties.ca)"},
            )
            data = r.json()
            if data:
                prop.lat = float(data[0]["lat"])
                prop.lng = float(data[0]["lon"])
                try:
                    inferred = json.loads(prop.inferred_features or "[]")
                except Exception:
                    inferred = []
                inferred.append("geocoded_nominatim")
                prop.inferred_features = json.dumps(inferred)
                repo.save(prop)
                logger.info(
                    "Geocoded property %s → %.4f, %.4f",
                    prop_id, prop.lat, prop.lng,
                )
    except Exception as e:
        logger.debug("Geocoding failed for %s (%s): %s", prop_id, address, e)
