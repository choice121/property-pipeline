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


def normalize_row(row: dict) -> dict:
    def get(key):
        v = row.get(key)
        return safe_val(v)

    # New HomeHarvest uses alt_photos and primary_photo instead of img_srcs
    alt_photos = get("alt_photos")
    primary_photo = get("primary_photo")

    image_urls = []
    if primary_photo and isinstance(primary_photo, str):
        image_urls.append(primary_photo)
    if isinstance(alt_photos, list):
        for url in alt_photos:
            if url and url not in image_urls:
                image_urls.append(url)
    elif isinstance(alt_photos, str) and alt_photos:
        image_urls.append(alt_photos)

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
        "source": "realtor",
        "source_url": get("property_url"),
        "source_listing_id": str(get("mls_id")) if get("mls_id") is not None else str(get("listing_id")) if get("listing_id") is not None else None,
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
        "half_bathrooms": int(get("half_baths")) if get("half_baths") is not None else None,
        "square_footage": int(get("sqft")) if get("sqft") is not None else None,
        "lot_size_sqft": int(get("lot_sqft")) if get("lot_sqft") is not None else None,
        "monthly_rent": int(get("list_price")) if get("list_price") is not None else None,
        "property_type": get("style"),
        "year_built": int(get("year_built")) if get("year_built") is not None else None,
        "description": get("text"),
        "virtual_tour_url": None,
        "original_image_urls": json.dumps(image_urls),
        "local_image_paths": "[]",
        "original_data": json.dumps(row_serializable),
        "edited_fields": "[]",
        "scraped_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }


def scrape(
    location: str,
    listing_type: str = "for_rent",
    min_price: Optional[int] = None,
    max_price: Optional[int] = None,
    bedrooms: Optional[int] = None,
):
    kwargs = dict(
        location=location,
        listing_type=listing_type,
        past_days=60,
        price_min=min_price,
        price_max=max_price,
        beds_min=bedrooms,
        beds_max=bedrooms,
    )
    # Remove None values to avoid passing null filters
    kwargs = {k: v for k, v in kwargs.items() if v is not None}
    kwargs["location"] = location
    kwargs["listing_type"] = listing_type
    kwargs["past_days"] = 60

    df = scrape_property(**kwargs)

    if df is None or len(df) == 0:
        return []

    results = []
    for _, row in df.iterrows():
        row_dict = row.to_dict()
        normalized = normalize_row(row_dict)
        results.append(normalized)

    return results
