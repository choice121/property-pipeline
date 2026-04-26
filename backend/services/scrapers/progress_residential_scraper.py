"""
Progress Residential scraper — fetches single-family rental listings from ProgressResidential.com.
Note: ProgressResidential.com blocks datacenter/cloud IP ranges via Cloudflare.
      This scraper works correctly from residential internet connections.
"""

import json
import logging
import re
from typing import Optional
from datetime import datetime

import httpx
from bs4 import BeautifulSoup

from services.http_utils import random_headers, get_proxy_map

logger = logging.getLogger(__name__)

BASE_URL = "https://www.progressresidential.com"

# Phase 2 (2.8): UA rotation — UA supplied per-request by random_headers().
HEADER_EXTRAS = {
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Cache-Control": "max-age=0",
}

API_HEADER_EXTRAS = {
    **HEADER_EXTRAS,
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
}

# Location → URL slug mapping for Progress Residential markets
LOCATION_MAP = {
    "atlanta": "georgia/atlanta",
    "birmingham": "alabama/birmingham",
    "charlotte": "north-carolina/charlotte",
    "chicago": "illinois/chicago",
    "columbus": "ohio/columbus",
    "dallas": "texas/dallas",
    "denver": "colorado/denver",
    "houston": "texas/houston",
    "indianapolis": "indiana/indianapolis",
    "jacksonville": "florida/jacksonville",
    "las vegas": "nevada/las-vegas",
    "memphis": "tennessee/memphis",
    "miami": "florida/miami",
    "nashville": "tennessee/nashville",
    "oklahoma city": "oklahoma/oklahoma-city",
    "orlando": "florida/orlando",
    "phoenix": "arizona/phoenix",
    "raleigh": "north-carolina/raleigh",
    "richmond": "virginia/richmond",
    "salt lake": "utah/salt-lake-city",
    "san antonio": "texas/san-antonio",
    "savannah": "georgia/savannah",
    "seattle": "washington/seattle",
    "tampa": "florida/tampa",
    "tucson": "arizona/tucson",
}

STATE_MAP = {
    "ga": "georgia/atlanta",
    "al": "alabama/birmingham",
    "nc": "north-carolina/charlotte",
    "il": "illinois/chicago",
    "oh": "ohio/columbus",
    "tx": "texas/dallas",
    "co": "colorado/denver",
    "in": "indiana/indianapolis",
    "fl": "florida/jacksonville",
    "nv": "nevada/las-vegas",
    "tn": "tennessee/nashville",
    "ok": "oklahoma/oklahoma-city",
    "az": "arizona/phoenix",
    "va": "virginia/richmond",
    "ut": "utah/salt-lake-city",
    "wa": "washington/seattle",
}


def _location_to_slug(location: str) -> Optional[str]:
    loc = location.strip().lower()
    loc_clean = re.sub(r",\s*[a-z]{2}$", "", loc).strip()

    for keyword in sorted(LOCATION_MAP.keys(), key=len, reverse=True):
        if keyword in loc_clean:
            return LOCATION_MAP[keyword]

    state_match = re.search(r",\s*([a-z]{2})$", loc)
    if state_match:
        return STATE_MAP.get(state_match.group(1))

    return None


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
        cleaned = re.sub(r"[^0-9.]", "", str(val))
        return float(cleaned) if cleaned else None
    except Exception:
        return None


def _normalize_json(home: dict, source_url: str = "") -> Optional[dict]:
    """Normalize a Progress Residential JSON property record."""
    try:
        address = (home.get("address") or home.get("street_address") or
                   home.get("address_1") or home.get("streetAddress") or "")
        if isinstance(address, dict):
            address = address.get("street") or address.get("streetAddress") or ""

        city = home.get("city") or ""
        state = home.get("state") or home.get("region") or ""
        zipcode = str(home.get("zip") or home.get("zipCode") or home.get("postalCode") or "")

        beds = _safe_int(home.get("beds") or home.get("bedrooms") or home.get("bedroom_count"))
        baths = _safe_float(home.get("baths") or home.get("bathrooms") or home.get("bathroom_count"))
        sqft = _safe_int(home.get("sqft") or home.get("square_feet") or home.get("squareFeet") or home.get("living_area"))
        rent = _safe_int(home.get("rent") or home.get("price") or home.get("monthly_rent") or home.get("listPrice"))

        lat = _safe_float(home.get("lat") or home.get("latitude"))
        lng = _safe_float(home.get("lng") or home.get("longitude"))

        photos = []
        for key in ("photos", "images", "media", "gallery"):
            raw = home.get(key)
            if isinstance(raw, list):
                for item in raw:
                    if isinstance(item, str) and item.startswith("http"):
                        photos.append(item)
                    elif isinstance(item, dict):
                        for fk in ("url", "src", "href", "image_url"):
                            if str(item.get(fk, "")).startswith("http"):
                                photos.append(item[fk])
                                break
                if photos:
                    break

        hero = home.get("hero_image") or home.get("primary_photo") or home.get("thumbnail")
        if hero and str(hero).startswith("http") and hero not in photos:
            photos.insert(0, hero)

        description = home.get("description") or home.get("remarks") or home.get("longdesc") or ""
        prop_type = home.get("property_type") or home.get("propertyType") or "Single Family"
        listing_id = str(home.get("id") or home.get("property_id") or home.get("listing_id") or "")

        url = home.get("url") or home.get("property_url") or source_url
        if url and not url.startswith("http"):
            url = BASE_URL + url

        amenities_raw = home.get("amenities") or home.get("features") or []
        amenities = []
        if isinstance(amenities_raw, list):
            amenities = [str(a) for a in amenities_raw if a]
        elif isinstance(amenities_raw, str):
            amenities = [amenities_raw]

        if not address and not city:
            return None

        return {
            "source": "progress_residential",
            "source_url": url,
            "source_listing_id": f"pr-{listing_id}" if listing_id else None,
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
            # Phase 5.5: compact original_data — only allow-listed identifier + price keys
            "original_data": json.dumps({
                "listing_id": listing_id,
                "property_url": url,
                "list_price": rent,
                "status": home.get("status") or home.get("listing_status") or "active",
            }),
            "scraped_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "_list_date": None,
            "_days_on_market": None,
        }
    except Exception as e:
        logger.warning("Progress Residential normalize error: %s", e)
        return None


def _normalize_card(card, base_url: str) -> Optional[dict]:
    """Parse a listing card from the Progress Residential search HTML."""
    try:
        listing_id = card.get("data-id") or card.get("data-propertyid") or card.get("id") or ""

        url_tag = card.find("a", href=re.compile(r"/homes-for-rent/", re.I))
        url = ""
        if url_tag:
            href = url_tag.get("href", "")
            url = href if href.startswith("http") else BASE_URL + href

        title_tag = card.find(class_=re.compile(r"property.?title|listing.?title|address", re.I))
        address_text = title_tag.get_text(strip=True) if title_tag else ""

        street = ""
        city = ""
        state = ""
        zipcode = ""
        parts = address_text.split(",")
        if len(parts) >= 2:
            street = parts[0].strip()
            rest = parts[1].strip()
            tokens = rest.split()
            if len(tokens) >= 2:
                city = " ".join(tokens[:-2]) if len(tokens) > 2 else tokens[0]
                state = tokens[-2] if len(tokens) >= 2 else ""
                zipcode = tokens[-1] if len(tokens) >= 1 else ""
        elif address_text:
            street = address_text

        price_tag = card.find(class_=re.compile(r"price|rent|amount", re.I))
        rent = None
        if price_tag:
            m = re.search(r"\$([\d,]+)", price_tag.get_text())
            if m:
                rent = int(m.group(1).replace(",", ""))

        beds = None
        baths = None
        detail_tag = card.find(class_=re.compile(r"beds?|details?|specs?", re.I))
        if detail_tag:
            text = detail_tag.get_text(strip=True).lower()
            bed_m = re.search(r"(\d+)\s*(?:bed|br)", text)
            bath_m = re.search(r"([\d.]+)\s*(?:bath|ba)", text)
            if bed_m:
                beds = int(bed_m.group(1))
            if bath_m:
                baths = float(bath_m.group(1))

        sqft = None
        sqft_tag = card.find(class_=re.compile(r"sqft|square", re.I))
        if sqft_tag:
            m = re.search(r"([\d,]+)", sqft_tag.get_text())
            if m:
                sqft = int(m.group(1).replace(",", ""))

        photos = []
        for img in card.find_all("img", limit=5):
            src = img.get("data-src") or img.get("src") or ""
            if src.startswith("http"):
                photos.append(src)

        if not street and not city:
            return None

        return {
            "source": "progress_residential",
            "source_url": url,
            "source_listing_id": f"pr-{listing_id}" if listing_id else None,
            "status": "scraped",
            "address": street,
            "city": city,
            "state": state,
            "zip": zipcode,
            "lat": None,
            "lng": None,
            "bedrooms": beds,
            "bathrooms": baths,
            "total_bathrooms": baths,
            "square_footage": sqft,
            "monthly_rent": rent,
            "property_type": "Single Family",
            "description": "",
            "amenities": "[]",
            "original_image_urls": json.dumps(photos),
            "local_image_paths": "[]",
            "edited_fields": "[]",
            "inferred_features": "[]",
            "appliances": "[]",
            "utilities_included": "[]",
            "flooring": "[]",
            "lease_terms": "[]",
            "pet_types_allowed": "[]",
            "original_data": "{}",
            "scraped_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "_list_date": None,
            "_days_on_market": None,
        }
    except Exception as e:
        logger.warning("Progress Residential card parse error: %s", e)
        return None


def _try_api(location_slug: str, beds_min, beds_max, min_price, max_price, limit) -> list:
    """Try Progress Residential JSON API endpoints."""
    city = location_slug.split("/")[-1]
    state = location_slug.split("/")[0]

    endpoints = [
        f"{BASE_URL}/api/properties",
        f"{BASE_URL}/api/homes",
        f"{BASE_URL}/wp-json/pr/v1/properties",
        f"{BASE_URL}/wp-json/wp/v2/properties",
    ]

    params = {
        "city": city.replace("-", " ").title(),
        "state": state.replace("-", " ").title(),
        "per_page": min(limit, 100),
    }
    if beds_min:
        params["beds_min"] = beds_min
    if beds_max:
        params["beds_max"] = beds_max
    if min_price:
        params["price_min"] = min_price
    if max_price:
        params["price_max"] = max_price

    for endpoint in endpoints:
        try:
            with httpx.Client(headers=random_headers(API_HEADER_EXTRAS), timeout=20, follow_redirects=True, proxies=get_proxy_map()) as client:
                resp = client.get(endpoint, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    homes = (data if isinstance(data, list)
                             else data.get("properties") or data.get("homes")
                             or data.get("results") or data.get("data") or [])
                    if isinstance(homes, list) and homes:
                        results = []
                        for home in homes[:limit]:
                            norm = _normalize_json(home)
                            if norm:
                                results.append(norm)
                        logger.info("Progress Residential API: got %d results from %s", len(results), endpoint)
                        return results
        except Exception as e:
            logger.debug("Progress Residential API %s failed: %s", endpoint, e)

    return []


def _try_html(location_slug: str, beds_min, beds_max, limit) -> list:
    """Scrape Progress Residential search page HTML."""
    beds_suffix = ""
    if beds_min:
        bed_map = {1: "1-bedroom", 2: "2-bedroom", 3: "3-bedroom", 4: "4-bedroom"}
        beds_suffix = "/" + bed_map.get(beds_min, f"{beds_min}-bedroom")

    url = f"{BASE_URL}/homes-for-rent/{location_slug}{beds_suffix}/"

    try:
        with httpx.Client(headers=random_headers(HEADER_EXTRAS), timeout=25, follow_redirects=True, proxies=get_proxy_map()) as client:
            resp = client.get(url)
            if resp.status_code != 200:
                logger.warning("Progress Residential HTML returned %d for %s", resp.status_code, url)
                return []

            html = resp.text
            soup = BeautifulSoup(html, "lxml")

            # Try JSON-LD first
            results = []
            for script in soup.find_all("script", type="application/ld+json"):
                try:
                    obj = json.loads(script.string or "")
                    items = obj if isinstance(obj, list) else [obj]
                    for item in items:
                        if item.get("@type") in ("SingleFamilyResidence", "House", "RealEstateListing", "Residence"):
                            norm = _normalize_json(item, url)
                            if norm:
                                results.append(norm)
                except Exception:
                    pass

            if results:
                logger.info("Progress Residential JSON-LD: got %d results", len(results))
                return results[:limit]

            # Try inline JSON state
            for pattern in [
                r'window\.__INITIAL_STATE__\s*=\s*(\{.+?\});',
                r'window\.__APP_STATE__\s*=\s*(\{.+?\});',
                r'"properties"\s*:\s*(\[.+?\])',
            ]:
                m = re.search(pattern, html, re.DOTALL)
                if m:
                    try:
                        state_data = json.loads(m.group(1))
                        homes = (state_data if isinstance(state_data, list)
                                 else state_data.get("properties") or state_data.get("homes") or [])
                        for home in homes[:limit]:
                            norm = _normalize_json(home, url)
                            if norm:
                                results.append(norm)
                        if results:
                            logger.info("Progress Residential inline JSON: got %d results", len(results))
                            return results
                    except Exception:
                        pass

            # Try HTML card parsing
            cards = soup.find_all(
                ["div", "article", "li"],
                class_=re.compile(r"property.?card|listing.?card|home.?card|property.?item", re.I),
            )
            for card in cards[:limit]:
                norm = _normalize_card(card, url)
                if norm:
                    results.append(norm)

            if results:
                logger.info("Progress Residential HTML cards: got %d results", len(results))
            else:
                logger.warning("Progress Residential: no listings parsed from %s", url)

            return results

    except Exception as e:
        logger.error("Progress Residential HTML scrape failed for %s: %s", url, e)
        return []


def scrape(
    location: str,
    min_price: Optional[int] = None,
    max_price: Optional[int] = None,
    beds_min: Optional[int] = None,
    beds_max: Optional[int] = None,
    limit: int = 200,
    **kwargs,
) -> list:
    """Scrape Progress Residential single-family rental listings for a given location."""

    location_slug = _location_to_slug(location)
    if not location_slug:
        logger.warning("Progress Residential: could not resolve location slug for '%s'", location)
        return []

    logger.info("Progress Residential: resolved '%s' → slug '%s'", location, location_slug)

    # Try API endpoints first
    results = _try_api(location_slug, beds_min, beds_max, min_price, max_price, limit)
    if results:
        return results

    # Fallback to HTML scraping
    results = _try_html(location_slug, beds_min, beds_max, limit)

    # Apply price/bed filters if not already applied
    filtered = []
    for r in results:
        beds = r.get("bedrooms")
        rent = r.get("monthly_rent")
        if beds_min is not None and (beds is None or beds < beds_min):
            continue
        if beds_max is not None and (beds is None or beds > beds_max):
            continue
        if min_price is not None and (rent is None or rent < min_price):
            continue
        if max_price is not None and (rent is None or rent > max_price):
            continue
        filtered.append(r)

    return filtered[:limit]
