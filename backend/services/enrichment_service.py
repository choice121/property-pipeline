import json
import logging
import os
import time
from datetime import date

import httpx

logger = logging.getLogger(__name__)

# ── FEMA flood zone ──────────────────────────────────────────────────────────
_FEMA_ENDPOINT = (
    "https://msc.fema.gov/arcgis/rest/services/National_Flood_Hazard_Layer"
    "/MapServer/0/query"
)
_FLOOD_ZONE_LABELS = {
    "A":   "High Risk — Zone A (100-yr floodplain, no BFE)",
    "AE":  "High Risk — Zone AE (100-yr floodplain with BFE)",
    "AH":  "High Risk — Zone AH (shallow flooding)",
    "AO":  "High Risk — Zone AO (sheet flow flooding)",
    "AR":  "Moderate Risk — Zone AR (restoration area)",
    "A99": "High Risk — Zone A99 (protected by levee)",
    "V":   "High Risk — Zone V (coastal, no BFE)",
    "VE":  "High Risk — Zone VE (coastal with BFE)",
    "B":   "Moderate Risk — Zone B",
    "C":   "Low Risk — Zone C",
    "X":   "Minimal Risk — Zone X (outside 500-yr floodplain)",
    "D":   "Undetermined — Zone D",
}


def fetch_flood_zone(prop_id: str, repo) -> None:
    """Look up FEMA flood zone for a property using its lat/lng.

    Stores the result in prop.flood_zone as a human-readable string.
    Uses the free FEMA National Flood Hazard Layer public REST API — no key needed.
    """
    prop = repo.get(prop_id)
    if not prop:
        return
    if prop.flood_zone:
        return  # already enriched
    if not prop.lat or not prop.lng:
        return

    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(
                _FEMA_ENDPOINT,
                params={
                    "geometry":      f"{prop.lng},{prop.lat}",
                    "geometryType":  "esriGeometryPoint",
                    "inSR":          "4326",
                    "spatialRel":    "esriSpatialRelIntersects",
                    "returnGeometry": "false",
                    "outFields":     "FLD_ZONE,ZONE_SUBTY",
                    "f":             "json",
                },
            )
            data = resp.json()
    except Exception as e:
        logger.debug("FEMA flood zone lookup failed for %s: %s", prop_id, e)
        return

    features = data.get("features") or []
    if not features:
        prop.flood_zone = "Zone X — Minimal Risk (outside 500-yr floodplain)"
    else:
        attrs = features[0].get("attributes") or {}
        zone = (attrs.get("FLD_ZONE") or "").strip()
        subtype = (attrs.get("ZONE_SUBTY") or "").strip()
        label = _FLOOD_ZONE_LABELS.get(zone, f"Zone {zone}" if zone else "Unknown")
        if subtype:
            label = f"{label} ({subtype})"
        prop.flood_zone = label

    try:
        inferred = json.loads(prop.inferred_features or "[]")
    except Exception:
        inferred = []
    inferred.append("flood_zone_fema")
    prop.inferred_features = json.dumps(inferred)
    repo.save(prop)
    logger.info("Flood zone for %s: %s", prop_id, prop.flood_zone)


# ── Walk Score ───────────────────────────────────────────────────────────────

def fetch_walk_score(prop_id: str, repo) -> None:
    """Fetch Walk Score, Transit Score, and Bike Score for a property.

    Requires WALKSCORE_API_KEY environment variable.
    Free API key at https://www.walkscore.com/professional/api.php
    Stores results in prop.walk_score, prop.transit_score, prop.bike_score.
    """
    api_key = os.environ.get("WALKSCORE_API_KEY", "").strip()
    if not api_key:
        logger.debug("WALKSCORE_API_KEY not set — skipping Walk Score enrichment")
        return

    prop = repo.get(prop_id)
    if not prop:
        return
    if prop.walk_score is not None:
        return  # already enriched
    if not prop.lat or not prop.lng:
        return

    address = " ".join(filter(None, [prop.address, prop.city, prop.state, prop.zip]))

    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(
                "https://api.walkscore.com/score",
                params={
                    "format":   "json",
                    "address":  address,
                    "lat":      prop.lat,
                    "lon":      prop.lng,
                    "transit":  1,
                    "bike":     1,
                    "wsapikey": api_key,
                },
            )
            data = resp.json()
    except Exception as e:
        logger.debug("Walk Score lookup failed for %s: %s", prop_id, e)
        return

    if data.get("status") not in (1, 2):
        logger.debug("Walk Score returned status %s for %s", data.get("status"), prop_id)
        return

    prop.walk_score    = data.get("walkscore")
    prop.transit_score = (data.get("transit") or {}).get("score")
    prop.bike_score    = (data.get("bike") or {}).get("score")

    try:
        inferred = json.loads(prop.inferred_features or "[]")
    except Exception:
        inferred = []
    inferred.append("walk_score_fetched")
    prop.inferred_features = json.dumps(inferred)
    repo.save(prop)
    logger.info(
        "Walk scores for %s: walk=%s transit=%s bike=%s",
        prop_id, prop.walk_score, prop.transit_score, prop.bike_score,
    )


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
