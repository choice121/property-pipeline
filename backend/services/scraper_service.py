import json
import uuid
from datetime import datetime
from typing import Optional

from homeharvest import scrape_property


def generate_property_id() -> str:
    return "PP-" + str(uuid.uuid4()).replace("-", "")[:6].upper()


def safe_val(val):
    try:
        import math
        if val is None:
            return None
        if isinstance(val, float) and math.isnan(val):
            return None
        return val
    except Exception:
        return None


def normalize_row(row: dict, source: str) -> dict:
    def get(key):
        v = row.get(key)
        return safe_val(v)

    img_srcs = get("img_srcs")
    if img_srcs is None:
        image_urls = []
    elif isinstance(img_srcs, list):
        image_urls = img_srcs
    else:
        image_urls = []

    virtual_tours = get("virtual_tours")
    if isinstance(virtual_tours, list) and len(virtual_tours) > 0:
        virtual_tour_url = virtual_tours[0]
    else:
        virtual_tour_url = None

    row_serializable = {}
    for k, v in row.items():
        sv = safe_val(v)
        if isinstance(sv, (list, dict)):
            row_serializable[k] = sv
        elif sv is None:
            row_serializable[k] = None
        else:
            try:
                json.dumps(sv)
                row_serializable[k] = sv
            except Exception:
                row_serializable[k] = str(sv)

    return {
        "source": source,
        "source_url": get("property_url"),
        "source_listing_id": str(get("mls_id")) if get("mls_id") is not None else None,
        "status": "scraped",
        "address": get("street"),
        "city": get("city"),
        "state": get("state"),
        "zip": str(get("zip_code")) if get("zip_code") is not None else None,
        "county": get("county"),
        "lat": get("latitude"),
        "lng": get("longitude"),
        "bedrooms": int(get("beds")) if get("beds") is not None else None,
        "bathrooms": float(get("full_baths")) if get("full_baths") is not None else None,
        "square_footage": int(get("sqft")) if get("sqft") is not None else None,
        "lot_size_sqft": int(get("lot_sqft")) if get("lot_sqft") is not None else None,
        "monthly_rent": int(get("list_price")) if get("list_price") is not None else None,
        "property_type": get("style"),
        "year_built": int(get("year_built")) if get("year_built") is not None else None,
        "description": get("text"),
        "virtual_tour_url": virtual_tour_url,
        "original_image_urls": json.dumps(image_urls),
        "local_image_paths": "[]",
        "original_data": json.dumps(row_serializable),
        "edited_fields": "[]",
        "scraped_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }


def scrape(
    location: str,
    source: str = "zillow",
    listing_type: str = "for_rent",
    min_price: Optional[int] = None,
    max_price: Optional[int] = None,
    bedrooms: Optional[int] = None,
):
    site_map = {
        "zillow": "zillow",
        "realtor": "realtor.com",
        "redfin": "redfin",
    }
    site_name = site_map.get(source, "zillow")

    kwargs = dict(
        location=location,
        listing_type=listing_type,
        site_name=[site_name],
        past_days=60,
    )

    df = scrape_property(**kwargs)

    if df is None or len(df) == 0:
        return []

    results = []
    for _, row in df.iterrows():
        row_dict = row.to_dict()
        normalized = normalize_row(row_dict, source)

        if min_price is not None and normalized.get("monthly_rent") is not None:
            if normalized["monthly_rent"] < min_price:
                continue
        if max_price is not None and normalized.get("monthly_rent") is not None:
            if normalized["monthly_rent"] > max_price:
                continue
        if bedrooms is not None and normalized.get("bedrooms") is not None:
            if normalized["bedrooms"] != bedrooms:
                continue

        results.append(normalized)

    return results
