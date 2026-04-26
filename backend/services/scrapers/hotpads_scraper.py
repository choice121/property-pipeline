"""
HotPads scraper — fetches rental listings from HotPads (a Zillow Group company).
Uses their public search API.
"""

import json
import logging
import re
from typing import Optional
from datetime import datetime

import httpx

from services.http_utils import random_headers

logger = logging.getLogger(__name__)

# Phase 2 (2.8): UA rotation — UA supplied per-request by random_headers().
HEADER_EXTRAS = {
    "Accept": "application/json, */*",
    "Referer": "https://hotpads.com/",
}

BASE_URL = "https://hotpads.com"


def _safe_int(val):
    try:
        if val is None:
            return None
        cleaned = re.sub(r"[^0-9.]", "", str(val))
        return int(float(cleaned)) if cleaned else None
    except Exception:
        return None


def _safe_float(val):
    try:
        if val is None:
            return None
        return float(val)
    except Exception:
        return None


def _normalize(listing: dict) -> Optional[dict]:
    """Normalize a HotPads listing to the standard property schema."""
    try:
        address = listing.get("address") or {}
        if isinstance(address, str):
            street = address
            city = listing.get("city") or ""
            state = listing.get("state") or ""
            zip_code = str(listing.get("zip") or listing.get("zipCode") or "")
        else:
            street = address.get("streetAddress") or address.get("street") or listing.get("streetAddress") or ""
            city = address.get("city") or listing.get("city") or ""
            state = address.get("state") or listing.get("state") or ""
            zip_code = str(address.get("zip") or address.get("zipCode") or listing.get("zipCode") or "")

        lat = _safe_float(listing.get("latitude") or listing.get("lat") or (listing.get("location") or {}).get("lat"))
        lng = _safe_float(listing.get("longitude") or listing.get("lon") or (listing.get("location") or {}).get("lon"))

        price = _safe_int(
            listing.get("price") or listing.get("listPrice") or listing.get("rentPrice")
            or listing.get("monthlyPrice") or listing.get("rent")
        )

        beds = _safe_int(listing.get("bedrooms") or listing.get("beds"))
        baths = _safe_float(listing.get("bathrooms") or listing.get("baths"))
        sqft = _safe_int(listing.get("squareFootage") or listing.get("sqft") or listing.get("livingArea"))

        photos = []
        for key in ("photos", "images", "media", "imgUrl"):
            raw = listing.get(key)
            if isinstance(raw, list):
                for item in raw:
                    if isinstance(item, str) and item.startswith("http"):
                        photos.append(item)
                    elif isinstance(item, dict):
                        for fk in ("url", "src", "href"):
                            if str(item.get(fk, "")).startswith("http"):
                                photos.append(item[fk])
                                break
                if photos:
                    break
            elif isinstance(raw, str) and raw.startswith("http"):
                photos.append(raw)
                break

        hero = listing.get("heroImage") or listing.get("primaryPhoto") or listing.get("thumbnail")
        if hero and str(hero).startswith("http") and hero not in photos:
            photos.insert(0, hero)

        listing_id = str(listing.get("id") or listing.get("listingId") or listing.get("zpid") or "")
        url = listing.get("url") or listing.get("detailUrl") or listing.get("hdpUrl") or ""
        if url and not url.startswith("http"):
            url = BASE_URL + url

        description = listing.get("description") or listing.get("remarks") or ""
        prop_type = listing.get("propertyType") or listing.get("homeType") or listing.get("type") or "Apartment"

        amenities_raw = listing.get("amenities") or listing.get("features") or []
        amenities = []
        if isinstance(amenities_raw, list):
            amenities = [str(a) for a in amenities_raw if a]
        elif isinstance(amenities_raw, str):
            amenities = [amenities_raw]

        pets = listing.get("petsAllowed") or listing.get("pets")
        pets_allowed = None
        if pets is True or pets == "Yes" or pets == "true":
            pets_allowed = True
        elif pets is False or pets == "No" or pets == "false":
            pets_allowed = False

        if not street and not city:
            return None

        return {
            "source": "hotpads",
            "source_url": url,
            "source_listing_id": f"hp-{listing_id}" if listing_id else None,
            "status": "scraped",
            "address": street,
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
            "pets_allowed": pets_allowed,
            "amenities": json.dumps(amenities),
            "original_image_urls": json.dumps(photos),
            "local_image_paths": "[]",
            "edited_fields": "[]",
            "inferred_features": "[]",
            "appliances": "[]",
            "utilities_included": "[]",
            "flooring": "[]",
            "lease_terms": "[]",
            "pet_types_allowed": "[]",
            "original_data": json.dumps(listing),
            "scraped_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "_list_date": None,
            "_days_on_market": None,
        }
    except Exception as e:
        logger.warning("HotPads normalize error: %s", e)
        return None


def scrape(
    location: str,
    min_price: Optional[int] = None,
    max_price: Optional[int] = None,
    beds_min: Optional[int] = None,
    beds_max: Optional[int] = None,
    limit: int = 200,
    **kwargs,
) -> list:
    """Scrape HotPads rental listings."""
    location_encoded = location.strip().lower().replace(",", "").replace("  ", " ").replace(" ", "-")

    params = {
        "listingTypes": "APARTMENT,HOUSE,CONDO,TOWNHOUSE",
        "numResults": min(limit, 100),
    }
    if min_price:
        params["minPrice"] = min_price
    if max_price:
        params["maxPrice"] = max_price
    if beds_min:
        params["minBeds"] = beds_min
    if beds_max:
        params["maxBeds"] = beds_max

    results = []

    api_endpoints = [
        f"{BASE_URL}/api/v1/listings",
        f"{BASE_URL}/rental-listings/{location_encoded}",
    ]

    for endpoint in api_endpoints:
        try:
            with httpx.Client(headers=random_headers(HEADER_EXTRAS), timeout=20, follow_redirects=True) as client:
                resp = client.get(endpoint, params=params)
                if resp.status_code == 200:
                    try:
                        data = resp.json()
                        listings = (
                            data.get("listings") or data.get("results") or
                            data.get("data") or data.get("properties") or []
                        )
                        if isinstance(listings, list) and listings:
                            for item in listings[:limit]:
                                normalized = _normalize(item)
                                if normalized:
                                    results.append(normalized)
                            logger.info("HotPads: fetched %d listings", len(results))
                            return results
                    except Exception:
                        pass
        except Exception as e:
            logger.warning("HotPads endpoint %s failed: %s", endpoint, e)
            continue

    return results
