import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone

from imagekitio import ImageKit
from supabase import create_client

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PROPERTY_TYPE_MAP = {
    "SINGLE_FAMILY":  "house",
    "APARTMENT":      "apartment",
    "APARTMENTS":     "apartment",
    "CONDO":          "condo",
    "CONDOS":         "condo",
    "CONDO_TOWNHOME": "condo",
    "TOWNHOMES":      "townhouse",
    "TOWNHOME":       "townhouse",
    "MULTI_FAMILY":   "house",
    "DUPLEX_TRIPLEX": "house",
    "MOBILE":         "house",
    "LAND":           "house",
    "FARM":           "house",
}

BOILERPLATE_PATTERNS = [
    r"To apply,?\s+visit\s+TurboTenant[^.]*\.",
    r"apply here on TurboTenant[^.]*\.",
    r"Applications are only received through\s+TurboTenant[^.]*\.",
    r"search for Property ID\s+\d+[^.]*\.",
    r"FOLLOW these STEPS to END YOUR SEARCH[\s\S]*?(?=\n\n|\Z)",
    r"For more information.*?call[^.]*\.",
    r"Contact\s+(?:us|the agent|the landlord|your|our)[^.]*for (?:more|a) (?:info|showing|tour)[^.]*\.",
    r"Visit our website for more properties[^.]*\.",
    r"Schedule a tour (?:today|now)[^.]*\.",
    r"Don['']t miss (?:this|out)[^!.]*[!.]",
    r"This (?:won['']t|will not) last[^!.]*[!.]",
    r"Call (?:today|now|us)[^!.]*[!.]",
    r"Apply Now[^\n]*",
    r"Apply (?:today|now|online)[^!.]*[!.]",
    r"-{8,}",
    r"={8,}",
    r"\*{8,}",
    r"_{8,}",
    r"All applicants must[^.]*\.",
    r"We (?:do not|don['']t) accept[^.]*applications[^.]*\.",
    r"Background check(?:s)? required[^.]*\.",
]


def _clean_description(text: str) -> str:
    if not text:
        return text
    for pattern in BOILERPLATE_PATTERNS:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()
    return text


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


def _build_supabase_record(prop, imagekit_results: list) -> dict:
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

    def _generate_title(prop) -> str:
        if prop.title:
            return prop.title
        parts = []
        if prop.bedrooms:
            parts.append(f"{prop.bedrooms} Bed")
        if prop.bathrooms:
            baths = int(prop.bathrooms) if prop.bathrooms == int(prop.bathrooms) else prop.bathrooms
            parts.append(f"{baths} Bath")
        ptype = (prop.property_type or "").replace("_", " ").title() or "Property"
        bed_bath = " / ".join(parts)
        location = ", ".join(filter(None, [prop.city, prop.state]))
        if bed_bath:
            return f"{bed_bath} {ptype} in {location}" if location else f"{bed_bath} {ptype}"
        return f"{ptype} in {location}" if location else prop.address or "Rental Property"

    choice_id = "PROP-" + uuid.uuid4().hex[:8].upper()

    raw_type = (prop.property_type or "").upper()
    normalized_type = PROPERTY_TYPE_MAP.get(raw_type, raw_type.lower() if raw_type else None)

    pets_allowed = prop.pets_allowed
    cleaned_description = _clean_description(prop.description)
    application_fee = prop.application_fee if prop.application_fee is not None else 0

    record = {
        "id":                   choice_id,
        "status":               "active",
        "title":                _generate_title(prop),
        "description":          cleaned_description,
        "showing_instructions": prop.showing_instructions,
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
        "security_deposit":     prop.security_deposit,
        "last_months_rent":     prop.last_months_rent,
        "application_fee":      application_fee,
        "pet_deposit":          prop.pet_deposit,
        "admin_fee":            prop.admin_fee,
        "move_in_special":      prop.move_in_special,
        "available_date":       prop.available_date,
        "lease_terms":          parse_json(prop.lease_terms),
        "minimum_lease_months": prop.minimum_lease_months,
        "pets_allowed":         pets_allowed,
        "pet_types_allowed":    parse_json(prop.pet_types_allowed),
        "pet_weight_limit":     prop.pet_weight_limit,
        "pet_details":          prop.pet_details,
        "smoking_allowed":      prop.smoking_allowed,
        "utilities_included":   parse_json(prop.utilities_included),
        "parking":              prop.parking,
        "parking_fee":          prop.parking_fee,
        "amenities":            _build_amenities_list(prop, parse_json),
        "appliances":           parse_json(prop.appliances),
        "flooring":             parse_json(prop.flooring),
        "heating_type":         prop.heating_type,
        "cooling_type":         prop.cooling_type,
        "laundry_type":         prop.laundry_type,
        "virtual_tour_url":     prop.virtual_tour_url,
        # photo_urls / photo_file_ids were removed from properties in Choice migration
        # 20260426000002 — photos now live in property_photos table (inserted separately)
    }

    if landlord_id:
        record["landlord_id"] = landlord_id

    SCHEMA_OPTIONAL_BOOLEANS = {"has_basement", "has_central_air", "smoking_allowed"}
    result = {}
    for k, v in record.items():
        if v is None:
            continue
        if k in SCHEMA_OPTIONAL_BOOLEANS and v is False:
            continue
        result[k] = v
    return result


def refresh_images(prop, repo) -> dict:
    local_paths = []
    try:
        local_paths = json.loads(prop.local_image_paths or "[]")
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

    raw_type = (prop.property_type or "").upper()
    normalized_type = PROPERTY_TYPE_MAP.get(raw_type, raw_type.lower() if raw_type else None)

    update_payload = {
        "title":                prop.title,
        "description":          _clean_description(prop.description),
        "showing_instructions": prop.showing_instructions,
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
        "security_deposit":     prop.security_deposit,
        "last_months_rent":     prop.last_months_rent,
        "application_fee":      prop.application_fee if prop.application_fee is not None else 0,
        "pet_deposit":          prop.pet_deposit,
        "admin_fee":            prop.admin_fee,
        "available_date":       prop.available_date,
        "lease_terms":          parse_json(prop.lease_terms),
        "minimum_lease_months": prop.minimum_lease_months,
        "pets_allowed":         prop.pets_allowed,
        "pet_types_allowed":    parse_json(prop.pet_types_allowed),
        "pet_weight_limit":     prop.pet_weight_limit,
        "pet_details":          prop.pet_details,
        "smoking_allowed":      prop.smoking_allowed,
        "utilities_included":   parse_json(prop.utilities_included),
        "parking":              prop.parking,
        "parking_fee":          prop.parking_fee,
        "amenities":            _build_amenities_list(prop, parse_json),
        "appliances":           parse_json(prop.appliances),
        "flooring":             parse_json(prop.flooring),
        "heating_type":         prop.heating_type,
        "cooling_type":         prop.cooling_type,
        "laundry_type":         prop.laundry_type,
        "move_in_special":      prop.move_in_special,
        "virtual_tour_url":     prop.virtual_tour_url,
    }

    update_payload = {k: v for k, v in update_payload.items() if v is not None}

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
    valid = {"active", "rented", "archived", "inactive"}
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


BLOCKING_RULES = [
    ("address",   lambda p: bool(p.address),                               "Address is required"),
    ("city_state",lambda p: bool(p.city and p.state),                      "City and state are required"),
    ("rent",      lambda p: bool(p.monthly_rent),                          "Monthly rent must be set"),
    ("bedrooms",  lambda p: p.bedrooms is not None,                        "Bedroom count is required"),
    ("photos",    lambda p: bool(json.loads(p.local_image_paths or "[]")), "At least one image must be downloaded"),
    ("quality",   lambda p: (p.data_quality_score or 0) >= 50,            "Quality score is below 50 — too many critical fields missing"),
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


def publish(prop, repo) -> dict:
    if prop.choice_property_id:
        raise ValueError(
            f"Property {prop.id} is already published (choice_property_id={prop.choice_property_id})"
        )

    blocking_errors = pre_publish_checks(prop)
    if blocking_errors:
        raise ValueError("Cannot publish — failing checks:\n• " + "\n• ".join(blocking_errors))

    local_paths = []
    try:
        local_paths = json.loads(prop.local_image_paths or "[]")
    except Exception:
        pass

    if not local_paths:
        raise ValueError("No local images found. Download images before publishing.")

    client = _get_supabase()
    existing_id = _check_duplicate_in_supabase(client, prop)
    if existing_id:
        logger.warning(
            "Duplicate detected: property %s matches existing Supabase record %s (%s, %s, %s). Skipping.",
            prop.id, existing_id, prop.address, prop.city, prop.state
        )
        prop.status = "published"
        prop.published_at = datetime.now(timezone.utc).isoformat()
        prop.choice_property_id = existing_id
        repo.save(prop)
        return {
            "ok":                True,
            "choice_property_id": existing_id,
            "message":           f"Duplicate detected — linked to existing listing {existing_id} (not re-published)",
            "was_duplicate":     True,
        }

    logger.info("Uploading %d images to ImageKit for property %s", len(local_paths), prop.id)
    imagekit_results = _upload_images_to_imagekit(prop.id, local_paths)

    if not imagekit_results:
        raise RuntimeError("Image upload to ImageKit failed — no images were uploaded successfully.")

    logger.info("Inserting property into Supabase for property %s", prop.id)
    record = _build_supabase_record(prop, imagekit_results)

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
    now = datetime.now(timezone.utc).isoformat()

    # Insert photos into property_photos (photos no longer live as columns on properties)
    if imagekit_results:
        photos_payload = [
            {
                "property_id":   str(choice_property_id),
                "url":           r["url"],
                "file_id":       r["file_id"],
                "display_order": i,
            }
            for i, r in enumerate(imagekit_results)
        ]
        try:
            client.table("property_photos").insert(photos_payload).execute()
            logger.info(
                "Inserted %d photos into property_photos for %s",
                len(photos_payload), choice_property_id
            )
        except Exception as photo_exc:
            # Log but don't fail the publish — the listing record is already committed
            logger.error(
                "property_photos insert failed for %s: %s", choice_property_id, photo_exc
            )

    prop.status = "published"
    prop.published_at = now
    prop.choice_property_id = str(choice_property_id)
    repo.save(prop)

    logger.info("Property %s published successfully as %s", prop.id, choice_property_id)
    return {
        "ok":                 True,
        "choice_property_id": str(choice_property_id),
        "message":           "Published successfully",
        "was_duplicate":     False,
    }
