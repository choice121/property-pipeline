"""
Opendoor scraper — fetches homes listed for sale on Opendoor (iBuyer platform).
Note: Opendoor deals in home sales, not rentals. Price = sale price.
"""

import json
import logging
import re
from typing import Optional
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/html,*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.opendoor.com/",
}

BASE_URL = "https://www.opendoor.com"


def _parse_location(location: str):
    """Parse 'City, ST' or 'City ST' or ZIP into city/state/zip components."""
    location = location.strip()
    zip_match = re.match(r"^(\d{5})$", location)
    if zip_match:
        return {"zip": zip_match.group(1)}

    parts = re.split(r",\s*|\s{2,}", location)
    if len(parts) >= 2:
        city = parts[0].strip().title()
        state = parts[1].strip().upper()
        return {"city": city, "state": state}

    return {"city": location.title()}


def _safe_int(val):
    try:
        if val is None:
            return None
        return int(float(str(val).replace(",", "").replace("$", "")))
    except Exception:
        return None


def _normalize(home: dict, source_url: str = "") -> dict:
    """Map Opendoor API fields to the standard property schema."""
    address = home.get("address") or {}
    if isinstance(address, str):
        address_str = address
        city = home.get("city") or home.get("market", {}).get("city", "")
        state = home.get("state") or home.get("market", {}).get("state", "")
        zip_code = home.get("zip") or home.get("postal_code", "")
    else:
        address_str = address.get("street") or address.get("line1") or home.get("street_address", "")
        city = address.get("city") or home.get("city", "")
        state = address.get("state") or home.get("state", "")
        zip_code = str(address.get("zip") or address.get("postal_code") or home.get("zip", ""))

    photos = []
    for key in ("photos", "images", "media"):
        raw = home.get(key)
        if isinstance(raw, list):
            for item in raw:
                if isinstance(item, str) and item.startswith("http"):
                    photos.append(item)
                elif isinstance(item, dict):
                    for fk in ("url", "src", "href", "photo_url", "large_url"):
                        if item.get(fk, "").startswith("http"):
                            photos.append(item[fk])
                            break
            if photos:
                break

    primary = home.get("hero_image_url") or home.get("primary_photo") or home.get("thumbnail")
    if primary and primary.startswith("http") and primary not in photos:
        photos.insert(0, primary)

    price = _safe_int(
        home.get("list_price") or home.get("price") or home.get("asking_price")
        or home.get("sale_price") or home.get("estimated_value")
    )
    beds = _safe_int(home.get("bedrooms") or home.get("beds"))
    baths = None
    try:
        bv = home.get("bathrooms") or home.get("baths")
        if bv is not None:
            baths = float(bv)
    except Exception:
        pass

    sqft = _safe_int(home.get("square_feet") or home.get("sqft") or home.get("living_area"))
    prop_type = home.get("property_type") or home.get("home_type") or home.get("type") or "Single Family"
    description = home.get("description") or home.get("remarks") or home.get("about") or ""

    listing_id = str(
        home.get("id") or home.get("listing_id") or home.get("home_id") or home.get("mls_id") or ""
    )

    url = home.get("url") or home.get("property_url") or home.get("listing_url") or source_url
    if url and not url.startswith("http"):
        url = BASE_URL + url

    lat = None
    lng = None
    try:
        lat = float(home.get("latitude") or home.get("lat") or (home.get("location") or {}).get("lat") or 0) or None
        lng = float(home.get("longitude") or home.get("lng") or (home.get("location") or {}).get("lng") or 0) or None
    except Exception:
        pass

    return {
        "source": "opendoor",
        "source_url": url,
        "source_listing_id": f"opendoor-{listing_id}" if listing_id else None,
        "status": "scraped",
        "address": address_str,
        "city": city,
        "state": state,
        "zip": zip_code,
        "lat": lat,
        "lng": lng,
        "bedrooms": beds,
        "bathrooms": baths,
        "total_bathrooms": baths,
        "square_footage": sqft,
        "monthly_rent": price,
        "property_type": prop_type,
        "description": description,
        "original_image_urls": json.dumps(photos),
        "local_image_paths": "[]",
        "edited_fields": "[]",
        "inferred_features": "[]",
        "amenities": "[]",
        "appliances": "[]",
        "utilities_included": "[]",
        "flooring": "[]",
        "lease_terms": "[]",
        "pet_types_allowed": "[]",
        "original_data": json.dumps(home),
        "scraped_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
        "_list_date": None,
        "_days_on_market": None,
    }


def scrape(
    location: str,
    min_price: Optional[int] = None,
    max_price: Optional[int] = None,
    beds_min: Optional[int] = None,
    beds_max: Optional[int] = None,
    limit: int = 200,
    **kwargs,
) -> list:
    """Scrape Opendoor listings for a given location."""
    loc = _parse_location(location)

    params = {"limit": min(limit, 100), "page": 1}
    if loc.get("zip"):
        params["postal_code"] = loc["zip"]
    elif loc.get("city"):
        params["city"] = loc["city"]
        if loc.get("state"):
            params["state"] = loc["state"]

    if min_price:
        params["price_min"] = min_price
    if max_price:
        params["price_max"] = max_price
    if beds_min:
        params["beds_min"] = beds_min
    if beds_max:
        params["beds_max"] = beds_max

    results = []

    endpoints = [
        f"{BASE_URL}/api/v2/homes",
        f"{BASE_URL}/api/v1/listings",
        f"{BASE_URL}/api/homes",
    ]

    for endpoint in endpoints:
        try:
            with httpx.Client(headers=HEADERS, timeout=20, follow_redirects=True) as client:
                resp = client.get(endpoint, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    homes = (
                        data.get("homes") or data.get("listings") or
                        data.get("results") or data.get("data") or []
                    )
                    if isinstance(homes, list) and homes:
                        for home in homes[:limit]:
                            try:
                                results.append(_normalize(home))
                            except Exception as e:
                                logger.warning("Opendoor normalize error: %s", e)
                        logger.info("Opendoor: fetched %d listings from %s", len(results), endpoint)
                        return results
        except Exception as e:
            logger.warning("Opendoor endpoint %s failed: %s", endpoint, e)
            continue

    if not results:
        results = _scrape_html(location, loc, params, limit)

    return results


def _scrape_html(location: str, loc: dict, params: dict, limit: int) -> list:
    """Fallback: scrape the Opendoor web search page for embedded JSON data."""
    try:
        city = loc.get("city", "").lower().replace(" ", "-")
        state = loc.get("state", "").lower()
        slug = f"{city}-{state}" if state else city

        url = f"{BASE_URL}/homes/{slug}"
        with httpx.Client(headers=HEADERS, timeout=20, follow_redirects=True) as client:
            resp = client.get(url)
            if resp.status_code != 200:
                logger.warning("Opendoor HTML page returned %d for %s", resp.status_code, url)
                return []

            html = resp.text
            json_match = re.search(r'window\.__INITIAL_STATE__\s*=\s*(\{.+?\});', html, re.DOTALL)
            if not json_match:
                json_match = re.search(r'__NEXT_DATA__["\s]*=\s*(\{.+?\})\s*;', html, re.DOTALL)

            if json_match:
                state_data = json.loads(json_match.group(1))
                homes = (
                    state_data.get("homes") or
                    state_data.get("listings") or
                    (state_data.get("props") or {}).get("pageProps", {}).get("homes") or []
                )
                results = []
                for home in homes[:limit]:
                    try:
                        results.append(_normalize(home, url))
                    except Exception as e:
                        logger.warning("Opendoor HTML normalize error: %s", e)
                if results:
                    logger.info("Opendoor HTML: extracted %d listings", len(results))
                    return results

    except Exception as e:
        logger.warning("Opendoor HTML scrape failed: %s", e)

    return []
