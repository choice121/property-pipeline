import json
import logging
import os
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
        # HS256 signature is exactly 32 bytes = 43 base64url chars
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
        try:
            return json.loads(val)
        except Exception:
            return []

    landlord_id = os.environ.get("CHOICE_LANDLORD_ID") or None

    record = {
        "status": "active",
        "title": prop.title,
        "address": prop.address,
        "city": prop.city,
        "state": prop.state,
        "zip": prop.zip,
        "county": prop.county,
        "lat": prop.lat,
        "lng": prop.lng,
        "bedrooms": prop.bedrooms,
        "bathrooms": prop.bathrooms,
        "half_bathrooms": prop.half_bathrooms,
        "square_footage": prop.square_footage,
        "lot_size_sqft": prop.lot_size_sqft,
        "monthly_rent": prop.monthly_rent,
        "property_type": prop.property_type,
        "year_built": prop.year_built,
        "description": prop.description,
        "available_date": prop.available_date,
        "parking": prop.parking,
        "pets_allowed": prop.pets_allowed,
        "pet_details": prop.pet_details,
        "smoking_allowed": prop.smoking_allowed,
        "heating_type": prop.heating_type,
        "cooling_type": prop.cooling_type,
        "laundry_type": prop.laundry_type,
        "virtual_tour_url": prop.virtual_tour_url,
        "lease_terms": parse_json(prop.lease_terms),
        "amenities": parse_json(prop.amenities),
        "appliances": parse_json(prop.appliances),
        "utilities_included": parse_json(prop.utilities_included),
        "flooring": parse_json(prop.flooring),
        "photo_urls": [r["url"] for r in imagekit_results],
        "photo_file_ids": [r["file_id"] for r in imagekit_results],
        "source": prop.source,
        "source_url": prop.source_url,
    }

    if landlord_id:
        record["landlord_id"] = landlord_id

    return {k: v for k, v in record.items() if v is not None}


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
