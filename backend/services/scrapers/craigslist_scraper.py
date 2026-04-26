"""
Craigslist scraper — fetches rental listings via Craigslist RSS/Atom feeds.
Supports apartments, houses, and rooms for rent.
"""

import json
import logging
import re
import xml.etree.ElementTree as ET
from typing import Optional
from datetime import datetime
from urllib.parse import urlencode, quote

import httpx

from services.http_utils import random_headers

logger = logging.getLogger(__name__)

# Phase 2 (2.8): UA rotation — UA supplied per-request by random_headers().
HEADER_EXTRAS = {
    "Accept": "application/rss+xml, application/atom+xml, text/xml, */*",
}

CITY_MAP = {
    "new york": "newyork",
    "new york city": "newyork",
    "nyc": "newyork",
    "los angeles": "losangeles",
    "la": "losangeles",
    "san francisco": "sfbay",
    "sf": "sfbay",
    "san jose": "sfbay",
    "chicago": "chicago",
    "houston": "houston",
    "phoenix": "phoenix",
    "philadelphia": "philadelphia",
    "san antonio": "sanantonio",
    "san diego": "sandiego",
    "dallas": "dallas",
    "austin": "austin",
    "jacksonville": "jacksonville",
    "fort worth": "dallas",
    "columbus": "columbus",
    "charlotte": "charlotte",
    "indianapolis": "indianapolis",
    "seattle": "seattle",
    "denver": "denver",
    "nashville": "nashville",
    "oklahoma city": "oklahomacity",
    "el paso": "elpaso",
    "washington": "washingtondc",
    "dc": "washingtondc",
    "las vegas": "lasvegas",
    "louisville": "louisville",
    "memphis": "memphis",
    "portland": "portland",
    "baltimore": "baltimore",
    "milwaukee": "milwaukee",
    "albuquerque": "albuquerque",
    "tucson": "tucson",
    "fresno": "fresno",
    "sacramento": "sacramento",
    "mesa": "phoenix",
    "kansas city": "kansascity",
    "atlanta": "atlanta",
    "omaha": "omaha",
    "colorado springs": "coloradosprings",
    "raleigh": "raleigh",
    "miami": "miami",
    "minneapolis": "minneapolis",
    "cleveland": "cleveland",
    "tampa": "tampa",
    "pittsburgh": "pittsburgh",
    "cincinnati": "cincinnati",
    "st. louis": "stlouis",
    "orlando": "orlando",
    "salt lake city": "saltlakecity",
}


def _city_to_subdomain(location: str) -> str:
    """Convert a location string to a Craigslist city subdomain."""
    loc_lower = location.strip().lower()
    loc_lower = re.sub(r",\s*[a-z]{2}$", "", loc_lower).strip()

    # Sort by key length descending so longer, more specific matches win
    # (e.g. "atlanta" beats "la" which is a substring of "atlanta")
    for city in sorted(CITY_MAP.keys(), key=len, reverse=True):
        if city in loc_lower:
            return CITY_MAP[city]

    words = re.sub(r"[^a-z\s]", "", loc_lower).split()
    return "".join(words[:2])


def _safe_int(val):
    try:
        if val is None:
            return None
        cleaned = re.sub(r"[^0-9.]", "", str(val))
        return int(float(cleaned)) if cleaned else None
    except Exception:
        return None


def _parse_rss_entry(entry, ns: dict) -> Optional[dict]:
    """Parse a single RSS/Atom entry from Craigslist into a property dict."""
    try:
        title_el = entry.find("title")
        title = title_el.text.strip() if title_el is not None and title_el.text else ""

        link_el = entry.find("link")
        url = link_el.text.strip() if link_el is not None and link_el.text else ""
        if not url:
            url = link_el.get("{http://www.w3.org/2005/Atom}href", "") if link_el is not None else ""

        desc_el = entry.find("description") or entry.find("{http://www.w3.org/2005/Atom}content")
        description = ""
        if desc_el is not None and desc_el.text:
            description = re.sub(r"<[^>]+>", " ", desc_el.text).strip()
            description = re.sub(r"\s+", " ", description)

        date_el = entry.find("pubDate") or entry.find("{http://www.w3.org/2005/Atom}updated")
        list_date = None
        if date_el is not None and date_el.text:
            try:
                from email.utils import parsedate_to_datetime
                dt = parsedate_to_datetime(date_el.text.strip())
                list_date = dt.strftime("%Y-%m-%d")
            except Exception:
                pass

        listing_id = None
        id_el = entry.find("guid") or entry.find("{http://www.w3.org/2005/Atom}id")
        if id_el is not None and id_el.text:
            id_match = re.search(r"(\d{10,})", id_el.text)
            if id_match:
                listing_id = id_match.group(1)

        searchable = (title + " " + description).lower()

        price = None
        price_match = re.search(r"\$\s*([\d,]+)", title)
        if not price_match:
            price_match = re.search(r"\$\s*([\d,]+)", description)
        if price_match:
            price = int(price_match.group(1).replace(",", ""))

        beds = None
        bed_match = re.search(r"(\d+)\s*(?:br|bed|bedroom)", searchable)
        if bed_match:
            beds = int(bed_match.group(1))

        baths = None
        bath_match = re.search(r"([\d.]+)\s*(?:ba|bath|bathroom)", searchable)
        if bath_match:
            baths = float(bath_match.group(1))

        sqft = None
        sqft_match = re.search(r"([\d,]+)\s*(?:sqft|sq\.?\s*ft\.?|square\s*feet)", searchable)
        if sqft_match:
            sqft = int(sqft_match.group(1).replace(",", ""))

        address = ""
        city = ""
        state = ""
        zip_code = ""

        addr_match = re.search(r"(?:at|@|located at)\s+([\d]+ [^,\n]+)", searchable)
        if addr_match:
            address = addr_match.group(1).strip().title()

        loc_el = entry.find("{http://www.georss.org/georss}point")
        lat = lng = None
        if loc_el is not None and loc_el.text:
            try:
                parts = loc_el.text.strip().split()
                lat = float(parts[0])
                lng = float(parts[1])
            except Exception:
                pass

        if not title:
            return None

        prop_type = "Apartment"
        if "house" in searchable or "home" in searchable:
            prop_type = "Single Family"
        elif "condo" in searchable:
            prop_type = "Condo"
        elif "room" in searchable:
            prop_type = "Room"
        elif "townhouse" in searchable or "townhome" in searchable:
            prop_type = "Townhome"

        return {
            "source": "craigslist",
            "source_url": url,
            "source_listing_id": f"cl-{listing_id}" if listing_id else None,
            "status": "scraped",
            "title": title,
            "address": address,
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
            "description": description[:2000],
            "amenities": "[]",
            "original_image_urls": "[]",
            "local_image_paths": "[]",
            "edited_fields": "[]",
            "inferred_features": "[]",
            "appliances": "[]",
            "utilities_included": "[]",
            "flooring": "[]",
            "lease_terms": "[]",
            "pet_types_allowed": "[]",
            "original_data": json.dumps({"title": title, "url": url, "description": description}),
            "scraped_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "_list_date": list_date,
            "_days_on_market": None,
        }
    except Exception as e:
        logger.warning("Craigslist entry parse error: %s", e)
        return None


def scrape(
    location: str,
    min_price: Optional[int] = None,
    max_price: Optional[int] = None,
    beds_min: Optional[int] = None,
    beds_max: Optional[int] = None,
    limit: int = 200,
    listing_type: Optional[str] = "for_rent",
    **kwargs,
) -> list:
    """Scrape Craigslist rental listings via RSS feed."""
    subdomain = _city_to_subdomain(location)

    category_map = {
        "for_rent": "apa",
        "rooms": "roo",
    }
    category = category_map.get(listing_type or "for_rent", "apa")

    params = {}
    if min_price:
        params["min_price"] = min_price
    if max_price:
        params["max_price"] = max_price
    if beds_min:
        params["min_bedrooms"] = beds_min
    if beds_max:
        params["max_bedrooms"] = beds_max

    results = []
    seen_ids = set()

    rss_url = f"https://{subdomain}.craigslist.org/search/{category}?format=rss"
    if params:
        rss_url += "&" + urlencode(params)

    try:
        with httpx.Client(headers=random_headers(HEADER_EXTRAS), timeout=20, follow_redirects=True) as client:
            resp = client.get(rss_url)
            if resp.status_code != 200:
                logger.warning(
                    "Craigslist RSS returned %d for %s (subdomain: %s)",
                    resp.status_code, location, subdomain
                )
                return []

            xml_text = resp.text
            ns = {
                "atom": "http://www.w3.org/2005/Atom",
                "georss": "http://www.georss.org/georss",
            }

            try:
                root = ET.fromstring(xml_text.encode("utf-8"))
            except ET.ParseError:
                clean_xml = re.sub(r'&(?!(amp|lt|gt|apos|quot);)', '&amp;', xml_text)
                root = ET.fromstring(clean_xml.encode("utf-8"))

            entries = root.findall(".//item") or root.findall(".//{http://www.w3.org/2005/Atom}entry")

            for entry in entries:
                if len(results) >= limit:
                    break
                normalized = _parse_rss_entry(entry, ns)
                if normalized:
                    key = normalized.get("source_listing_id") or normalized.get("source_url")
                    if key and key not in seen_ids:
                        seen_ids.add(key)
                        results.append(normalized)

            logger.info("Craigslist: fetched %d listings from %s", len(results), rss_url)

    except Exception as e:
        logger.warning("Craigslist scrape failed for %s: %s", location, e)

    return results
