"""
Apartments.com scraper — fetches rental listings from Apartments.com.
Uses their public search page and parses embedded JSON/schema.org data.
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

# Phase 2 (2.8): UA rotation — UA is supplied per-request by random_headers().
HEADER_EXTRAS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

BASE_URL = "https://www.apartments.com"


def _location_to_slug(location: str) -> str:
    """Convert 'Austin, TX' → 'austin-tx' for Apartments.com URLs."""
    location = location.strip().lower()
    location = re.sub(r"[,\s]+", "-", location)
    location = re.sub(r"-+", "-", location).strip("-")
    return location


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


def _normalize_jsonld(item: dict) -> Optional[dict]:
    """Normalize a schema.org ApartmentComplex/Apartment JSON-LD object."""
    name = item.get("name") or ""
    description = item.get("description") or ""
    url = item.get("url") or item.get("@id") or ""

    address = item.get("address") or {}
    street = address.get("streetAddress") or ""
    city = address.get("addressLocality") or ""
    state = address.get("addressRegion") or ""
    zip_code = str(address.get("postalCode") or "")

    geo = item.get("geo") or {}
    lat = _safe_float(geo.get("latitude"))
    lng = _safe_float(geo.get("longitude"))

    photos = []
    for img_key in ("image", "photo", "photos"):
        imgs = item.get(img_key)
        if imgs:
            if isinstance(imgs, str) and imgs.startswith("http"):
                photos.append(imgs)
            elif isinstance(imgs, list):
                for img in imgs:
                    if isinstance(img, str) and img.startswith("http"):
                        photos.append(img)
                    elif isinstance(img, dict) and img.get("url", "").startswith("http"):
                        photos.append(img["url"])

    offers = item.get("makesOffer") or item.get("offers") or []
    price = None
    beds = None
    baths = None
    sqft = None

    if isinstance(offers, list) and offers:
        offer = offers[0]
        price = _safe_int(offer.get("price") or offer.get("lowPrice") or offer.get("priceRange"))
        beds = _safe_int(offer.get("numberOfBedrooms") or offer.get("bedrooms"))
        baths = _safe_float(offer.get("numberOfBathroomsFull") or offer.get("bathrooms"))
        sqft = _safe_int(offer.get("floorSize", {}).get("value") if isinstance(offer.get("floorSize"), dict) else offer.get("floorSize"))

    if not price:
        price = _safe_int(item.get("priceRange") or item.get("price"))
    if not beds:
        beds = _safe_int(item.get("numberOfBedrooms") or item.get("bedrooms"))
    if not baths:
        baths = _safe_float(item.get("numberOfBathroomsFull") or item.get("bathrooms"))

    listing_id = url.replace(BASE_URL, "").strip("/").replace("/", "-") or None

    amenities_raw = item.get("amenityFeature") or []
    amenities = []
    if isinstance(amenities_raw, list):
        for a in amenities_raw:
            if isinstance(a, dict) and a.get("name"):
                amenities.append(a["name"])
            elif isinstance(a, str):
                amenities.append(a)

    if not street and not city:
        return None

    return {
        "source": "apartments",
        "source_url": url,
        "source_listing_id": f"apts-{listing_id}" if listing_id else None,
        "status": "scraped",
        "title": name,
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
        "property_type": item.get("@type") or "Apartment",
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
        "original_data": json.dumps(item),
        "scraped_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
        "_list_date": None,
        "_days_on_market": None,
    }


def _normalize_card(card, base_url: str) -> Optional[dict]:
    """Normalize a listing card element from the Apartments.com search page."""
    try:
        listing_id = card.get("data-listingid") or card.get("data-id") or ""
        url_tag = card.find("a", class_=re.compile(r"property-link|listing-link|js-url", re.I))
        url = ""
        if url_tag and url_tag.get("href"):
            href = url_tag["href"]
            url = href if href.startswith("http") else BASE_URL + href

        title_tag = card.find(class_=re.compile(r"js-placardTitle|property-title|listing-title", re.I))
        title = title_tag.get_text(strip=True) if title_tag else ""

        address_tag = card.find(class_=re.compile(r"property-address|location|address", re.I))
        address_text = address_tag.get_text(strip=True) if address_tag else ""

        street = ""
        city = ""
        state = ""
        zip_code = ""
        addr_parts = address_text.split(",")
        if len(addr_parts) >= 2:
            street = addr_parts[0].strip()
            rest = addr_parts[1].strip()
            state_zip = rest.split()
            if len(state_zip) >= 2:
                city = " ".join(state_zip[:-2]) if len(state_zip) > 2 else ""
                state = state_zip[-2] if len(state_zip) >= 2 else ""
                zip_code = state_zip[-1]
        elif address_text:
            street = address_text

        price_tag = card.find(class_=re.compile(r"price-range|js-price|rent", re.I))
        price = None
        if price_tag:
            price_text = price_tag.get_text(strip=True)
            price_match = re.search(r"\$?([\d,]+)", price_text)
            if price_match:
                price = int(price_match.group(1).replace(",", ""))

        beds = None
        baths = None
        info_tag = card.find(class_=re.compile(r"bed-range|property-beds|property-info-details", re.I))
        if info_tag:
            text = info_tag.get_text(strip=True).lower()
            bed_m = re.search(r"(\d+)(?:\s*-\s*\d+)?\s*(?:bed|bd)", text)
            bath_m = re.search(r"([\d.]+)(?:\s*-\s*[\d.]+)?\s*(?:bath|ba)", text)
            if bed_m:
                beds = int(bed_m.group(1))
            if bath_m:
                baths = float(bath_m.group(1))

        sqft = None
        sqft_tag = card.find(class_=re.compile(r"sqft|square-feet|sq-ft", re.I))
        if sqft_tag:
            sqft_text = sqft_tag.get_text(strip=True)
            sqft_m = re.search(r"([\d,]+)", sqft_text)
            if sqft_m:
                sqft = int(sqft_m.group(1).replace(",", ""))

        photos = []
        img_tags = card.find_all("img", limit=10)
        for img in img_tags:
            src = img.get("data-src") or img.get("src") or ""
            if src.startswith("http") and any(ext in src for ext in [".jpg", ".jpeg", ".png", ".webp"]):
                photos.append(src)

        if not street and not title:
            return None

        return {
            "source": "apartments",
            "source_url": url,
            "source_listing_id": f"apts-{listing_id}" if listing_id else None,
            "status": "scraped",
            "title": title,
            "address": street,
            "city": city,
            "state": state,
            "zip": zip_code,
            "bedrooms": beds,
            "bathrooms": baths,
            "total_bathrooms": baths,
            "square_footage": sqft,
            "monthly_rent": price,
            "property_type": "Apartment",
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
        logger.warning("Apartments.com card parse error: %s", e)
        return None


def scrape(
    location: str,
    min_price: Optional[int] = None,
    max_price: Optional[int] = None,
    beds_min: Optional[int] = None,
    limit: int = 200,
    **kwargs,
) -> list:
    """Scrape rental listings from Apartments.com."""
    slug = _location_to_slug(location)
    results = []
    page = 1

    price_suffix = ""
    if min_price and max_price:
        price_suffix = f"{min_price}-to-{max_price}/"
    elif min_price:
        price_suffix = f"over-{min_price}/"
    elif max_price:
        price_suffix = f"under-{max_price}/"

    beds_suffix = ""
    if beds_min:
        bed_map = {1: "1-bedrooms", 2: "2-bedrooms", 3: "3-bedrooms", 4: "4-bedrooms"}
        beds_suffix = bed_map.get(beds_min, f"{beds_min}-bedrooms") + "/"

    while len(results) < limit:
        url = f"{BASE_URL}/{slug}/{beds_suffix}{price_suffix}"
        if page > 1:
            url += f"{page}/"

        try:
            with httpx.Client(headers=random_headers(HEADER_EXTRAS), timeout=25, follow_redirects=True, proxies=get_proxy_map()) as client:
                resp = client.get(url)
                if resp.status_code == 404:
                    url = f"{BASE_URL}/apartments/{slug}/"
                    if page > 1:
                        url += f"{page}/"
                    resp = client.get(url)

                if resp.status_code != 200:
                    logger.warning("Apartments.com returned %d for %s", resp.status_code, url)
                    break

                html = resp.text
                soup = BeautifulSoup(html, "lxml")

                jsonld_tags = soup.find_all("script", type="application/ld+json")
                page_results = []
                for tag in jsonld_tags:
                    try:
                        data = json.loads(tag.string or "")
                        items = data if isinstance(data, list) else [data]
                        for item in items:
                            if item.get("@type") in (
                                "ApartmentComplex", "Apartment",
                                "SingleFamilyResidence", "House", "RealEstateListing"
                            ):
                                normalized = _normalize_jsonld(item)
                                if normalized:
                                    page_results.append(normalized)
                    except Exception:
                        pass

                if not page_results:
                    cards = soup.find_all(
                        "article",
                        class_=re.compile(r"placard|listing-item|property-listing", re.I)
                    )
                    for card in cards:
                        normalized = _normalize_card(card, url)
                        if normalized:
                            page_results.append(normalized)

                if not page_results:
                    json_match = re.search(
                        r'window\.__SEARCH_STATE__\s*=\s*(\{.+?\});',
                        html, re.DOTALL
                    )
                    if json_match:
                        try:
                            state_data = json.loads(json_match.group(1))
                            listings = (
                                state_data.get("listings") or
                                state_data.get("results") or
                                state_data.get("properties") or []
                            )
                            for item in listings:
                                try:
                                    normalized = _normalize_jsonld(item)
                                    if normalized:
                                        page_results.append(normalized)
                                except Exception:
                                    pass
                        except Exception:
                            pass

                if not page_results:
                    logger.info("Apartments.com: no listings found on page %d for %s", page, location)
                    break

                results.extend(page_results)
                logger.info("Apartments.com: page %d returned %d listings", page, len(page_results))

                next_btn = soup.find("a", attrs={"data-page": str(page + 1)}) or \
                           soup.find("a", class_=re.compile(r"next|next-page", re.I))
                if not next_btn:
                    break
                page += 1

        except Exception as e:
            logger.warning("Apartments.com scrape error (page %d): %s", page, e)
            break

    seen_ids = set()
    unique = []
    for r in results[:limit]:
        key = r.get("source_listing_id") or r.get("source_url") or id(r)
        if key not in seen_ids:
            seen_ids.add(key)
            unique.append(r)

    return unique
