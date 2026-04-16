import json
import logging
import re
import uuid
from datetime import datetime
from typing import List, Optional

from homeharvest import scrape_property

logger = logging.getLogger(__name__)

HOMEHARVEST_SOURCES = {"realtor", "zillow", "redfin"}
CUSTOM_SOURCES = {"opendoor", "apartments", "craigslist", "hotpads", "invitation_homes", "progress_residential"}
ALL_SOURCES = HOMEHARVEST_SOURCES | CUSTOM_SOURCES

HOMEHARVEST_SITE_MAP = {
    "realtor": "realtor.com",
    "zillow": "zillow",
    "redfin": "redfin",
}


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


FIELD_FALLBACKS = {
    "monthly_rent":     ["list_price", "list_price_min", "rent", "price", "asking_price"],
    "description":      ["text", "description", "property_description", "remarks", "public_remarks", "agent_remarks"],
    "security_deposit": ["security_deposit", "deposit", "deposit_amount", "security", "move_in_deposit"],
    "available_date":   ["date_available", "available_date", "move_in_date", "date_available_text", "availability"],
    "laundry":          ["laundry", "laundry_type", "laundry_features", "laundry_location"],
    "parking":          ["parking_garage", "parking", "parking_type", "garage_spaces", "parking_spaces"],
}

WEIGHTED_QUALITY_FIELDS = {
    "address":           {"weight": 10, "group": "location"},
    "city":              {"weight": 5,  "group": "location"},
    "state":             {"weight": 5,  "group": "location"},
    "zip":               {"weight": 3,  "group": "location"},
    "monthly_rent":      {"weight": 20, "group": "rent"},
    "bedrooms":          {"weight": 8,  "group": "beds_baths"},
    "bathrooms":         {"weight": 6,  "group": "beds_baths"},
    "photos":            {"weight": 15, "group": "photos"},
    "description":       {"weight": 10, "group": "description"},
    "property_type":     {"weight": 4,  "group": "type"},
    "available_date":    {"weight": 4,  "group": "date"},
    "square_footage":    {"weight": 3,  "group": "size"},
    "laundry_type":      {"weight": 2,  "group": "amenities"},
    "heating_type":      {"weight": 2,  "group": "amenities"},
    "amenities":         {"weight": 2,  "group": "amenities"},
    "appliances":        {"weight": 1,  "group": "amenities"},
}


def _calculate_weighted_quality(prop: dict, image_urls: list) -> tuple[int, list]:
    """
    Calculate a weighted quality score (0-100) that reflects actual publish-readiness.
    Returns (score, missing_fields).
    """
    missing = []
    earned = 0
    total_weight = sum(f["weight"] for f in WEIGHTED_QUALITY_FIELDS.values())

    checks = {
        "address":        prop.get("address"),
        "city":           prop.get("city"),
        "state":          prop.get("state"),
        "zip":            prop.get("zip"),
        "monthly_rent":   prop.get("monthly_rent"),
        "bedrooms":       prop.get("bedrooms"),
        "bathrooms":      prop.get("bathrooms") or prop.get("total_bathrooms"),
        "photos":         image_urls if len(image_urls) >= 3 else None,
        "description":    prop.get("description") if prop.get("description") and len(str(prop.get("description", ""))) >= 50 else None,
        "property_type":  prop.get("property_type"),
        "available_date": prop.get("available_date"),
        "square_footage": prop.get("square_footage"),
        "laundry_type":   prop.get("laundry_type"),
        "heating_type":   prop.get("heating_type"),
        "amenities":      prop.get("amenities") if prop.get("amenities") and prop.get("amenities") != "[]" else None,
        "appliances":     prop.get("appliances") if prop.get("appliances") and prop.get("appliances") != "[]" else None,
    }

    for field, cfg in WEIGHTED_QUALITY_FIELDS.items():
        val = checks.get(field)
        if val in (None, "", [], {}, "[]"):
            missing.append(field)
        else:
            earned += cfg["weight"]

    score = round((earned / total_weight) * 100)
    return score, missing


def normalize_row(row: dict) -> dict:
    def get(key):
        v = row.get(key)
        return safe_val(v)

    alt_photos = get("alt_photos")
    primary_photo = get("primary_photo")

    def _extract_urls(value) -> list:
        """Extract all individual image URLs from whatever format alt_photos arrives in."""
        urls = []
        if not value:
            return urls
        if isinstance(value, list):
            for item in value:
                if isinstance(item, str) and item.strip().startswith("http"):
                    urls.append(item.strip())
                elif isinstance(item, dict):
                    for candidate in ("url", "href", "src", "photo_url"):
                        if item.get(candidate, "").startswith("http"):
                            urls.append(item[candidate].strip())
                            break
        elif isinstance(value, str):
            for part in value.split(","):
                part = part.strip()
                if part.startswith("http"):
                    urls.append(part)
        return urls

    image_urls = []
    for url in _extract_urls(alt_photos):
        if url not in image_urls:
            image_urls.append(url)

    if primary_photo and isinstance(primary_photo, str) and primary_photo.startswith("http"):
        primary_photo = primary_photo.strip()
        if primary_photo not in image_urls:
            image_urls.insert(0, primary_photo)

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

    dogs = get("dogs_allowed")
    cats = get("cats_allowed")
    if dogs or cats:
        pets_allowed = True
    elif dogs is False and cats is False:
        pets_allowed = False
    else:
        pets_allowed = None

    parking_garage = get("parking_garage")
    if parking_garage:
        try:
            spots = int(parking_garage)
            parking = f"{spots} garage space{'s' if spots != 1 else ''}"
        except Exception:
            parking = str(parking_garage)
    else:
        parking = None

    list_date = get("list_date")
    if list_date is not None:
        try:
            list_date = str(list_date)[:10]
        except Exception:
            list_date = None

    days_on_market = get("days_on_market")
    if days_on_market is not None:
        try:
            days_on_market = int(days_on_market)
        except Exception:
            days_on_market = None

    available_date = None
    for field in FIELD_FALLBACKS["available_date"]:
        val = get(field)
        if val is not None:
            try:
                available_date = str(val)[:10]
                break
            except Exception:
                continue

    def first_value(*keys):
        for key in keys:
            val = get(key)
            if val not in (None, "", [], {}):
                return val
        return None

    def to_int(value):
        value = safe_val(value)
        if value in (None, ""):
            return None
        try:
            if isinstance(value, str):
                cleaned = re.sub(r"[^0-9.-]", "", value)
                if not cleaned:
                    return None
                return int(float(cleaned))
            return int(float(value))
        except Exception:
            return None

    def to_float(value):
        value = safe_val(value)
        if value in (None, ""):
            return None
        try:
            if isinstance(value, str):
                cleaned = re.sub(r"[^0-9.-]", "", value)
                if not cleaned:
                    return None
                return float(cleaned)
            return float(value)
        except Exception:
            return None

    def as_text(value):
        if value is None:
            return ""
        if isinstance(value, (list, tuple, set)):
            return " ".join(as_text(v) for v in value)
        if isinstance(value, dict):
            return " ".join(as_text(v) for v in value.values())
        return str(value)

    searchable_parts = [
        as_text(first_value("text", "description", "property_description", "remarks")),
        as_text(first_value("amenities", "features", "tags", "property_details", "details")),
        as_text(first_value("appliances", "utilities", "parking", "heating", "cooling", "laundry")),
    ]
    searchable = " ".join(part for part in searchable_parts if part).lower()

    def extract_terms(candidates):
        found = []
        for label, patterns in candidates:
            if any(pattern in searchable for pattern in patterns):
                found.append(label)
        return found

    appliances = extract_terms([
          ("Refrigerator", ["refrigerator", "fridge"]),
          ("Range / Oven", ["range", "oven", "stove"]),
          ("Dishwasher", ["dishwasher"]),
          ("Microwave", ["microwave"]),
          ("Washer", ["washer", "washing machine"]),
          ("Dryer", ["dryer"]),
          ("Garbage Disposal", ["garbage disposal", "disposal"]),
          ("Ice Maker", ["ice maker"]),
          ("Wine Cooler", ["wine cooler", "wine refrigerator", "wine fridge"]),
          ("Trash Compactor", ["trash compactor"]),
          ("Double Oven", ["double oven"]),
          ("Freezer", ["chest freezer", "standalone freezer"]),
          ("Air Purifier", ["air purifier", "air filtration"]),
      ])

    amenities = extract_terms([
          ("Basement", ["basement", "finished basement", "lower level"]),
          ("Central Air", ["central air", "central a/c", "central ac", "central cooling"]),
          ("Garage", ["garage", "attached garage", "detached garage"]),
          ("Fenced Yard", ["fenced yard", "fenced backyard"]),
          ("Patio", ["patio"]),
          ("Deck", ["deck"]),
          ("Fireplace", ["fireplace"]),
          ("Walk-in Closet", ["walk-in closet", "walk in closet"]),
          ("Hardwood Floors", ["hardwood floor", "hardwood floors"]),
          ("Swimming Pool", ["swimming pool", "community pool", "outdoor pool", "indoor pool"]),
          ("Gym / Fitness Center", ["gym", "fitness center", "workout room", "fitness room", "exercise room"]),
          ("Elevator", ["elevator", "lift"]),
          ("Balcony", ["balcony", "private balcony"]),
          ("In-Unit Laundry", ["in-unit laundry", "in unit laundry", "washer/dryer in unit", "washer dryer in unit", "laundry in unit", "w/d in unit"]),
          ("EV Charging", ["ev charging", "ev charger", "electric vehicle charging", "tesla charger", "level 2 charger"]),
          ("Storage Unit", ["storage unit", "private storage", "storage room", "storage locker"]),
          ("Wheelchair Accessible", ["wheelchair accessible", "handicap accessible", "ada compliant", "ada accessible"]),
          ("Smart Home", ["smart home", "smart thermostat", "nest thermostat", "smart lock", "keyless entry"]),
          ("High-Speed Internet", ["high-speed internet", "fiber internet", "gigabit internet", "internet included", "high speed internet"]),
          ("Cable / Satellite TV", ["cable tv", "cable included", "satellite tv", "cable and internet"]),
          ("Rooftop Access", ["rooftop", "roof deck", "rooftop terrace", "rooftop access"]),
          ("Concierge / Doorman", ["concierge", "doorman", "front desk", "24-hour concierge"]),
          ("Dog Run", ["dog run", "dog park", "pet area", "pet play area"]),
          ("Gated Community", ["gated community", "gated entrance", "gated access", "secure entry"]),
          ("Intercom System", ["intercom", "video intercom", "buzzer"]),
          ("Bike Storage", ["bike storage", "bicycle storage", "bike room"]),
          ("Package Lockers", ["package locker", "amazon locker", "package room"]),
      ])

    utilities_included = extract_terms([
        ("Water", ["water included"]),
        ("Sewer", ["sewer included"]),
        ("Trash", ["trash included", "garbage included"]),
        ("Gas", ["gas included"]),
        ("Electric", ["electric included", "electricity included"]),
        ("Internet", ["internet included", "wifi included", "wi-fi included"]),
    ])

    flooring = extract_terms([
        ("Hardwood", ["hardwood"]),
        ("Carpet", ["carpet"]),
        ("Tile", ["tile"]),
        ("Vinyl", ["vinyl"]),
        ("Laminate", ["laminate"]),
    ])

    lease_terms = []
    lease_text = as_text(first_value("lease_terms", "lease_term", "terms"))
    if lease_text:
        lease_terms.append(lease_text)
    month_match = re.search(r"(\d{1,2})\s*[- ]?month", searchable)
    minimum_lease_months = to_int(first_value("minimum_lease_months", "min_lease_months", "lease_months"))
    if month_match and not minimum_lease_months:
        minimum_lease_months = int(month_match.group(1))
    if month_match and not lease_terms:
        lease_terms.append(f"{month_match.group(1)} months")

    garage_spaces = to_int(first_value("parking_garage", "garage_spaces", "garage_space", "garage"))
    if garage_spaces and not parking:
        parking = f"{garage_spaces} garage space{'s' if garage_spaces != 1 else ''}"

    full_baths = to_float(first_value("full_baths", "baths_full", "bathrooms_full"))
    half_baths = to_int(first_value("half_baths", "baths_half", "bathrooms_half"))
    source_baths = to_float(first_value("baths", "bathrooms"))
    if full_baths is None and source_baths is not None:
        full_baths = int(source_baths)
    total_bathrooms = source_baths if source_baths is not None else ((full_baths or 0) + ((half_baths or 0) * 0.5))
    if total_bathrooms == 0:
        total_bathrooms = None

    pet_types_allowed = []
    if dogs:
        pet_types_allowed.append("Dogs")
    if cats:
        pet_types_allowed.append("Cats")
    if not pet_types_allowed:
        if "dogs allowed" in searchable or "dog friendly" in searchable:
            pet_types_allowed.append("Dogs")
        if "cats allowed" in searchable or "cat friendly" in searchable:
            pet_types_allowed.append("Cats")
    if "no pets" in searchable or "pets not allowed" in searchable:
        pets_allowed = False
        pet_types_allowed = []
    elif pet_types_allowed:
        pets_allowed = True

    smoking_allowed = None
    if "no smoking" in searchable or "smoke-free" in searchable or "smoke free" in searchable:
        smoking_allowed = False
    elif "smoking allowed" in searchable:
        smoking_allowed = True

    has_basement = any(term in searchable for term in ["basement", "finished basement", "lower level"])
    has_central_air = any(term in searchable for term in ["central air", "central a/c", "central ac", "central cooling"])
    cooling_type = first_value("cooling", "cooling_type", "cooling_system")
    if not cooling_type and has_central_air:
        cooling_type = "Central Air"
    if not cooling_type:
        if "window ac" in searchable or "window unit" in searchable or "window air conditioner" in searchable:
            cooling_type = "Window Units"
        elif "mini split" in searchable or "mini-split" in searchable or "ductless" in searchable:
            cooling_type = "Mini-Split"
        elif "no ac" in searchable or "no air conditioning" in searchable or "no cooling" in searchable:
            cooling_type = "None"

    heating_type = first_value("heating", "heating_type", "heating_system")
    if not heating_type:
        if "forced air" in searchable or "forced-air" in searchable:
            heating_type = "Forced Air"
        elif "radiant heat" in searchable or "radiant floor" in searchable or "radiant heating" in searchable:
            heating_type = "Radiant"
        elif "baseboard heat" in searchable or "electric baseboard" in searchable:
            heating_type = "Baseboard"
        elif "heat pump" in searchable:
            heating_type = "Heat Pump"
        elif "gas heat" in searchable or "natural gas heat" in searchable:
            heating_type = "Gas"
        elif "electric heat" in searchable:
            heating_type = "Electric"
        elif "boiler" in searchable:
            heating_type = "Boiler"

    laundry_type = first_value("laundry", "laundry_type")
    if not laundry_type:
        if "in-unit laundry" in searchable or "in unit laundry" in searchable or "washer dryer" in searchable or "washer/dryer" in searchable:
            laundry_type = "In-unit"
        elif "laundry hookups" in searchable or "washer dryer hookup" in searchable or "w/d hookup" in searchable:
            laundry_type = "Hookups"
        elif "shared laundry" in searchable or "laundry room" in searchable or "coin laundry" in searchable or "on-site laundry" in searchable:
            laundry_type = "Shared"
        elif "no laundry" in searchable:
            laundry_type = "None"

    inferred_features = []
    for label, value in [
        ("Basement", has_basement),
        ("Central Air", has_central_air),
        ("Garage Spaces", garage_spaces),
        ("Appliances", appliances),
        ("Utilities Included", utilities_included),
        ("Flooring", flooring),
        ("Laundry Type", laundry_type),
    ]:
        if value:
            inferred_features.append(label)

    _pre_score_prop = {
        "address":       get("street"),
        "city":          get("city"),
        "state":         get("state"),
        "zip":           str(get("zip_code")) if get("zip_code") is not None else None,
        "monthly_rent":  to_int(first_value(*FIELD_FALLBACKS["monthly_rent"])),
        "bedrooms":      int(get("beds")) if get("beds") is not None else None,
        "bathrooms":     total_bathrooms,
        "description":   first_value(*FIELD_FALLBACKS["description"]),
        "property_type": get("style"),
        "available_date":available_date,
        "amenities":     json.dumps(amenities),
        "appliances":    json.dumps(appliances),
    }
    data_quality_score, missing_fields = _calculate_weighted_quality(_pre_score_prop, image_urls)

    # PIPE-3 FIX: source is passed in at scrape() call time and injected here
    # so each property correctly reflects its actual scrape source (zillow/realtor/redfin).
    # The _source key is set by scrape() after normalize_row() returns.
    return {
        "source": row.get("_source", "realtor"),
        "source_url": get("property_url"),
        "source_listing_id": str(get("mls_id")) if get("mls_id") is not None else str(get("listing_id")) if get("listing_id") is not None else None,
        "status": "scraped",
        "title": first_value("title", "property_name"),
        "address": get("street"),
        "city": get("city"),
        "state": get("state"),
        "zip": str(get("zip_code")) if get("zip_code") is not None else None,
        "county": get("county"),
        "lat": get("latitude"),
        "lng": get("longitude"),
        "bedrooms": int(get("beds")) if get("beds") is not None else None,
        "bathrooms": full_baths,
        "half_bathrooms": half_baths,
        "total_bathrooms": total_bathrooms,
        "square_footage": int(get("sqft")) if get("sqft") is not None else None,
        "lot_size_sqft": int(get("lot_sqft")) if get("lot_sqft") is not None else None,
        "monthly_rent": to_int(first_value(*FIELD_FALLBACKS["monthly_rent"])),
        "property_type": get("style"),
        "year_built": int(get("year_built")) if get("year_built") is not None else None,
        "floors": to_int(first_value("floors", "stories")),
        "unit_number": first_value("unit", "unit_number"),
        "total_units": to_int(first_value("total_units", "units")),
        "description": first_value(*FIELD_FALLBACKS["description"]),
        "available_date": available_date,
        "virtual_tour_url": first_value("virtual_tour_url", "virtual_tour", "matterport_url"),
        "pets_allowed": pets_allowed,
        "pet_types_allowed": json.dumps(pet_types_allowed),
        "pet_weight_limit": to_int(first_value("pet_weight_limit", "pets_weight_limit")),
        "pet_details": first_value("pet_details", "pet_policy"),
        "smoking_allowed": smoking_allowed,
        "parking": parking,
        "garage_spaces": garage_spaces,
        "security_deposit": to_int(first_value(*FIELD_FALLBACKS["security_deposit"])),
        "last_months_rent": to_int(first_value("last_months_rent", "last_month_rent")),
        "application_fee": to_int(first_value("application_fee", "app_fee")),
        "pet_deposit": to_int(first_value("pet_deposit")),
        "admin_fee": to_int(first_value("admin_fee", "move_in_fee")),
        "move_in_special": first_value("move_in_special", "specials"),
        "lease_terms": json.dumps(lease_terms),
        "minimum_lease_months": minimum_lease_months,
        "parking_fee": to_int(first_value("parking_fee")),
        "amenities": json.dumps(amenities),
        "appliances": json.dumps(appliances),
        "utilities_included": json.dumps(utilities_included),
        "flooring": json.dumps(flooring),
        "heating_type": heating_type,
        "cooling_type": cooling_type,
        "laundry_type": laundry_type,
        "has_basement": has_basement,
        "has_central_air": has_central_air,
        "original_image_urls": json.dumps(image_urls),
        "local_image_paths": "[]",
        "original_data": json.dumps(row_serializable),
        "edited_fields": "[]",
        "data_quality_score": data_quality_score,
        "missing_fields": json.dumps(missing_fields),
        "inferred_features": json.dumps(inferred_features),
        "scraped_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
        "_list_date": list_date,
        "_days_on_market": days_on_market,
    }


def scrape(
    location: str,
    source: str = "realtor",
    listing_type: Optional[str] = "for_rent",
    property_type: Optional[List[str]] = None,
    min_price: Optional[int] = None,
    max_price: Optional[int] = None,
    beds_min: Optional[int] = None,
    beds_max: Optional[int] = None,
    baths_min: Optional[float] = None,
    baths_max: Optional[float] = None,
    sqft_min: Optional[int] = None,
    sqft_max: Optional[int] = None,
    lot_sqft_min: Optional[int] = None,
    lot_sqft_max: Optional[int] = None,
    year_built_min: Optional[int] = None,
    year_built_max: Optional[int] = None,
    past_days: Optional[int] = None,
    past_hours: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    radius: Optional[float] = None,
    limit: Optional[int] = 200,
    mls_only: bool = False,
    foreclosure: Optional[bool] = None,
    exclude_pending: bool = False,
    sort_by: Optional[str] = None,
    sort_direction: str = "desc",
):
    source = (source or "realtor").lower()

    if source in CUSTOM_SOURCES:
        return _scrape_custom(
            source=source,
            location=location,
            listing_type=listing_type,
            min_price=min_price,
            max_price=max_price,
            beds_min=beds_min,
            beds_max=beds_max,
            limit=limit or 200,
        )

    return _scrape_homeharvest(
        source=source,
        location=location,
        listing_type=listing_type,
        property_type=property_type,
        min_price=min_price,
        max_price=max_price,
        beds_min=beds_min,
        beds_max=beds_max,
        baths_min=baths_min,
        baths_max=baths_max,
        sqft_min=sqft_min,
        sqft_max=sqft_max,
        lot_sqft_min=lot_sqft_min,
        lot_sqft_max=lot_sqft_max,
        year_built_min=year_built_min,
        year_built_max=year_built_max,
        past_days=past_days,
        past_hours=past_hours,
        date_from=date_from,
        date_to=date_to,
        radius=radius,
        limit=limit,
        mls_only=mls_only,
        foreclosure=foreclosure,
        exclude_pending=exclude_pending,
        sort_by=sort_by,
        sort_direction=sort_direction,
    )


def _scrape_homeharvest(
    source: str = "realtor",
    location: str = "",
    listing_type: Optional[str] = "for_rent",
    property_type: Optional[List[str]] = None,
    min_price: Optional[int] = None,
    max_price: Optional[int] = None,
    beds_min: Optional[int] = None,
    beds_max: Optional[int] = None,
    baths_min: Optional[float] = None,
    baths_max: Optional[float] = None,
    sqft_min: Optional[int] = None,
    sqft_max: Optional[int] = None,
    lot_sqft_min: Optional[int] = None,
    lot_sqft_max: Optional[int] = None,
    year_built_min: Optional[int] = None,
    year_built_max: Optional[int] = None,
    past_days: Optional[int] = None,
    past_hours: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    radius: Optional[float] = None,
    limit: Optional[int] = 200,
    mls_only: bool = False,
    foreclosure: Optional[bool] = None,
    exclude_pending: bool = False,
    sort_by: Optional[str] = None,
    sort_direction: str = "desc",
) -> list:
    kwargs = dict(
        location=location,
        listing_type=listing_type,
        price_min=min_price,
        price_max=max_price,
        beds_min=beds_min,
        beds_max=beds_max,
        baths_min=baths_min,
        baths_max=baths_max,
        sqft_min=sqft_min,
        sqft_max=sqft_max,
        lot_sqft_min=lot_sqft_min,
        lot_sqft_max=lot_sqft_max,
        year_built_min=year_built_min,
        year_built_max=year_built_max,
        past_days=past_days,
        past_hours=past_hours,
        date_from=date_from,
        date_to=date_to,
        radius=radius,
        limit=limit,
        mls_only=mls_only,
        foreclosure=foreclosure,
        exclude_pending=exclude_pending,
        sort_by=sort_by,
        sort_direction=sort_direction,
    )

    if property_type:
        kwargs["property_type"] = property_type

    kwargs = {k: v for k, v in kwargs.items() if v is not None and v is not False}
    kwargs["location"] = location
    kwargs["listing_type"] = listing_type
    kwargs["sort_direction"] = sort_direction
    kwargs["exclude_pending"] = exclude_pending
    kwargs["mls_only"] = mls_only
    if limit:
        kwargs["limit"] = limit

    df = scrape_property(**kwargs)

    if df is None or len(df) == 0:
        return []

    results = []
    for _, row in df.iterrows():
        row_dict = row.to_dict()
        normalized = normalize_row(row_dict)
        results.append(normalized)

    return results


def scrape_all_sources(
    location: str,
    listing_type: Optional[str] = "for_rent",
    property_type: Optional[List[str]] = None,
    min_price: Optional[int] = None,
    max_price: Optional[int] = None,
    beds_min: Optional[int] = None,
    beds_max: Optional[int] = None,
    baths_min: Optional[float] = None,
    baths_max: Optional[float] = None,
    sqft_min: Optional[int] = None,
    sqft_max: Optional[int] = None,
    lot_sqft_min: Optional[int] = None,
    lot_sqft_max: Optional[int] = None,
    year_built_min: Optional[int] = None,
    year_built_max: Optional[int] = None,
    past_days: Optional[int] = None,
    past_hours: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    radius: Optional[float] = None,
    limit: int = 200,
    mls_only: bool = False,
    foreclosure: Optional[bool] = None,
    exclude_pending: bool = False,
    sort_by: Optional[str] = None,
    sort_direction: str = "desc",
) -> tuple[list, dict]:
    """Scrape all sources simultaneously using a thread pool. Returns (results, source_counts)."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    sources = list(ALL_SOURCES)
    per_source_limit = max(30, limit // len(sources))

    common_kwargs = dict(
        location=location,
        listing_type=listing_type,
        min_price=min_price,
        max_price=max_price,
        beds_min=beds_min,
        beds_max=beds_max,
        limit=per_source_limit,
    )

    def _run_source(src: str):
        try:
            if src in HOMEHARVEST_SOURCES:
                return src, _scrape_homeharvest(
                    source=src,
                    property_type=property_type,
                    baths_min=baths_min,
                    baths_max=baths_max,
                    sqft_min=sqft_min,
                    sqft_max=sqft_max,
                    lot_sqft_min=lot_sqft_min,
                    lot_sqft_max=lot_sqft_max,
                    year_built_min=year_built_min,
                    year_built_max=year_built_max,
                    past_days=past_days,
                    past_hours=past_hours,
                    date_from=date_from,
                    date_to=date_to,
                    radius=radius,
                    mls_only=mls_only,
                    foreclosure=foreclosure,
                    exclude_pending=exclude_pending,
                    sort_by=sort_by,
                    sort_direction=sort_direction,
                    **common_kwargs,
                )
            else:
                return src, _scrape_custom(source=src, **common_kwargs)
        except Exception as e:
            logger.warning("Multi-source: '%s' failed: %s", src, e)
            return src, []

    all_results = []
    source_counts = {}

    with ThreadPoolExecutor(max_workers=len(sources)) as executor:
        futures = {executor.submit(_run_source, src): src for src in sources}
        for future in as_completed(futures, timeout=60):
            src = futures[future]
            try:
                src_name, src_results = future.result(timeout=5)
                source_counts[src_name] = len(src_results)
                for r in src_results:
                    r.setdefault("source", src_name)
                all_results.extend(src_results)
                logger.info("Multi-source: '%s' returned %d results", src_name, len(src_results))
            except Exception as e:
                logger.warning("Multi-source: future for '%s' failed: %s", src, e)
                source_counts[src] = 0

    seen_ids = set()
    seen_addresses = set()
    unique = []
    for r in all_results:
        lid = r.get("source_listing_id")
        addr = (str(r.get("address") or "") + str(r.get("city") or "")).lower().strip()

        if lid and lid in seen_ids:
            continue
        if not lid and addr and addr in seen_addresses:
            continue

        if lid:
            seen_ids.add(lid)
        if addr:
            seen_addresses.add(addr)
        unique.append(r)

    logger.info("Multi-source: combined %d unique results from %d sources", len(unique), len(source_counts))
    return unique[:limit], source_counts


def _scrape_custom(
    source: str,
    location: str,
    listing_type: Optional[str] = "for_rent",
    min_price: Optional[int] = None,
    max_price: Optional[int] = None,
    beds_min: Optional[int] = None,
    beds_max: Optional[int] = None,
    limit: int = 200,
) -> list:
    """Dispatch to a custom scraper module."""
    try:
        if source == "opendoor":
            from services.scrapers.opendoor_scraper import scrape as _scrape
        elif source == "apartments":
            from services.scrapers.apartments_scraper import scrape as _scrape
        elif source == "craigslist":
            from services.scrapers.craigslist_scraper import scrape as _scrape
        elif source == "hotpads":
            from services.scrapers.hotpads_scraper import scrape as _scrape
        elif source == "invitation_homes":
            from services.scrapers.invitation_homes_scraper import scrape as _scrape
        elif source == "progress_residential":
            from services.scrapers.progress_residential_scraper import scrape as _scrape
        else:
            raise ValueError(f"Unknown custom source: {source}")

        results = _scrape(
            location=location,
            listing_type=listing_type,
            min_price=min_price,
            max_price=max_price,
            beds_min=beds_min,
            beds_max=beds_max,
            limit=limit,
        )

        for r in results:
            r.setdefault("source", source)
            r.setdefault("status", "scraped")
            r.setdefault("local_image_paths", "[]")
            r.setdefault("edited_fields", "[]")
            r.setdefault("original_data", "{}")

        logger.info("Custom scraper '%s' returned %d results for '%s'", source, len(results), location)
        return results

    except Exception as e:
        logger.error("Custom scraper '%s' failed for '%s': %s", source, location, e)
        raise


def _inject_source(results: list, source: str) -> list:
    """PIPE-3 FIX: stamp the real source onto each normalized row."""
    for r in results:
        r["source"] = source
    return results
