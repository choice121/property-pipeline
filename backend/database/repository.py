from __future__ import annotations

from datetime import datetime, timezone
from database.supabase_client import get_supabase

PROPERTY_FIELDS = [
    "id", "source", "source_url", "source_listing_id", "status",
    "title", "address", "city", "state", "zip", "county",
    "lat", "lng", "bedrooms", "bathrooms", "half_bathrooms",
    "square_footage", "lot_size_sqft", "monthly_rent", "property_type",
    "year_built", "floors", "unit_number", "total_units", "description",
    "showing_instructions", "available_date", "parking", "garage_spaces",
    "pets_allowed", "pet_types_allowed", "pet_weight_limit", "pet_details",
    "smoking_allowed", "lease_terms", "minimum_lease_months",
    "security_deposit", "last_months_rent", "application_fee",
    "pet_deposit", "admin_fee", "move_in_special", "parking_fee",
    "amenities", "appliances", "utilities_included", "flooring",
    "heating_type", "cooling_type", "laundry_type", "total_bathrooms",
    "has_basement", "has_central_air", "virtual_tour_url",
    "original_image_urls", "local_image_paths", "original_data",
    "edited_fields", "data_quality_score", "missing_fields",
    "inferred_features", "published_at", "choice_property_id",
    "scraped_at", "updated_at",
]

_PROPERTY_DEFAULTS = {
    "status":           "scraped",
    "local_image_paths": "[]",
    "edited_fields":    "[]",
    "missing_fields":   "[]",
    "inferred_features": "[]",
}


class PropertyRecord:
    def __init__(self, **kwargs):
        for field in PROPERTY_FIELDS:
            if field in kwargs:
                setattr(self, field, kwargs[field])
            elif field in _PROPERTY_DEFAULTS:
                setattr(self, field, _PROPERTY_DEFAULTS[field])
            else:
                setattr(self, field, None)

    def to_dict(self) -> dict:
        return {field: getattr(self, field, None) for field in PROPERTY_FIELDS}


class AiEnrichmentLog:
    def __init__(self, property_id, field, method,
                 ai_value=None, human_value=None,
                 was_overridden=False, id=None, created_at=None):
        self.id = id
        self.property_id = property_id
        self.field = field
        self.method = method
        self.ai_value = ai_value
        self.human_value = human_value
        self.was_overridden = was_overridden
        self.created_at = created_at


class Repository:
    def __init__(self, client=None):
        self._client = client or get_supabase()

    def get(self, prop_id: str) -> PropertyRecord | None:
        result = (
            self._client.table("pipeline_properties")
            .select("*")
            .eq("id", prop_id)
            .limit(1)
            .execute()
        )
        if result.data:
            return PropertyRecord(**result.data[0])
        return None

    def get_by_source_listing_id(self, source_listing_id: str) -> PropertyRecord | None:
        result = (
            self._client.table("pipeline_properties")
            .select("*")
            .eq("source_listing_id", source_listing_id)
            .limit(1)
            .execute()
        )
        if result.data:
            return PropertyRecord(**result.data[0])
        return None

    def list(self, status=None, search=None, sort="scraped_at") -> list[PropertyRecord]:
        query = self._client.table("pipeline_properties").select("*")

        if status:
            query = query.eq("status", status)

        sort_map = {
            "scraped_at":        ("scraped_at", True),
            "monthly_rent":      ("monthly_rent", False),
            "monthly_rent_desc": ("monthly_rent", True),
            "bedrooms":          ("bedrooms", False),
        }
        col, descending = sort_map.get(sort, ("scraped_at", True))
        query = query.order(col, desc=descending)

        result = query.execute()
        props = [PropertyRecord(**row) for row in result.data]

        if search:
            term = search.lower()
            props = [
                p for p in props
                if (p.address and term in p.address.lower())
                or (p.city and term in p.city.lower())
            ]

        return props

    def save(self, prop: PropertyRecord) -> None:
        prop.updated_at = datetime.now(timezone.utc).isoformat()
        data = {k: v for k, v in prop.to_dict().items() if v is not None}
        self._client.table("pipeline_properties").upsert(data, on_conflict="id").execute()

    def delete(self, prop_id: str) -> None:
        self._client.table("pipeline_properties").delete().eq("id", prop_id).execute()

    def get_enrichment_log(self, prop_id: str, field: str, was_overridden: bool) -> AiEnrichmentLog | None:
        result = (
            self._client.table("pipeline_enrichment_log")
            .select("*")
            .eq("property_id", prop_id)
            .eq("field", field)
            .eq("was_overridden", was_overridden)
            .limit(1)
            .execute()
        )
        if result.data:
            return AiEnrichmentLog(**result.data[0])
        return None

    def update_log(self, log: AiEnrichmentLog) -> None:
        self._client.table("pipeline_enrichment_log").update({
            "was_overridden": log.was_overridden,
            "human_value":    log.human_value,
        }).eq("id", log.id).execute()

    def add_log(self, log: AiEnrichmentLog) -> None:
        data = {
            "property_id":    log.property_id,
            "field":          log.field,
            "method":         log.method,
            "ai_value":       log.ai_value,
            "human_value":    log.human_value,
            "was_overridden": log.was_overridden,
        }
        self._client.table("pipeline_enrichment_log").insert(data).execute()

    def add_all_logs(self, logs: list[AiEnrichmentLog]) -> None:
        for log in logs:
            self.add_log(log)

    def update_inferred_features(self, prop_id: str, features: list) -> None:
        """
        Lightweight update of just the inferred_features field.
        Used by bulk operations to save scan/clean timestamps without
        triggering a full property save (which would change updated_at
        and invalidate the 'edited since last scan' check).
        """
        try:
            import json
            self._client.table("pipeline_properties").update(
                {"inferred_features": json.dumps(features)}
            ).eq("id", prop_id).execute()
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(
                "Could not update inferred_features for %s: %s", prop_id, e
            )

    def list_logs_by_field(self, prop_id: str, field: str, limit: int = 10) -> list[AiEnrichmentLog]:
        try:
            result = (
                self._client.table("pipeline_enrichment_log")
                .select("*")
                .eq("property_id", prop_id)
                .eq("field", field)
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            if result.data:
                return [AiEnrichmentLog(**row) for row in result.data]
        except Exception:
            pass
        return []

    def commit(self):
        pass

    def refresh(self, prop: PropertyRecord):
        pass


def get_repo() -> Repository:
    return Repository()
