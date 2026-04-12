import json
import logging
import os
import uuid
from datetime import datetime, timezone

from imagekitio import ImageKit
from supabase import create_client

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _get_imagekit():
    return ImageKit(private_key=os.environ["IMAGEKIT_PRIVATE_KEY"])


def _clean_jwt(key: str) -> str:
    key = key.strip()
    parts = key.split(".")
    if len(parts) == 3:
        sig = parts[2]
        if len(sig) > 43:
            sig = sig[:43]
        parts[2] = sig
        key = ".".join(parts)
    return key


def _get_supabase():
    url = os.environ["SUPABASE_URL"].rstrip("/")
    key = _clean_jwt(os.environ["SUPABASE_SERVICE_ROLE_KEY"])
    return create_client(url, key)


def _upload_images_to_imagekit(property_id: str, local_image_paths: list) -> list:
    ik = _get_imagekit()
    results = []

    for rel_path in local_image_paths:
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
            "url": upload_result.url,
            "file_id": upload_result.file_id,
        })
        logger.info("Uploaded image to ImageKit: %s -> %s", file_name, upload_result.url)

    return results


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

    landlord_id = os.environ.get("CHOICE_LANDLORD_ID") or None

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

    record = {
        "id": choice_id,
        "status": "active",
        "title": _generate_title(prop),
        "description": prop.description,
        "showing_instructions": prop.showing_instructions,
        "address": prop.address,
        "city": prop.city,
        "state": prop.state,
        "zip": prop.zip,
        "county": prop.county,
        "lat": prop.lat,
        "lng": prop.lng,
        "property_type": prop.property_type,
        "year_built": prop.year_built,
        "floors": prop.floors,
        "unit_number": prop.unit_number,
        "total_units": prop.total_units,
        "bedrooms": prop.bedrooms,
        "bathrooms": prop.bathrooms,
        "half_bathrooms": prop.half_bathrooms,
        "total_bathrooms": prop.total_bathrooms,
        "square_footage": prop.square_footage,
        "lot_size_sqft": prop.lot_size_sqft,
        "garage_spaces": prop.garage_spaces,
        "monthly_rent": prop.monthly_rent,
        "security_deposit": prop.security_deposit,
        "last_months_rent": prop.last_months_rent,
        "application_fee": prop.application_fee,
        "pet_deposit": prop.pet_deposit,
        "admin_fee": prop.admin_fee,
        "move_in_special": prop.move_in_special,
        "available_date": prop.available_date,
        "lease_terms": parse_json(prop.lease_terms),
        "minimum_lease_months": prop.minimum_lease_months,
        "pets_allowed": prop.pets_allowed,
        "pet_types_allowed": parse_json(prop.pet_types_allowed),
        "pet_weight_limit": prop.pet_weight_limit,
        "pet_details": prop.pet_details,
        "smoking_allowed": prop.smoking_allowed,
        "utilities_included": parse_json(prop.utilities_included),
        "parking": prop.parking,
        "parking_fee": prop.parking_fee,
        "amenities": parse_json(prop.amenities),
        "appliances": parse_json(prop.appliances),
        "flooring": parse_json(prop.flooring),
        "heating_type": prop.heating_type,
        "cooling_type": prop.cooling_type,
        "laundry_type": prop.laundry_type,
        "has_basement": prop.has_basement,
        "has_central_air": prop.has_central_air,
        "virtual_tour_url": prop.virtual_tour_url,
        "photo_urls": [r["url"] for r in imagekit_results],
        "photo_file_ids": [r["file_id"] for r in imagekit_results],
    }

    if landlord_id:
        record["landlord_id"] = landlord_id

    return {k: v for k, v in record.items() if v is not None}


def refresh_images(prop, db) -> dict:
    """Re-upload all local images to ImageKit and update the live Supabase record."""
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
        raise RuntimeError(
            "Image upload to ImageKit failed — no images were uploaded successfully."
        )

    client = _get_supabase()
    update_payload = {
        "photo_urls": [r["url"] for r in imagekit_results],
        "photo_file_ids": [r["file_id"] for r in imagekit_results],
    }

    result = (
        client.table("properties")
        .update(update_payload)
        .eq("id", prop.choice_property_id)
        .execute()
    )

    if not result.data:
        raise RuntimeError(
            "Supabase update returned no data. The record may not exist or permissions may be insufficient."
        )

    logger.info(
        "Images refreshed for property %s: %d photos now live",
        prop.choice_property_id, len(imagekit_results)
    )
    return {
        "ok": True,
        "choice_property_id": prop.choice_property_id,
        "photo_count": len(imagekit_results),
        "message": f"Gallery updated — {len(imagekit_results)} photos now live on website",
    }


def publish(prop, db) -> dict:
    if prop.choice_property_id:
        raise ValueError(
            f"Property {prop.id} is already published (choice_property_id={prop.choice_property_id})"
        )

    local_paths = []
    try:
        local_paths = json.loads(prop.local_image_paths or "[]")
    except Exception:
        pass

    if not local_paths:
        raise ValueError("No local images found. Download images before publishing.")

    logger.info("Uploading %d images to ImageKit for property %s", len(local_paths), prop.id)
    imagekit_results = _upload_images_to_imagekit(prop.id, local_paths)

    if not imagekit_results:
        raise RuntimeError(
            "Image upload to ImageKit failed — no images were uploaded successfully."
        )

    logger.info("Inserting property into Supabase for property %s", prop.id)
    client = _get_supabase()
    record = _build_supabase_record(prop, imagekit_results)

    result = client.table("properties").insert(record).execute()

    if not result.data:
        raise RuntimeError(
            "Supabase insert returned no data. Check your database schema and permissions."
        )

    choice_property_id = result.data[0].get("id")
    now = datetime.now(timezone.utc).isoformat()

    prop.status = "published"
    prop.published_at = now
    prop.choice_property_id = str(choice_property_id)
    db.commit()
    db.refresh(prop)

    logger.info("Property %s published successfully as %s", prop.id, choice_property_id)
    return {
        "ok": True,
        "choice_property_id": str(choice_property_id),
        "message": "Published successfully",
    }
