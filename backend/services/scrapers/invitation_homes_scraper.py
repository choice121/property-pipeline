"""
Invitation Homes scraper — fetches single-family rental listings from InvitationHomes.com.
Uses the SvelteKit SSR __data.json endpoint which returns full market-level property data.
Works reliably from cloud and residential IPs alike.
"""

import json
import logging
import re
from typing import Optional
from datetime import datetime

import httpx

from services.http_utils import random_headers, get_proxy_map

logger = logging.getLogger(__name__)

BASE_URL = "https://www.invitationhomes.com"

# Phase 2 (2.8): UA rotation — UA supplied per-request by random_headers().
HEADER_EXTRAS = {
    "Accept": "application/json, */*",
    "Referer": BASE_URL,
}

# Market slug map — city/state keywords → IH market slug
MARKET_MAP = {
    "atlanta": "atlanta-georgia",
    "austin": "austin-texas",
    "carolinas": "charlotte-north-carolina",
    "charlotte": "charlotte-north-carolina",
    "chicago": "chicago-illinois",
    "dallas": "dallas-texas",
    "denver": "denver-colorado",
    "houston": "houston-texas",
    "jacksonville": "jacksonville-florida",
    "las vegas": "las-vegas-nevada",
    "minneapolis": "minneapolis-minnesota",
    "sacramento": "sacramento-california",
    "northern california": "sacramento-california",
    "orlando": "orlando-florida",
    "phoenix": "phoenix-arizona",
    "salt lake": "salt-lake-city-utah",
    "salt lake city": "salt-lake-city-utah",
    "san antonio": "san-antonio-texas",
    "seattle": "seattle-washington",
    "miami": "miami-florida",
    "south florida": "miami-florida",
    "los angeles": "los-angeles-california",
    "southern california": "los-angeles-california",
    "tampa": "tampa-florida",
}

# State abbreviation → likely market slug (best-effort fallback)
STATE_MARKET_MAP = {
    "ga": "atlanta-georgia",
    "tx": "dallas-texas",
    "fl": "orlando-florida",
    "co": "denver-colorado",
    "az": "phoenix-arizona",
    "il": "chicago-illinois",
    "wa": "seattle-washington",
    "nv": "las-vegas-nevada",
    "mn": "minneapolis-minnesota",
    "ut": "salt-lake-city-utah",
    "ca": "los-angeles-california",
    "tn": "nashville-tennessee",
}


def _location_to_market_slug(location: str) -> Optional[str]:
    loc = location.strip().lower()
    # Strip state abbreviation for matching
    loc_clean = re.sub(r",\s*[a-z]{2}$", "", loc).strip()

    # Try longest match first to avoid partial hits
    for keyword in sorted(MARKET_MAP.keys(), key=len, reverse=True):
        if keyword in loc_clean:
            return MARKET_MAP[keyword]

    # Fallback: try state abbreviation
    state_match = re.search(r",\s*([a-z]{2})$", loc)
    if state_match:
        state = state_match.group(1)
        return STATE_MARKET_MAP.get(state)

    return None


def _deref(arr: list, val):
    """Dereference exactly one level of the SvelteKit flat-array format.
    
    In SvelteKit __data.json, every field value in a dict is an index into
    the flat 'data' array. The value at that index IS the actual value — we
    must NOT follow integer values further because they could themselves be
    valid scalars (e.g. beds=3, sqft=1676).
    """
    if isinstance(val, int) and 0 <= val < len(arr):
        return arr[val]
    return val


def _resolve_prop(arr: list, prop_dict: dict) -> dict:
    """Shallow-resolve all fields of a property dict using the flat array."""
    return {k: _deref(arr, v) for k, v in prop_dict.items()}


def _decode_photos(arr: list, photos_idx) -> list:
    """Decode the photos list for a property."""
    photos_list = _deref(arr, photos_idx)
    if not isinstance(photos_list, list):
        return []
    urls = []
    for photo_idx in photos_list:
        photo_dict = _deref(arr, photo_idx)
        if isinstance(photo_dict, dict):
            image_url = _deref(arr, photo_dict.get("image_url"))
            if isinstance(image_url, str) and image_url.startswith("http"):
                urls.append(image_url)
    return urls


def _normalize(prop: dict, arr: list) -> Optional[dict]:
    """Map a raw Invitation Homes property dict to the standard schema."""
    try:
        r = _resolve_prop(arr, prop)

        address = r.get("address_1") or ""
        city = r.get("city") or ""
        state = r.get("state") or ""
        zipcode = str(r.get("zipcode") or "")

        beds = None
        try:
            beds = int(float(str(r.get("beds") or 0))) or None
        except Exception:
            pass

        baths = None
        try:
            baths = float(str(r.get("baths") or 0)) or None
        except Exception:
            pass

        sqft = None
        try:
            sqft_val = r.get("sqft")
            if sqft_val and str(sqft_val).replace(".", "").isdigit():
                sqft = int(float(sqft_val))
        except Exception:
            pass

        rent = None
        try:
            rent = int(float(str(r.get("market_rent") or r.get("total_monthly_rent") or 0))) or None
        except Exception:
            pass

        lat = None
        lng = None
        try:
            lat = float(r.get("lat") or 0) or None
            lng = float(r.get("lng") or 0) or None
        except Exception:
            pass

        photos = _decode_photos(arr, prop.get("photos"))

        description = r.get("longdesc") or r.get("shortdesc") or ""

        prop_type = r.get("property_type") or "Single Family Home"

        # Amenities from amenities_list string
        amenities_raw = r.get("amenities_list") or ""
        amenities = [a.strip() for a in amenities_raw.split(",") if a.strip()] if amenities_raw else []

        # Feature flags
        features = []
        for flag, label in [
            ("has_pool", "Pool"),
            ("has_garage", "Garage"),
            ("has_fireplace", "Fireplace"),
            ("has_deck", "Deck"),
            ("has_patio", "Patio"),
            ("has_fenced_yard", "Fenced Yard"),
            ("has_washer_dryer", "Washer/Dryer"),
            ("has_walk_in_closet", "Walk-in Closet"),
            ("has_finished_basement", "Finished Basement"),
            ("has_hardwood_floors", "Hardwood Floors"),
            ("has_vaulted_ceilings", "Vaulted Ceilings"),
        ]:
            if r.get(flag):
                features.append(label)

        pets_allowed = r.get("is_pet_friendly")

        listing_id = r.get("slug") or r.get("unit_code") or r.get("id") or ""
        source_url = r.get("property_url") or r.get("application_url") or ""
        if source_url and not source_url.startswith("http"):
            source_url = BASE_URL + source_url

        if not address and not city:
            return None

        return {
            "source": "invitation_homes",
            "source_url": source_url,
            "source_listing_id": f"invh-{listing_id}" if listing_id else None,
            "status": "scraped",
            "address": address,
            "city": city,
            "state": state,
            "zip": zipcode,
            "lat": lat,
            "lng": lng,
            "bedrooms": beds,
            "bathrooms": baths,
            "total_bathrooms": baths,
            "square_footage": sqft,
            "monthly_rent": rent,
            "property_type": prop_type,
            "description": description,
            "pets_allowed": pets_allowed,
            "amenities": json.dumps(amenities + features),
            "original_image_urls": json.dumps(photos),
            "local_image_paths": "[]",
            "edited_fields": "[]",
            "inferred_features": json.dumps(features),
            "appliances": "[]",
            "utilities_included": "[]",
            "flooring": "[]",
            "lease_terms": "[]",
            "pet_types_allowed": "[]",
            "original_data": json.dumps({
                "id": r.get("id"),
                "slug": listing_id,
                "market_slug": r.get("market_slug"),
                "days_on_market": r.get("days_on_market"),
                "available_at": str(r.get("available_at") or ""),
                "property_status": r.get("property_status"),
            }),
            "scraped_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "_list_date": None,
            "_days_on_market": r.get("days_on_market"),
        }
    except Exception as e:
        logger.warning("InvitationHomes normalize error: %s", e)
        return None


def _fetch_markets() -> list:
    """Fetch the full list of IH markets with their slugs from the root __data.json."""
    try:
        url = f"{BASE_URL}/find-a-home/__data.json"
        with httpx.Client(headers=random_headers(HEADER_EXTRAS), timeout=20, follow_redirects=True, proxies=get_proxy_map()) as client:
            resp = client.get(url)
            if resp.status_code != 200:
                logger.warning("IH markets endpoint returned %d", resp.status_code)
                return []
            data = resp.json()
            nodes = data.get("nodes", [])
            for node in nodes:
                if not node or not isinstance(node, dict):
                    continue
                raw = node.get("data", [])
                if not isinstance(raw, list) or not raw:
                    continue
                root = raw[0]
                if not isinstance(root, dict) or "markets" not in root:
                    continue
                markets_idx = root["markets"]
                markets_data = raw[markets_idx] if isinstance(markets_idx, int) else None
                if not isinstance(markets_data, dict):
                    continue
                results_idx = markets_data.get("results")
                results = raw[results_idx] if isinstance(results_idx, int) else None
                if not isinstance(results, list):
                    continue
                markets = []
                for item_idx in results:
                    item = raw[item_idx] if isinstance(item_idx, int) else item_idx
                    if isinstance(item, dict):
                        resolved = {k: (raw[v] if isinstance(v, int) and 0 <= v < len(raw) else v)
                                    for k, v in item.items()}
                        markets.append(resolved)
                return markets
    except Exception as e:
        logger.warning("IH markets fetch failed: %s", e)
    return []


def _fetch_market_properties(market_slug: str) -> tuple[list, list]:
    """
    Fetch all properties for a given market slug.
    Returns (properties_list, raw_arr) for decoding.
    """
    url = f"{BASE_URL}/markets/houses-for-rent/{market_slug}/__data.json"
    headers = random_headers({**HEADER_EXTRAS, "Referer": f"{BASE_URL}/markets/houses-for-rent/{market_slug}"})

    try:
        with httpx.Client(headers=headers, timeout=30, follow_redirects=True, proxies=get_proxy_map()) as client:
            resp = client.get(url)
            if resp.status_code != 200:
                logger.warning("IH market %s returned %d", market_slug, resp.status_code)
                return [], []
            data = resp.json()
            nodes = data.get("nodes", [])
            for node in nodes:
                if not node or not isinstance(node, dict):
                    continue
                raw = node.get("data", [])
                if not isinstance(raw, list) or not raw:
                    continue
                root = raw[0]
                if not isinstance(root, dict) or "featuredHomes" not in root:
                    continue

                fh_idx = root["featuredHomes"]
                featured_groups = raw[fh_idx] if isinstance(fh_idx, int) else fh_idx
                if not isinstance(featured_groups, list):
                    continue

                all_prop_indices = []
                seen = set()
                for group_idx in featured_groups:
                    group = raw[group_idx] if isinstance(group_idx, int) else group_idx
                    if not isinstance(group, dict):
                        continue
                    props_idx = group.get("properties")
                    props_list = raw[props_idx] if isinstance(props_idx, int) else props_idx
                    if not isinstance(props_list, list):
                        continue
                    for pidx in props_list:
                        if pidx not in seen:
                            seen.add(pidx)
                            all_prop_indices.append(pidx)

                properties = []
                for pidx in all_prop_indices:
                    prop_dict = raw[pidx] if isinstance(pidx, int) else pidx
                    if isinstance(prop_dict, dict):
                        properties.append((prop_dict, raw))

                logger.info("IH market '%s': found %d properties", market_slug, len(properties))
                return properties, raw

    except Exception as e:
        logger.warning("IH market fetch failed for '%s': %s", market_slug, e)
    return [], []


def scrape(
    location: str,
    min_price: Optional[int] = None,
    max_price: Optional[int] = None,
    beds_min: Optional[int] = None,
    beds_max: Optional[int] = None,
    limit: int = 200,
    **kwargs,
) -> list:
    """Scrape Invitation Homes single-family rental listings for a given location."""

    market_slug = _location_to_market_slug(location)

    if not market_slug:
        # Try to find a close match by fetching the live market list
        markets = _fetch_markets()
        loc_lower = location.strip().lower()
        for m in markets:
            name = str(m.get("name") or "").lower()
            slug = str(m.get("slug") or "")
            if name in loc_lower or loc_lower in name:
                market_slug = slug
                break

    if not market_slug:
        logger.warning("InvitationHomes: could not resolve market slug for '%s'", location)
        return []

    logger.info("InvitationHomes: resolved '%s' → market slug '%s'", location, market_slug)

    prop_tuples, _ = _fetch_market_properties(market_slug)
    if not prop_tuples:
        return []

    results = []
    for prop_dict, raw in prop_tuples:
        if len(results) >= limit:
            break

        normalized = _normalize(prop_dict, raw)
        if not normalized:
            continue

        # Apply filters
        beds = normalized.get("bedrooms")
        rent = normalized.get("monthly_rent")

        if beds_min is not None and (beds is None or beds < beds_min):
            continue
        if beds_max is not None and (beds is None or beds > beds_max):
            continue
        if min_price is not None and (rent is None or rent < min_price):
            continue
        if max_price is not None and (rent is None or rent > max_price):
            continue

        results.append(normalized)

    logger.info("InvitationHomes: returning %d properties for '%s'", len(results), location)
    return results
