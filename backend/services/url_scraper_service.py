"""
URL-based scraper: scrape a specific property from a direct listing URL.
Supports Zillow and rentprogress.com detail pages.
"""

import json
import logging
import re
from datetime import datetime
from typing import Optional

import httpx
from homeharvest import scrape_property

from services.http_utils import random_headers, get_proxy_url
from services.scraper_service import normalize_row

logger = logging.getLogger(__name__)

STREET_TYPES = {
    "st", "ave", "dr", "ct", "blvd", "ln", "rd", "way", "pl",
    "cir", "ter", "trl", "pkwy", "hwy", "loop", "path", "run",
}


# ─────────────────────────────────────────────────────────────
#  Zillow
# ─────────────────────────────────────────────────────────────

def _parse_zillow_url(url: str) -> dict:
    """Return {'address': str, 'zpid': str} from a Zillow homedetails URL."""
    zpid = ""
    m = re.search(r"/(\d+)_zpid", url)
    if m:
        zpid = m.group(1)

    slug_m = re.search(r"/homedetails/(.+?)/\d+_zpid", url)
    address = ""
    if slug_m:
        slug = slug_m.group(1)
        m2 = re.search(r"^(.+)-([A-Z]{2})-(\d{5})$", slug, re.IGNORECASE)
        if m2:
            street_city_raw = m2.group(1)
            state = m2.group(2).upper()
            zipcode = m2.group(3)
            parts = street_city_raw.split("-")
            street_end = -1
            for i, part in enumerate(parts):
                if part.lower() in STREET_TYPES:
                    street_end = i
            if street_end == -1:
                street_end = min(2, len(parts) - 2)
            street = " ".join(parts[: street_end + 1])
            city = " ".join(parts[street_end + 1 :])
            address = f"{street}, {city}, {state} {zipcode}"

    return {"address": address, "zpid": zpid}


def _scrape_zillow_page(url: str) -> Optional[dict]:
    """Fetch a Zillow homedetails page and parse __NEXT_DATA__ JSON."""
    hdrs = {
        **random_headers(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Cache-Control": "max-age=0",
        "Upgrade-Insecure-Requests": "1",
    }
    try:
        with httpx.Client(
            headers=hdrs,
            timeout=30,
            follow_redirects=True,
            proxy=get_proxy_url(),
        ) as client:
            resp = client.get(url)
            if resp.status_code != 200:
                logger.warning("Zillow page returned %d for %s", resp.status_code, url)
                return None
            html = resp.text

            # 1. Try __NEXT_DATA__
            nd_m = re.search(
                r'<script[^>]+id="__NEXT_DATA__"[^>]*>\s*(\{.+?\})\s*</script>',
                html, re.DOTALL
            )
            if nd_m:
                try:
                    nd = json.loads(nd_m.group(1))
                    return _parse_zillow_next_data(nd, url)
                except Exception as e:
                    logger.debug("Zillow __NEXT_DATA__ parse error: %s", e)

            # 2. Try inline JSON blobs
            for pattern in [
                r'"property"\s*:\s*(\{[^{}]{50,}\})',
                r'window\.hdpDataModel\s*=\s*(\{.+?\});\s*(?:window|</)',
                r'"hdpData"\s*:\s*(\{.+?"price".+?\})',
            ]:
                pm = re.search(pattern, html, re.DOTALL)
                if pm:
                    try:
                        obj = json.loads(pm.group(1))
                        result = _parse_zillow_dict(obj, url)
                        if result and result.get("monthly_rent"):
                            return result
                    except Exception:
                        pass

            return None
    except Exception as e:
        logger.error("Zillow direct scrape failed for %s: %s", url, e)
        return None


def _parse_zillow_next_data(nd: dict, url: str) -> Optional[dict]:
    """Walk __NEXT_DATA__ tree to find property info."""
    # Try common paths
    candidates = []
    props = nd.get("props", {})
    page_props = props.get("pageProps", {})

    # gdp = general detail page data
    for key in ("gdpClientCache", "initialData", "property", "homeDetails", "hdpData"):
        val = page_props.get(key)
        if isinstance(val, dict):
            candidates.append(val)

    # Also check if pageProps itself has price info
    candidates.append(page_props)
    candidates.append(nd)

    for candidate in candidates:
        result = _find_zillow_property(candidate, url, depth=0)
        if result and result.get("monthly_rent"):
            return result

    return None


def _find_zillow_property(obj, url, depth=0):
    """Recursively search a JSON tree for Zillow property data."""
    if depth > 8 or not isinstance(obj, dict):
        return None

    # Direct hit: has price + address
    price_keys = {"price", "hdpTypeDimension", "rentZestimate", "zestimate", "listPrice", "listingPrice"}
    addr_keys = {"streetAddress", "address", "city"}
    if any(k in obj for k in price_keys) and any(k in obj for k in addr_keys):
        result = _parse_zillow_dict(obj, url)
        if result:
            return result

    # Recurse
    for v in obj.values():
        if isinstance(v, dict):
            result = _find_zillow_property(v, url, depth + 1)
            if result:
                return result
        elif isinstance(v, list):
            for item in v:
                if isinstance(item, dict):
                    result = _find_zillow_property(item, url, depth + 1)
                    if result:
                        return result

    return None


def _parse_zillow_dict(obj: dict, source_url: str) -> Optional[dict]:
    """Normalize a Zillow property dict from any JSON source."""
    def si(v):
        try:
            if v is None: return None
            return int(float(re.sub(r"[^0-9.]", "", str(v))))
        except Exception: return None

    def sf(v):
        try:
            if v is None: return None
            return float(re.sub(r"[^0-9.]", "", str(v)))
        except Exception: return None

    # Address
    addr = obj.get("streetAddress") or obj.get("address") or ""
    if isinstance(addr, dict):
        addr = addr.get("streetAddress") or addr.get("street") or ""
    city = obj.get("city") or obj.get("addressCity") or ""
    state = obj.get("state") or obj.get("addressState") or ""
    zipcode = str(obj.get("zipcode") or obj.get("zip") or obj.get("postalCode") or "")

    if not addr or not city:
        return None

    # Rent — prefer rentZestimate, then price (for_rent listings)
    rent = (si(obj.get("price"))
            or si(obj.get("listPrice"))
            or si(obj.get("rentZestimate"))
            or si(obj.get("zestimate"))
            or si(obj.get("hdpTypeDimension")))

    beds = si(obj.get("bedrooms") or obj.get("beds"))
    baths = sf(obj.get("bathrooms") or obj.get("baths") or obj.get("bathroomsFull"))
    sqft = si(obj.get("livingArea") or obj.get("squareFootage") or obj.get("sqft"))
    year_built = si(obj.get("yearBuilt"))
    desc = obj.get("description") or obj.get("remarks") or ""

    # Photos
    photos = []
    for key in ("originalPhotos", "photos", "images", "media"):
        raw = obj.get(key)
        if isinstance(raw, list):
            for item in raw:
                if isinstance(item, str) and item.startswith("http"):
                    photos.append(item)
                elif isinstance(item, dict):
                    for fk in ("url", "mixedSources", "src"):
                        v = item.get(fk)
                        if isinstance(v, str) and v.startswith("http"):
                            photos.append(v)
                            break
                        elif isinstance(v, dict):
                            jpeg = v.get("jpeg") or v.get("webp")
                            if isinstance(jpeg, list):
                                for j in jpeg:
                                    if isinstance(j, dict) and str(j.get("url", "")).startswith("http"):
                                        photos.append(j["url"])
                                        break
            if photos:
                break

    hero = obj.get("miniCardPhotos") or obj.get("primaryPhoto") or obj.get("heroImage")
    if isinstance(hero, list) and hero:
        hero = hero[0]
    if isinstance(hero, dict):
        hero = hero.get("url") or hero.get("src")
    if isinstance(hero, str) and hero.startswith("http") and hero not in photos:
        photos.insert(0, hero)

    prop_type = str(obj.get("homeType") or obj.get("propertyType") or "SINGLE_FAMILY")
    listing_id = str(obj.get("zpid") or obj.get("propertyId") or obj.get("listingId") or "")

    return {
        "source": "zillow",
        "source_url": source_url,
        "source_listing_id": f"zillow-{listing_id}" if listing_id else None,
        "status": "scraped",
        "address": addr,
        "city": city,
        "state": state,
        "zip": zipcode,
        "lat": sf(obj.get("latitude") or obj.get("lat")),
        "lng": sf(obj.get("longitude") or obj.get("lng")),
        "bedrooms": beds,
        "bathrooms": baths,
        "total_bathrooms": baths,
        "square_footage": sqft,
        "year_built": year_built,
        "monthly_rent": rent,
        "property_type": prop_type,
        "description": desc,
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
        "original_data": json.dumps({
            "listing_id": listing_id,
            "property_url": source_url,
            "list_price": rent,
            "status": "active",
        }),
        "scraped_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }


def _scrape_zillow_homeharvest(address: str, source_url: str) -> Optional[dict]:
    """Fallback: use homeharvest to find a property by address (any platform)."""
    from services.http_utils import get_homeharvest_proxy_kwarg
    proxy_kwargs = get_homeharvest_proxy_kwarg()

    for listing_type in ("for_rent", "for_sale"):
        try:
            df = scrape_property(
                location=address,
                listing_type=listing_type,
                limit=5,
                **proxy_kwargs,
            )
            if df is not None and len(df) > 0:
                row = df.iloc[0].to_dict()
                row["_source"] = "zillow"
                norm = normalize_row(row)
                norm["source"] = "zillow"
                norm["source_url"] = source_url
                norm["status"] = "scraped"
                return norm
        except Exception as e:
            logger.debug("homeharvest %s for '%s': %s", listing_type, address, e)

    return None


# ─────────────────────────────────────────────────────────────
#  rentprogress.com
# ─────────────────────────────────────────────────────────────

def _parse_rentprogress_url(url: str) -> dict:
    m = re.search(
        r"/property-details/(.+?)/(.+?)/([a-z]{2})/(\d{5})/(\d+)",
        url, re.IGNORECASE,
    )
    if not m:
        return {}
    return {
        "street": " ".join(w.capitalize() for w in m.group(1).replace("-", " ").split()),
        "city": " ".join(w.capitalize() for w in m.group(2).replace("-", " ").split()),
        "state": m.group(3).upper(),
        "zip": m.group(4),
        "id": m.group(5),
    }


def _scrape_rentprogress_url(url: str) -> Optional[dict]:
    parsed = _parse_rentprogress_url(url)
    if not parsed:
        logger.warning("Could not parse rentprogress URL: %s", url)
        return None

    prop_id = parsed["id"]
    hdrs = random_headers()

    # ── 1. Try known API endpoints ───────────────────────────
    api_candidates = [
        f"https://rentprogress.com/api/property/{prop_id}",
        f"https://rentprogress.com/api/homes/{prop_id}",
        f"https://rentprogress.com/api/v1/properties/{prop_id}",
        f"https://rentprogress.com/api/v2/properties/{prop_id}",
        f"https://rentprogress.com/wp-json/pr/v1/property/{prop_id}",
    ]
    for api_url in api_candidates:
        try:
            with httpx.Client(
                headers={**hdrs, "Accept": "application/json"},
                timeout=20,
                follow_redirects=True,
                proxy=get_proxy_url(),
            ) as client:
                resp = client.get(api_url)
                if resp.status_code == 200:
                    data = resp.json()
                    home = data if isinstance(data, dict) else (data[0] if isinstance(data, list) and data else None)
                    if home and isinstance(home, dict):
                        result = _normalize_rentprogress(home, url, parsed)
                        if result:
                            return result
        except Exception as e:
            logger.debug("rentprogress API %s: %s", api_url, e)

    # ── 2. Fetch HTML page ───────────────────────────────────
    try:
        with httpx.Client(headers=hdrs, timeout=30, follow_redirects=True, proxy=get_proxy_url()) as client:
            resp = client.get(url)
            html = resp.text if resp.status_code == 200 else ""
    except Exception as e:
        logger.error("rentprogress fetch failed: %s", e)
        html = ""

    if html:
        # ── Always extract rent+photos from HTML first ────────
        html_rent = _extract_base_rent_from_html(html) or _extract_rent_from_html(html)
        html_photos = _extract_photos_from_html(html)
        logger.debug("rentprogress HTML: rent=%s photos=%d", html_rent, len(html_photos))

        # Try __NEXT_DATA__
        nd_m = re.search(
            r'<script[^>]+id="__NEXT_DATA__"[^>]*>\s*(\{.+?\})\s*</script>',
            html, re.DOTALL
        )
        if nd_m:
            try:
                nd = json.loads(nd_m.group(1))
                result = _find_rentprogress_data(nd, url, parsed)
                if result:
                    if not result.get("monthly_rent") and html_rent:
                        result["monthly_rent"] = html_rent
                    if html_photos:
                        result["original_image_urls"] = json.dumps(html_photos)
                    return result
            except Exception as e:
                logger.debug("rentprogress __NEXT_DATA__ error: %s", e)

        # Try JSON-LD (handles both flat and @graph arrays)
        jsonld_result = None
        for m in re.finditer(
            r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>',
            html, re.DOTALL | re.IGNORECASE
        ):
            try:
                obj = json.loads(m.group(1))
                candidates = obj if isinstance(obj, list) else obj.get("@graph", [obj]) if isinstance(obj, dict) else []
                for item in candidates:
                    if not isinstance(item, dict):
                        continue
                    if item.get("@type") in (
                        "SingleFamilyResidence", "House", "RealEstateListing",
                        "Residence", "Apartment",
                    ):
                        jsonld_result = _normalize_rentprogress(item, url, parsed)
                        if jsonld_result:
                            break
            except Exception:
                pass
            if jsonld_result:
                break

        if jsonld_result:
            # Merge HTML rent and all photos into the JSON-LD result
            if not jsonld_result.get("monthly_rent") and html_rent:
                jsonld_result["monthly_rent"] = html_rent
            if html_photos:
                jsonld_result["original_image_urls"] = json.dumps(html_photos)
            return jsonld_result

        # Try inline window state
        for pattern in [
            r'window\.__INITIAL_STATE__\s*=\s*({.+?});\s*(?:window|</)',
            r'window\.__APP_STATE__\s*=\s*({.+?});\s*(?:window|</)',
            r'"propertyDetails"\s*:\s*({.+?"rent".+?})',
            r'"property"\s*:\s*({[^{}]{30,}})',
        ]:
            jm = re.search(pattern, html, re.DOTALL)
            if jm:
                try:
                    obj = json.loads(jm.group(1))
                    result = _normalize_rentprogress(obj, url, parsed)
                    if result:
                        if not result.get("monthly_rent") and html_rent:
                            result["monthly_rent"] = html_rent
                        if html_photos:
                            result["original_image_urls"] = json.dumps(html_photos)
                        return result
                except Exception:
                    pass

        # ── Fallback: pure HTML parsing ───────────────────────
        beds = _extract_int_from_html(html, r"(\d+)\s*(?:bed|br|bedroom)", default=None)
        baths = _extract_float_from_html(html, r"([\d.]+)\s*(?:bath|ba|bathroom)", default=None)
        sqft = _extract_int_from_html(html, r"([\d,]+)\s*(?:sq\s*ft|sqft|square\s*f)", default=None)
        desc = ""
        dm = re.search(r'"description"\s*:\s*"([^"]{30,})"', html)
        if dm:
            desc = dm.group(1).replace("\\n", " ").strip()

        return {
            "source": "progress_residential",
            "source_url": url,
            "source_listing_id": f"pr-{prop_id}",
            "status": "scraped",
            "address": parsed["street"],
            "city": parsed["city"],
            "state": parsed["state"],
            "zip": parsed["zip"],
            "lat": None,
            "lng": None,
            "bedrooms": beds,
            "bathrooms": baths,
            "total_bathrooms": baths,
            "square_footage": sqft,
            "monthly_rent": html_rent,
            "property_type": "Single Family",
            "description": desc,
            "amenities": "[]",
            "original_image_urls": json.dumps(html_photos),
            "local_image_paths": "[]",
            "edited_fields": "[]",
            "inferred_features": "[]",
            "appliances": "[]",
            "utilities_included": "[]",
            "flooring": "[]",
            "lease_terms": "[]",
            "pet_types_allowed": "[]",
            "original_data": json.dumps({"listing_id": prop_id, "property_url": url}),
            "scraped_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }

    # ── 4. Stub with what we know from the URL ───────────────
    return _build_stub(parsed, url, prop_id)


def _find_rentprogress_data(nd: dict, url: str, parsed: dict) -> Optional[dict]:
    """Walk __NEXT_DATA__ tree for rentprogress property info."""
    def _walk(obj, depth=0):
        if depth > 8 or not isinstance(obj, dict):
            return None
        rent_keys = {"rent", "price", "monthly_rent", "listPrice", "monthlyRent"}
        if any(k in obj for k in rent_keys):
            r = _normalize_rentprogress(obj, url, parsed)
            if r and r.get("monthly_rent"):
                return r
        for v in obj.values():
            if isinstance(v, dict):
                r = _walk(v, depth + 1)
                if r:
                    return r
            elif isinstance(v, list):
                for item in v:
                    if isinstance(item, dict):
                        r = _walk(item, depth + 1)
                        if r:
                            return r
        return None

    return _walk(nd)


def _extract_base_rent_from_html(html: str) -> Optional[int]:
    """Extract 'Base Rent' specifically from rentprogress fee tables."""
    m = re.search(
        r'Base\s+Rent[^$]{0,100}\$([\d,]+)',
        html, re.IGNORECASE | re.DOTALL
    )
    if m:
        try:
            val = int(m.group(1).replace(",", ""))
            if 200 <= val <= 50000:
                return val
        except Exception:
            pass
    return None


def _extract_rent_from_html(html: str) -> Optional[int]:
    for pattern in [
        r'"\s*(?:rent|price|monthlyRent|listPrice)"\s*:\s*"?\$?([\d,]+)"?',
        r'\$\s*([\d,]{3,})\s*/\s*(?:mo|month)',
        r'>\s*\$\s*([\d,]{3,})\s*<',
    ]:
        m = re.search(pattern, html, re.IGNORECASE)
        if m:
            try:
                val = int(m.group(1).replace(",", ""))
                if 200 <= val <= 50000:
                    return val
            except Exception:
                pass
    return None


def _extract_int_from_html(html: str, pattern: str, default=None) -> Optional[int]:
    m = re.search(pattern, html, re.IGNORECASE)
    if m:
        try:
            return int(m.group(1).replace(",", ""))
        except Exception:
            pass
    return default


def _extract_float_from_html(html: str, pattern: str, default=None) -> Optional[float]:
    m = re.search(pattern, html, re.IGNORECASE)
    if m:
        try:
            return float(m.group(1))
        except Exception:
            pass
    return default


def _extract_photos_from_html(html: str) -> list:
    photos = []
    seen = set()
    for pattern in [
        r'https://photos\.rentprogress\.com/[^\s"\'<>]+\.(?:jpg|jpeg|png|webp)',
        r'https://[^\s"\'<>]+rentprogress[^\s"\'<>]+\.(?:jpg|jpeg|png|webp)',
    ]:
        for m in re.finditer(pattern, html, re.IGNORECASE):
            u = m.group(0).rstrip("\\")
            if u not in seen:
                seen.add(u)
                photos.append(u)
    return photos


def _normalize_rentprogress(home: dict, source_url: str, parsed: dict) -> Optional[dict]:
    def si(v):
        try:
            if v is None: return None
            return int(float(re.sub(r"[^0-9.]", "", str(v))))
        except Exception: return None

    def sf(v):
        try:
            if v is None: return None
            s = str(v).strip()
            neg = s.startswith("-")
            val = float(re.sub(r"[^0-9.]", "", s))
            return -val if neg else val
        except Exception: return None

    addr_obj = home.get("address") or {}
    if isinstance(addr_obj, dict):
        addr = (addr_obj.get("streetAddress") or addr_obj.get("street")
                or home.get("streetAddress") or home.get("street_address")
                or parsed.get("street", ""))
        city = addr_obj.get("addressLocality") or home.get("city") or parsed.get("city", "")
        state = addr_obj.get("addressRegion") or home.get("state") or parsed.get("state", "")
        zipcode = str(addr_obj.get("postalCode") or home.get("zip") or home.get("zipCode") or parsed.get("zip", ""))
    else:
        addr = addr_obj or home.get("streetAddress") or home.get("street_address") or parsed.get("street", "")
        city = home.get("addressLocality") or home.get("city") or parsed.get("city", "")
        state = home.get("addressRegion") or home.get("state") or parsed.get("state", "")
        zipcode = str(home.get("postalCode") or home.get("zip") or home.get("zipCode") or parsed.get("zip", ""))

    beds = si(home.get("numberOfBedrooms") or home.get("numberOfRooms")
              or home.get("beds") or home.get("bedrooms") or home.get("bedroom_count"))
    baths = sf(home.get("numberOfBathroomsTotal") or home.get("baths") or home.get("bathrooms"))
    sqft_raw = home.get("floorSize") or home.get("sqft") or home.get("squareFeet") or home.get("square_feet")
    sqft = si(sqft_raw.get("value") if isinstance(sqft_raw, dict) else sqft_raw)

    rent_raw = (home.get("price") or home.get("rent") or home.get("monthly_rent") or
                home.get("listPrice") or home.get("monthlyRent"))
    if isinstance(rent_raw, dict):
        rent_raw = rent_raw.get("minPrice") or rent_raw.get("price")
    rent = si(rent_raw)

    # Geo — handle nested GeoCoordinates object; JSON-LD sometimes swaps lat/lng
    geo = home.get("geo") or {}
    raw_lat = sf(geo.get("latitude") if isinstance(geo, dict) else home.get("latitude"))
    raw_lng = sf(geo.get("longitude") if isinstance(geo, dict) else home.get("longitude"))
    # Correct swapped coordinates: latitude must be positive for US (north)
    if raw_lat is not None and raw_lng is not None and raw_lat < 0 < raw_lng:
        raw_lat, raw_lng = raw_lng, raw_lat
    lat = raw_lat or sf(home.get("latitude"))
    lng = raw_lng or sf(home.get("longitude"))

    photos = []
    for key in ("photo", "photos", "images", "image", "media", "gallery"):
        raw = home.get(key)
        if isinstance(raw, str) and raw.startswith("http"):
            photos.append(raw)
        elif isinstance(raw, list):
            for item in raw:
                if isinstance(item, str) and item.startswith("http"):
                    photos.append(item)
                elif isinstance(item, dict):
                    for fk in ("url", "src", "href", "contentUrl"):
                        if str(item.get(fk, "")).startswith("http"):
                            photos.append(item[fk])
                            break
            if photos:
                break

    hero = home.get("image") or home.get("thumbnail") or home.get("primary_photo")
    if isinstance(hero, list): hero = hero[0] if hero else None
    if isinstance(hero, dict): hero = hero.get("url") or hero.get("contentUrl")
    if isinstance(hero, str) and hero.startswith("http") and hero not in photos:
        photos.insert(0, hero)

    description = home.get("description") or ""
    listing_id = re.sub(r"[^0-9]", "",
        str(home.get("id") or home.get("property_id") or home.get("listing_id") or parsed.get("id", ""))
    ) or parsed.get("id", "")

    if not addr:
        return None

    return {
        "source": "progress_residential",
        "source_url": source_url,
        "source_listing_id": f"pr-{listing_id}" if listing_id else None,
        "status": "scraped",
        "address": addr,
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
        "property_type": "Single Family",
        "description": description,
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
        "original_data": json.dumps({"listing_id": listing_id, "property_url": source_url, "list_price": rent}),
        "scraped_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }


def _build_stub(parsed: dict, source_url: str, prop_id: str) -> dict:
    return {
        "source": "progress_residential",
        "source_url": source_url,
        "source_listing_id": f"pr-{prop_id}",
        "status": "scraped",
        "address": parsed.get("street", ""),
        "city": parsed.get("city", ""),
        "state": parsed.get("state", ""),
        "zip": parsed.get("zip", ""),
        "lat": None, "lng": None,
        "bedrooms": None, "bathrooms": None, "total_bathrooms": None,
        "square_footage": None, "monthly_rent": None,
        "property_type": "Single Family",
        "description": "",
        "amenities": "[]", "original_image_urls": "[]",
        "local_image_paths": "[]", "edited_fields": "[]",
        "inferred_features": "[]", "appliances": "[]",
        "utilities_included": "[]", "flooring": "[]",
        "lease_terms": "[]", "pet_types_allowed": "[]",
        "original_data": json.dumps({"listing_id": prop_id, "property_url": source_url}),
        "scraped_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }


# ─────────────────────────────────────────────────────────────
#  Public entry point
# ─────────────────────────────────────────────────────────────

def scrape_by_url(url: str) -> Optional[dict]:
    """Detect URL type and dispatch to the correct scraper."""
    url = url.strip()

    if "zillow.com/homedetails" in url:
        info = _parse_zillow_url(url)
        logger.info("Scraping Zillow: %s  (zpid=%s)", info.get("address"), info.get("zpid"))

        # First try direct page scrape (fastest, richest data)
        result = _scrape_zillow_page(url)
        if result:
            return result

        # Fallback: homeharvest / realtor.com
        if info.get("address"):
            result = _scrape_zillow_homeharvest(info["address"], url)
            if result:
                return result

        return None

    if "rentprogress.com" in url or "progressresidential.com" in url:
        logger.info("Scraping rentprogress.com: %s", url)
        return _scrape_rentprogress_url(url)

    logger.warning("Unsupported URL: %s", url)
    return None
