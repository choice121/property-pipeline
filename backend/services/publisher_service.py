import json
import logging
import os
import re
import uuid
from urllib.parse import urlparse

from imagekitio import ImageKit
from supabase import create_client

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PROPERTY_TYPE_MAP = {
    "SINGLE_FAMILY": "house",
    "SINGLE_FAMILY_HOME": "house",
    "HOUSE": "house",
    "APARTMENT": "apartment",
    "APARTMENTS": "apartment",
    "APARTMENT_COMMUNITY": "apartment",
    "CONDO": "condo",
    "CONDOS": "condo",
    "CONDO_TOWNHOME": "townhouse",
    "TOWNHOMES": "townhouse",
    "TOWNHOME": "townhouse",
    "TOWNHOUSE": "townhouse",
    "ROW_HOUSE": "townhouse",
    "DUPLEX": "duplex",
    "HALF_DUPLEX": "duplex",
    "TRIPLEX": "triplex",
    "MULTI_FAMILY": "multi_family",
    "MULTIFAMILY": "multi_family",
    "MOBILE": "mobile_home",
    "MOBILE_HOME": "mobile_home",
    "MANUFACTURED": "mobile_home",
    "STUDIO": "studio",
    "ROOM": "room",
    "LOFT": "loft",
    "BASEMENT": "basement",
    "LAND": "land",
    "LOT": "land",
    "FARM": "farm",
    "COMMERCIAL": "commercial",
}

PROHIBITED_DESCRIPTION_BLOCKS = [
    re.compile(
        r"(?im)^\s*(?:requirements\s*&\s*qualifications|qualifications\s*&\s*requirements|"
        r"rental\s+requirements)\s*:?.*?(?=\n\s*\n|\Z)"
    ),
]

PROHIBITED_DESCRIPTION_SENTENCES = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bsecurity\s+deposit\b",
        r"\blease\s+(?:term|duration|length)\b|\b\d+[- ]month\s+lease\b",
        r"\bavailab(?:le|ility)\b|\bmove[- ]in\b",
        r"\bsmok(?:e|ing)\b",
        r"\b(?:pets?|animals?|cats?|dogs?)\b",
        r"\b(?:schedule|book|request|arrange)\s+(?:a\s+)?(?:tour|showing|viewing)\b|"
        r"\b(?:tour|showing|viewing)\s+(?:this|the|today|now)\b|\bopen\s+house\b",
        r"\b(?:agent|broker|realtor|property\s+manager|landlord)\b.*\b(?:call|text|contact|email)\b|"
        r"\b(?:call|text|contact|email)\b.*\b(?:agent|broker|realtor|property\s+manager|landlord)\b|"
        r"\b(?:agent|broker|realtor)\b",
        r"https?://|www\.",
        r"\b(?:zillow|realtor\.com|apartments\.com|turbotenant|rentcafe|rentspree|appfolio)\b",
        r"\bMLS\s*#?\s*\d+\b|\blisted\s+by\b|\bcourtesy\s+of\b",
        r"\b(?:requirements\s*&\s*qualifications|qualifications?\s*&\s*requirements|"
        r"rental\s+requirements|lease\s+requirements|credit\s+score|income\s+must\s+exceed|"
        r"three\s+times\s+the\s+monthly\s+rent|no\s+evictions|no\s+criminal\s+history|"
        r"application\s+pending|waiting\s+list\s+options?)\b",
        r"\b(?:stock\s+images?|marketing\s+purposes|illustrative\s+purposes|virtual\s+furniture\s+staging)\b",
        r"\b(?:scams?|fraud|scammers?)\b|\b(?:beware|protect\s+yourself)\b",
        r"\b(?:craigslist|facebook\s+marketplace|tiktok|offerup)\b|\b(?:do\s+not|don['']t|never)\s+"
        r"(?:advertise|post|list)\s+on\b",
        r"\b(?:cash\s*apps?|cashapp|zelle|paypal|venmo|apple\s*pay|wire\s*transfers?|"
        r"western\s+union|money\s+orders?)\b",
        r"\bapplication\s+fee\b|\b(?:free|waived|complimentary)\s+application\b",
        r"(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}|"
        r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}",
    )
]

APPLICATION_NOTE = (
    "Application Fee: $50. Submit your rental application today at Choice Properties."
)
EXPLICIT_NULL_FIELDS = {
    "original_description", "showing_instructions", "move_in_special",
    "move_in_total", "available_date", "lease_terms", "minimum_lease_months",
    "pet_deposit", "pets_allowed", "pet_types_allowed", "pet_weight_limit",
    "pet_details", "smoking_allowed", "virtual_tour_url",
}


def _standard_title(prop) -> str:
    address = str(getattr(prop, "address", None) or "").strip()
    city = str(getattr(prop, "city", None) or "").strip()
    state = str(getattr(prop, "state", None) or "").strip()
    zip_code = str(getattr(prop, "zip", None) or "").strip()
    location = ", ".join(part for part in (address, city) if part)
    if state:
        location = f"{location}, {state}" if location else state
    if zip_code:
        location = f"{location} {zip_code}".strip()
    return location


def _normalize_property_type(value, total_units=None) -> str:
    raw_type = re.sub(r"[\s/-]+", "_", str(value or "").strip().upper())
    normalized = PROPERTY_TYPE_MAP.get(raw_type)
    if raw_type == "DUPLEX_TRIPLEX":
        try:
            normalized = "triplex" if int(total_units or 0) >= 3 else "duplex"
        except (TypeError, ValueError):
            normalized = "duplex"
    return normalized or "other"


def _is_true(value) -> bool:
    return value is True or (isinstance(value, str) and value.strip().lower() in {"true", "1", "yes"})


def _metadata_text(value, limit: int) -> str | None:
    return value.strip()[:limit] if isinstance(value, str) and value.strip() else None

# Amenity slug → human-readable label (raw homeharvest slugs arrive as-is)
_AMENITY_SLUG_MAP = {
    "fenced_yard": "Fenced Yard",
    "open_concept_living": "Open Concept Living",
    "floor_plan": "Floor Plan Available",
    "den": "Den",
    "hardwood_floors": "Hardwood Floors",
    "granite_countertops": "Granite Countertops",
    "stainless_appliances": "Stainless Steel Appliances",
    "walk_in_closet": "Walk-In Closet",
    "walk_in_closets": "Walk-In Closets",
    "in_unit_laundry": "In-Unit Laundry",
    "washer_dryer": "Washer/Dryer Included",
    "washer_dryer_hookup": "Washer/Dryer Hookup",
    "dishwasher": "Dishwasher",
    "garbage_disposal": "Garbage Disposal",
    "microwave": "Microwave",
    "refrigerator": "Refrigerator",
    "air_conditioning": "Air Conditioning",
    "ceiling_fans": "Ceiling Fans",
    "fireplace": "Fireplace",
    "patio": "Patio",
    "balcony": "Balcony",
    "deck": "Deck",
    "pool": "Swimming Pool",
    "garage": "Garage",
    "carport": "Carport",
    "storage": "Storage",
    "elevator": "Elevator",
    "gym": "Gym / Fitness Center",
    "fitness_center": "Fitness Center",
    "clubhouse": "Clubhouse",
    "gated_community": "Gated Community",
    "security_system": "Security System",
    "smart_home": "Smart Home",
    "solar_panels": "Solar Panels",
    "ev_charging": "EV Charging",
    "wheelchair_accessible": "Wheelchair Accessible",
    "new_construction": "New Construction",
    "recently_renovated": "Recently Renovated",
    "furnished": "Furnished",
    "short_term_lease": "Short-Term Lease Available",
}


def _humanize_amenities(items: list) -> list:
    """Convert any raw homeharvest slugs (fenced_yard) to clean labels (Fenced Yard).

    Items that are already human-readable labels pass through unchanged.
    """
    out = []
    for item in items:
        if not isinstance(item, str):
            continue
        mapped = _AMENITY_SLUG_MAP.get(item.lower().strip())
        if mapped:
            out.append(mapped)
        else:
            # Already a label — capitalise first letter, replace underscores
            out.append(item.replace("_", " ").strip().title() if item == item.lower() else item.strip())
    # Deduplicate while preserving order
    seen = set()
    result = []
    for a in out:
        if a not in seen:
            seen.add(a)
            result.append(a)
    return result


def _clean_description(text: str | None) -> str | None:
    if not isinstance(text, str) or not text.strip():
        return APPLICATION_NOTE

    for pattern in PROHIBITED_DESCRIPTION_BLOCKS:
        text = pattern.sub("", text)

    sentences = re.split(r"(?<=[.!?])\s+|\n+", text)
    safe_sentences = [
        sentence.strip()
        for sentence in sentences
        if sentence.strip()
        and not any(pattern.search(sentence) for pattern in PROHIBITED_DESCRIPTION_SENTENCES)
    ]
    source_text = re.sub(r"[ \t]{2,}", " ", " ".join(safe_sentences)).strip()
    if not source_text:
        return APPLICATION_NOTE
    return f"{source_text} {APPLICATION_NOTE}"


def _parse_object(value) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


def _parse_photo_urls(value) -> list[dict]:
    try:
        parsed = json.loads(value) if isinstance(value, str) else value
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(parsed, list):
        return []

    photos = []
    for item in parsed[:40]:
        if isinstance(item, str):
            photo = {"url": item}
        elif isinstance(item, dict):
            photo = {
                "url": item.get("url"),
                "file_id": item.get("file_id") or item.get("fileId"),
                "width": item.get("width"),
                "height": item.get("height"),
            }
        else:
            continue
        parsed_url = urlparse(str(photo.get("url") or ""))
        if parsed_url.scheme != "https" or not parsed_url.netloc:
            continue
        photos.append(photo)
    return photos


def _positive_number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def _build_unit_options(original_data: dict) -> list[dict]:
    raw_options = original_data.get("unit_options")
    if not isinstance(raw_options, list):
        return []

    options = []
    for item in raw_options[:100]:
        if not isinstance(item, dict):
            continue
        unit = {}
        unit_number = item.get("unit_number") or item.get("unit")
        floor_plan_name = item.get("floor_plan_name") or item.get("name")
        if isinstance(unit_number, str) and unit_number.strip():
            unit["unit_number"] = unit_number.strip()[:80]
        if isinstance(floor_plan_name, str) and floor_plan_name.strip():
            unit["floor_plan_name"] = floor_plan_name.strip()[:120]
        for target, sources in {
            "unit_floor": ("unit_floor", "floor"),
            "bedrooms": ("bedrooms", "beds"),
            "bathrooms": ("bathrooms", "baths"),
            "square_footage": ("square_footage", "sqft"),
            "monthly_rent": ("monthly_rent", "starting_rent", "rent"),
        }.items():
            value = next((item.get(key) for key in sources if item.get(key) is not None), None)
            parsed = _positive_number(value)
            if parsed is not None:
                unit[target] = int(parsed) if parsed.is_integer() else parsed
        rent_basis = item.get("rent_basis")
        if isinstance(rent_basis, str) and rent_basis.strip():
            unit["rent_basis"] = rent_basis.strip()[:80]
        if unit:
            options.append(unit)
    return options


def _build_floor_plan_media(original_data: dict) -> list[dict]:
    raw_media = original_data.get("media")
    if not isinstance(raw_media, list):
        return []

    media = []
    seen_urls = set()
    for item in raw_media[:100]:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind") or "").strip().lower().replace("-", "_")
        url = str(item.get("url") or "").strip()
        parsed_url = urlparse(url)
        if kind not in {"floor_plan", "floorplan"}:
            continue
        if parsed_url.scheme != "https" or not parsed_url.netloc or url in seen_urls:
            continue
        seen_urls.add(url)
        entry = {
            "kind": "floor_plan",
            "url": url,
            "display_order": len(media) + 1,
        }
        title = item.get("title") or item.get("floor_plan_name")
        floor = item.get("floor_label") or item.get("unit_floor")
        if isinstance(title, str) and title.strip():
            entry["title"] = title.strip()[:120]
        if isinstance(floor, (str, int, float)) and str(floor).strip():
            entry["floor_label"] = str(floor).strip()[:60]
        entry["provider"] = parsed_url.hostname
        media.append(entry)
    return media


def _get_imagekit():
    return ImageKit(private_key=os.environ["IMAGEKIT_PRIVATE_KEY"])


def _get_supabase():
    url = os.environ["SUPABASE_URL"].rstrip("/")
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"].strip()
    return create_client(url, key)


_cached_landlord_id: str | None = None

def _get_landlord_id() -> str | None:
    global _cached_landlord_id

    env_id = os.environ.get("CHOICE_LANDLORD_ID", "").strip()
    if env_id:
        return env_id

    if _cached_landlord_id:
        return _cached_landlord_id

    try:
        client = _get_supabase()
        result = (
            client.table("landlords")
            .select("id, contact_name, business_name, email")
            .execute()
        )
        rows = result.data or []
        for row in rows:
            name = (row.get("business_name") or row.get("contact_name") or "").lower()
            email = (row.get("email") or "").lower()
            if "choice" in name or "choice" in email:
                _cached_landlord_id = row["id"]
                logger.info("Auto-resolved landlord ID from Supabase: %s (%s)", row["id"], name or email)
                return _cached_landlord_id
        if rows:
            _cached_landlord_id = rows[0]["id"]
            logger.info("No 'Choice' landlord found — using first landlord: %s", _cached_landlord_id)
            return _cached_landlord_id
    except Exception as e:
        logger.warning("Could not auto-resolve landlord ID from Supabase: %s", e)

    logger.warning("No landlord ID found. Published listing will have landlord_id=null.")
    return None


def _upload_images_to_imagekit(property_id: str, local_image_paths: list) -> list:
    MAX_PHOTOS = 40
    paths_to_upload = local_image_paths[:MAX_PHOTOS]
    if len(local_image_paths) > MAX_PHOTOS:
        logger.info(
            "Capping images at %d (had %d) for property %s",
            MAX_PHOTOS, len(local_image_paths), property_id
        )

    ik = _get_imagekit()
    results = []

    for rel_path in paths_to_upload:
        abs_path = os.path.join(BASE_DIR, rel_path.lstrip("/"))
        if not os.path.isfile(abs_path):
            logger.warning("Image file not found, skipping: %s", abs_path)
            continue

        file_name = os.path.basename(abs_path)
        with open(abs_path, "rb") as f:
            upload_result = ik.files.upload(
                file=f,
                file_name=file_name,
                folder=f"/properties/{property_id}",
            )

        results.append({
            "url":     upload_result.url,
            "file_id": upload_result.file_id,
        })
        logger.info("Uploaded image to ImageKit: %s -> %s", file_name, upload_result.url)

    return results


def _check_duplicate_in_supabase(client, prop) -> str | None:
    if not prop.address or not prop.city or not prop.state:
        return None
    try:
        result = (
            client.table("properties")
            .select("id")
            .eq("address", prop.address)
            .eq("city", prop.city)
            .eq("state", prop.state)
            .limit(1)
            .execute()
        )
        if result.data:
            return result.data[0]["id"]
    except Exception as e:
        logger.warning("Duplicate check query failed: %s", e)
    return None


def _build_amenities_list(prop, parse_json_fn) -> list:
    amenities = parse_json_fn(prop.amenities)
    if prop.has_basement and "Basement" not in amenities:
        amenities.append("Basement")
    if prop.has_central_air and "Central Air" not in amenities:
        amenities.append("Central Air")
    return amenities


def _build_supabase_record(
    prop,
    image_results: list,
    listing_status: str = "private_placement",
) -> dict:
    def parse_json(val):
        if not val:
            return []
        if isinstance(val, list):
            return val
        try:
            parsed = json.loads(val)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            pass
        if isinstance(val, str):
            return [item.strip() for item in val.split(",") if item.strip()]
        return []

    poster_id = getattr(prop, "poster_landlord_id", None)
    landlord_id = poster_id if poster_id else _get_landlord_id()
    if poster_id:
        logger.info("Using poster_landlord_id %s for property %s", poster_id, getattr(prop, "id", "?"))

    title = _standard_title(prop)
    choice_id = "prop-" + uuid.uuid4().hex[:8]

    normalized_type = _normalize_property_type(prop.property_type, prop.total_units)

    original_data = _parse_object(getattr(prop, "original_data", None))
    unit_options = _build_unit_options(original_data)
    source_description = _clean_description(prop.description)
    source_original_description = _clean_description(
        getattr(prop, "original_description", None) or prop.description
    )
    is_multi_unit = _is_true(original_data.get("is_multi_unit")) or bool(
        (prop.total_units or 0) > 1
        or unit_options
    )
    building_name = _metadata_text(original_data.get("building_name"), 160)
    price_range = _metadata_text(original_data.get("price_range"), 120)
    unit_floor = _positive_number(original_data.get("unit_floor"))
    if unit_floor is not None and unit_floor.is_integer():
        unit_floor = int(unit_floor)

    # Fix 2: humanize amenity slugs before sending to Supabase
    raw_amenities = _build_amenities_list(prop, parse_json)
    clean_amenities = _humanize_amenities(raw_amenities)

    # Nearby schools — stored as JSON string in pipeline, send as list to Supabase
    nearby_schools = []
    try:
        nearby_schools = json.loads(prop.nearby_schools or "[]") if hasattr(prop, "nearby_schools") else []
        if not isinstance(nearby_schools, list):
            nearby_schools = []
    except Exception:
        nearby_schools = []

    record = {
        "id":                   choice_id,
        "status":               listing_status,
        "title":                title,
        "description":          source_description,
        "original_description": source_original_description,
        "showing_instructions": None,
        "address":              prop.address,
        "city":                 prop.city,
        "state":                prop.state,
        "zip":                  prop.zip,
        "county":               prop.county,
        "lat":                  prop.lat,
        "lng":                  prop.lng,
        "neighborhood":         prop.neighborhood,
        "property_type":        normalized_type,
        "year_built":           prop.year_built,
        "floors":               prop.floors,
        "unit_number":          prop.unit_number,
        "total_units":          prop.total_units,
        "building_name":        building_name,
        "is_multi_unit":        is_multi_unit,
        "price_range":          price_range,
        "unit_options":         unit_options,
        "unit_floor":           unit_floor,
        "bedrooms":             prop.bedrooms,
        "bathrooms":            prop.bathrooms,
        "half_bathrooms":       prop.half_bathrooms,
        "total_bathrooms":      prop.total_bathrooms,
        "square_footage":       prop.square_footage,
        "lot_size_sqft":        prop.lot_size_sqft,
        "garage_spaces":        prop.garage_spaces,
        "has_basement":         prop.has_basement,
        "has_central_air":      prop.has_central_air,
        "monthly_rent":         prop.monthly_rent,
        "security_deposit":     prop.monthly_rent,
        "last_months_rent":     prop.last_months_rent,
        "application_fee":      50,
        "pet_deposit":          None,
        "admin_fee":            prop.admin_fee,
        "move_in_special":      None,
        "move_in_total":        None,
        "available_date":       None,
        "lease_terms":          None,
        "minimum_lease_months": None,
        "pets_allowed":         None,
        "pet_types_allowed":    None,
        "pet_weight_limit":     None,
        "pet_details":          None,
        "smoking_allowed":      None,
        "utilities_included":   parse_json(prop.utilities_included),
        "parking":              prop.parking,
        "parking_fee":          prop.parking_fee,
        "amenities":            clean_amenities,   # Fix 2: humanized
        "appliances":           parse_json(prop.appliances),
        "flooring":             parse_json(prop.flooring),
        "heating_type":         prop.heating_type,
        "cooling_type":         prop.cooling_type,
        "laundry_type":         prop.laundry_type,
        "virtual_tour_url":     None,
        # Enriched fields — populated by enrichment_service after scrape
        "flood_zone":           getattr(prop, "flood_zone", None),
        "walk_score":           getattr(prop, "walk_score", None),
        "transit_score":        getattr(prop, "transit_score", None),
        "bike_score":           getattr(prop, "bike_score", None),
        "nearby_schools":       nearby_schools if nearby_schools else None,
        # photo_urls / photo_file_ids removed — photos in property_photos table
        # (migration 20260426000002)
    }

    if landlord_id:
        record["landlord_id"] = landlord_id

    result = {
        key: value
        for key, value in record.items()
        if value is not None or key in EXPLICIT_NULL_FIELDS
    }
    if not result.get("unit_options"):
        result.pop("unit_options", None)
    return result


def refresh_images(prop, repo) -> dict:
    local_paths = []
    try:
        parsed = json.loads(prop.local_image_paths or "[]")
        # Flatten legacy doubly-nested format: [["p1","p2"]] → ["p1","p2"]
        flat = [p for item in parsed for p in (item if isinstance(item, list) else [item])]
        local_paths = [p for p in flat if isinstance(p, str)]
    except Exception:
        pass

    if not local_paths:
        raise ValueError("No local images found. Download images before refreshing.")

    logger.info(
        "Re-uploading %d images to ImageKit for property %s (choice_id=%s)",
        len(local_paths), prop.id, prop.choice_property_id
    )
    imagekit_results = _upload_images_to_imagekit(prop.id, local_paths)

    if not imagekit_results:
        raise RuntimeError("Image upload to ImageKit failed — no images were uploaded successfully.")

    client = _get_supabase()

    # Photos live in property_photos (not on properties columns).
    # Delete the old rows and replace with freshly-uploaded ones.
    client.table("property_photos").delete().eq("property_id", prop.choice_property_id).execute()
    photos_payload = [
        {
            "property_id":   prop.choice_property_id,
            "url":           r["url"],
            "file_id":       r["file_id"],
            "display_order": i,
        }
        for i, r in enumerate(imagekit_results)
    ]
    if photos_payload:
        client.table("property_photos").insert(photos_payload).execute()

    logger.info(
        "Images refreshed for property %s: %d photos now live",
        prop.choice_property_id, len(imagekit_results)
    )
    return {
        "ok":                True,
        "choice_property_id": prop.choice_property_id,
        "photo_count":       len(imagekit_results),
        "message":           f"Gallery updated — {len(imagekit_results)} photos now live on website",
    }


def sync_fields(prop, repo) -> dict:
    if not prop.choice_property_id:
        raise ValueError("Property has not been published yet.")

    client = _get_supabase()

    def parse_json(val):
        if not val:
            return []
        if isinstance(val, list):
            return val
        try:
            parsed = json.loads(val)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            pass
        return []

    normalized_type = _normalize_property_type(prop.property_type, prop.total_units)

    original_data = _parse_object(getattr(prop, "original_data", None))
    unit_options = _build_unit_options(original_data)

    update_payload = {
        "title":                _standard_title(prop),
        "description":          _clean_description(prop.description),
        "original_description": _clean_description(
            getattr(prop, "original_description", None) or prop.description
        ),
        "showing_instructions": None,
        "address":              prop.address,
        "city":                 prop.city,
        "state":                prop.state,
        "zip":                  prop.zip,
        "county":               prop.county,
        "lat":                  prop.lat,
        "lng":                  prop.lng,
        "property_type":        normalized_type,
        "year_built":           prop.year_built,
        "floors":               prop.floors,
        "unit_number":          prop.unit_number,
        "total_units":          prop.total_units,
        "building_name":        _metadata_text(original_data.get("building_name"), 160),
        "is_multi_unit":        _is_true(original_data.get("is_multi_unit")) or (prop.total_units or 0) > 1 or bool(unit_options),
        "price_range":          _metadata_text(original_data.get("price_range"), 120),
        "unit_options":         unit_options,
        "unit_floor":           _positive_number(original_data.get("unit_floor")),
        "bedrooms":             prop.bedrooms,
        "bathrooms":            prop.bathrooms,
        "half_bathrooms":       prop.half_bathrooms,
        "total_bathrooms":      prop.total_bathrooms,
        "square_footage":       prop.square_footage,
        "lot_size_sqft":        prop.lot_size_sqft,
        "garage_spaces":        prop.garage_spaces,
        "has_basement":         prop.has_basement,
        "has_central_air":      prop.has_central_air,
        "monthly_rent":         prop.monthly_rent,
        "security_deposit":     prop.monthly_rent,
        "last_months_rent":     prop.last_months_rent,
        "application_fee":      50,
        "pet_deposit":          None,
        "admin_fee":            prop.admin_fee,
        "available_date":       None,
        "lease_terms":          None,
        "minimum_lease_months": None,
        "pets_allowed":         None,
        "pet_types_allowed":    None,
        "pet_weight_limit":     None,
        "pet_details":          None,
        "smoking_allowed":      None,
        "utilities_included":   parse_json(prop.utilities_included),
        "parking":              prop.parking,
        "parking_fee":          prop.parking_fee,
        "amenities":            _humanize_amenities(_build_amenities_list(prop, parse_json)),
        "appliances":           parse_json(prop.appliances),
        "flooring":             parse_json(prop.flooring),
        "heating_type":         prop.heating_type,
        "cooling_type":         prop.cooling_type,
        "laundry_type":         prop.laundry_type,
        "move_in_special":      None,
        "virtual_tour_url":     None,
        # Enriched fields
        "flood_zone":           getattr(prop, "flood_zone", None),
        "walk_score":           getattr(prop, "walk_score", None),
        "transit_score":        getattr(prop, "transit_score", None),
        "bike_score":           getattr(prop, "bike_score", None),
        "neighborhood":         prop.neighborhood,
    }

    update_payload = {
        key: value
        for key, value in update_payload.items()
        if value is not None or key in EXPLICIT_NULL_FIELDS
    }
    update_payload["security_deposit"] = prop.monthly_rent
    update_payload["application_fee"] = 50
    update_payload["available_date"] = None
    update_payload["lease_terms"] = None
    update_payload["minimum_lease_months"] = None
    update_payload["pets_allowed"] = None
    update_payload["pet_types_allowed"] = None
    update_payload["pet_deposit"] = None
    update_payload["pet_weight_limit"] = None
    update_payload["pet_details"] = None
    update_payload["smoking_allowed"] = None
    update_payload["showing_instructions"] = None
    update_payload["move_in_special"] = None
    update_payload["virtual_tour_url"] = None

    result = (
        client.table("properties")
        .update(update_payload)
        .eq("id", prop.choice_property_id)
        .execute()
    )

    if not result.data:
        raise RuntimeError(
            "Supabase update returned no data. Record may not exist or permissions insufficient."
        )

    logger.info("Fields synced for property %s → %s", prop.id, prop.choice_property_id)
    return {
        "ok":                True,
        "choice_property_id": prop.choice_property_id,
        "message":           "Property fields synced to live site",
    }


def set_listing_status(prop, status: str, repo) -> dict:
    valid = {"active", "private_placement", "rented", "archived", "inactive"}
    if status not in valid:
        raise ValueError(f"Invalid status '{status}'. Must be one of: {', '.join(sorted(valid))}")
    if not prop.choice_property_id:
        raise ValueError("Property has not been published yet.")

    client = _get_supabase()
    result = (
        client.table("properties")
        .update({"status": status})
        .eq("id", prop.choice_property_id)
        .execute()
    )
    if not result.data:
        raise RuntimeError("Failed to update listing status on live site.")

    if status in ("rented", "archived"):
        prop.status = status
        repo.save(prop)

    logger.info("Listing status for %s set to '%s' on live site", prop.choice_property_id, status)
    return {
        "ok":                True,
        "choice_property_id": prop.choice_property_id,
        "listing_status":    status,
        "message":           f"Listing marked as '{status}' on live site",
    }


def _local_image_paths(prop) -> list[str]:
    try:
        parsed = json.loads(prop.local_image_paths or "[]")
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(parsed, list):
        return []
    flat = [path for item in parsed for path in (item if isinstance(item, list) else [item])]
    return [path for path in flat if isinstance(path, str) and path.strip()]


BLOCKING_RULES = [
    ("address", lambda p: bool(p.address), "Address is required"),
    ("city_state", lambda p: bool(p.city and p.state), "City and state are required"),
    ("zip", lambda p: bool(p.zip), "ZIP code is required"),
    ("rent", lambda p: p.monthly_rent is not None and p.monthly_rent > 0, "Monthly rent must be set"),
    ("bedrooms", lambda p: p.bedrooms is not None, "Bedroom count is required"),
    ("bathrooms", lambda p: p.bathrooms is not None, "Bathroom count is required"),
    (
        "photos",
        lambda p: bool(_parse_photo_urls(p.original_image_urls) or _local_image_paths(p)),
        "At least one authentic source photo is required",
    ),
    (
        "quality",
        lambda p: (p.data_quality_score or 0) >= 50,
        "Quality score is below 50 — too many critical fields missing",
    ),
]


def pre_publish_checks(prop) -> list[str]:
    errors = []
    for name, check, message in BLOCKING_RULES:
        try:
            if not check(prop):
                errors.append(message)
        except Exception as e:
            errors.append(f"Check '{name}' failed unexpectedly: {e}")
    return errors


def publish(prop, repo, listing_status: str = "private_placement") -> dict:
    if not isinstance(listing_status, str) or listing_status not in {"private_placement", "active"}:
        raise ValueError("Listing visibility must be private_placement or active")
    if prop.choice_property_id:
        raise ValueError(
            f"Property {prop.id} is already published (choice_property_id={prop.choice_property_id})"
        )

    blocking_errors = pre_publish_checks(prop)
    if blocking_errors:
        raise ValueError("Cannot publish — failing checks:\n• " + "\n• ".join(blocking_errors))

    image_results = _parse_photo_urls(prop.original_image_urls)
    if not image_results:
        local_paths = _local_image_paths(prop)
        if not local_paths:
            raise ValueError("No authentic source photos are available.")
        logger.info("Uploading %d legacy local images to ImageKit for property %s", len(local_paths), prop.id)
        image_results = _upload_images_to_imagekit(prop.id, local_paths)
    if not image_results:
        raise RuntimeError("No valid property photos are available for publishing.")

    client = _get_supabase()
    existing_id = _check_duplicate_in_supabase(client, prop)
    if existing_id:
        logger.warning(
            "Duplicate detected: property %s matches existing Supabase record %s (%s, %s, %s). Skipping.",
            prop.id, existing_id, prop.address, prop.city, prop.state
        )
        repo.delete(prop.id)
        return {
            "ok":                True,
            "choice_property_id": existing_id,
            "message":           f"Duplicate detected — linked to existing listing {existing_id} (not re-published)",
            "was_duplicate":     True,
        }

    logger.info("Inserting property into Supabase for property %s", prop.id)
    record = _build_supabase_record(prop, image_results, listing_status)

    stripped_columns = []
    for attempt in range(15):
        try:
            result = client.table("properties").insert(record).execute()
            break
        except Exception as exc:
            err_str = str(exc)
            if "PGRST204" in err_str or "could not find" in err_str.lower():
                import re as _re
                col_match = _re.search(r"'(\w+)'\s+column", err_str, _re.IGNORECASE)
                if col_match:
                    bad_col = col_match.group(1)
                    if bad_col in record:
                        if bad_col == "unit_options" and record[bad_col]:
                            raise RuntimeError(
                                "The Choice schema is missing properties.unit_options. "
                                "Apply the property-unit-options migration before publishing this community."
                            ) from exc
                        stripped_columns.append(bad_col)
                        del record[bad_col]
                        logger.warning(
                            "Supabase schema missing column '%s' — retrying without it (attempt %d)",
                            bad_col, attempt + 1
                        )
                        continue
            raise
    else:
        raise RuntimeError("Supabase insert failed after stripping unknown columns.")

    if stripped_columns:
        logger.warning(
            "Published property %s but %d column(s) missing from Supabase schema: %s.",
            prop.id, len(stripped_columns), stripped_columns
        )

    if not result.data:
        raise RuntimeError(
            "Supabase insert returned no data. Check your database schema and permissions."
        )

    choice_property_id = result.data[0].get("id")
    # Insert photos into property_photos (photos no longer live as columns on properties)
    if image_results:
        photos_payload = [
            {
                "property_id":   str(choice_property_id),
                "url":           r["url"],
                "file_id":       r.get("file_id"),
                "width":         r.get("width"),
                "height":        r.get("height"),
                "display_order": i + 1,
                "is_hero":       i == 0,
                "watermark_status": "clean",
            }
            for i, r in enumerate(image_results)
        ]
        try:
            client.table("property_photos").insert(photos_payload).execute()
            logger.info(
                "Inserted %d photos into property_photos for %s",
                len(photos_payload), choice_property_id
            )
        except Exception as photo_exc:
            _rollback_published_record(client, choice_property_id)
            raise RuntimeError(
                f"Photo insertion failed for {choice_property_id}; publication was rolled back."
            ) from photo_exc

    floor_plan_media = _build_floor_plan_media(_parse_object(getattr(prop, "original_data", None)))
    if floor_plan_media:
        media_payload = [
            {"property_id": str(choice_property_id), **item}
            for item in floor_plan_media
        ]
        try:
            client.table("property_media").insert(media_payload).execute()
        except Exception as media_exc:
            _rollback_published_record(client, choice_property_id)
            raise RuntimeError(
                f"Floor-plan media insertion failed for {choice_property_id}; publication was rolled back."
            ) from media_exc

    repo.delete(prop.id)

    logger.info(
        "Property %s published as %s (%s) and removed from pipeline",
        prop.id, choice_property_id, listing_status,
    )
    return {
        "ok":                 True,
        "choice_property_id": str(choice_property_id),
        "listing_status":     listing_status,
        "photo_count":        len(image_results),
        "floor_plan_count":   len(floor_plan_media),
        "message":            "Private placement created" if listing_status == "private_placement" else "Published publicly",
        "was_duplicate":     False,
    }


def _rollback_published_record(client, property_id: str) -> None:
    for table in ("property_media", "property_photos", "properties"):
        try:
            client.table(table).delete().eq("property_id" if table != "properties" else "id", property_id).execute()
        except Exception:
            logger.exception("Could not roll back %s for incomplete publication %s", table, property_id)
