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
    # Phase 3 (3.2) — added 2026-04-26. Each requires a Supabase ALTER TABLE
    # to actually persist; until the migration runs, `Repository.save` will
    # silently drop them via the live-schema cache (see _allowed_columns).
    #   ALTER TABLE pipeline_properties
    #     ADD COLUMN neighborhood text,
    #     ADD COLUMN broker_name  text,
    #     ADD COLUMN agent_name   text,
    #     ADD COLUMN tax_value    integer,
    #     ADD COLUMN hoa_fee      integer;
    "neighborhood", "broker_name", "agent_name", "tax_value", "hoa_fee",
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

    _INTEGER_FIELDS = {
        "bedrooms", "half_bathrooms", "square_footage", "lot_size_sqft",
        "monthly_rent", "year_built", "floors", "total_units", "garage_spaces",
        "pet_weight_limit", "minimum_lease_months", "security_deposit",
        "last_months_rent", "application_fee", "pet_deposit", "admin_fee",
        "parking_fee", "tax_value", "hoa_fee",
    }

    # Phase 3 (3.2): live-schema cache. PROPERTY_FIELDS may declare columns
    # that the upstream Supabase table does not yet have (because the migration
    # hasn't been run). We discover the real shape on first save by selecting
    # one row, then filter out any unknown keys before the upsert. Once the
    # ALTER TABLE is applied, restart the process and the new columns light up
    # automatically. Process-local — small, simple, sufficient.
    _allowed_columns_cache: set[str] | None = None

    def _allowed_columns(self) -> set[str]:
        if Repository._allowed_columns_cache is not None:
            return Repository._allowed_columns_cache
        try:
            probe = self._client.table("pipeline_properties").select("*").limit(1).execute()
            if probe.data:
                cols = set(probe.data[0].keys())
            else:
                # Empty table — fall back to optimistic "trust PROPERTY_FIELDS"
                # (a write will fail loudly if a column is missing; we'll learn
                # the real shape on the next call when the row exists).
                cols = set(PROPERTY_FIELDS)
        except Exception:
            cols = set(PROPERTY_FIELDS)
        Repository._allowed_columns_cache = cols
        return cols

    def save(self, prop: PropertyRecord) -> None:
        prop.updated_at = datetime.now(timezone.utc).isoformat()
        data = {k: v for k, v in prop.to_dict().items() if v is not None}
        for field in self._INTEGER_FIELDS:
            if field in data and data[field] is not None:
                try:
                    data[field] = int(float(data[field]))
                except (ValueError, TypeError):
                    pass

        allowed = self._allowed_columns()
        unknown = [k for k in data.keys() if k not in allowed]
        if unknown:
            for k in unknown:
                data.pop(k, None)

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

    def save_chat_message(self, property_id: str, session_id: str, role: str, content: str) -> None:
        """Save a chat message to the conversation history."""
        try:
            self._client.table("pipeline_chat_conversations").insert({
                "property_id": property_id,
                "session_id": session_id,
                "role": role,
                "content": content,
            }).execute()
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(
                "Could not save chat message: %s", e
            )

    def get_chat_history(self, property_id: str, session_id: str, limit: int = 50) -> list[dict]:
        """Retrieve chat history for a property session."""
        try:
            result = (
                self._client.table("pipeline_chat_conversations")
                .select("*")
                .eq("property_id", property_id)
                .eq("session_id", session_id)
                .order("created_at", desc=False)
                .limit(limit)
                .execute()
            )
            if result.data:
                return [
                    {
                        "role": row["role"],
                        "content": row["content"],
                        "timestamp": row["created_at"]
                    }
                    for row in result.data
                ]
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(
                "Could not fetch chat history: %s", e
        )
        return []

    def clear_old_chat_history(self, days_old: int = 30) -> None:
        """Clean up chat history older than specified days."""
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days_old)
            self._client.table("pipeline_chat_conversations").delete().lt(
                "created_at", cutoff.isoformat()
            ).execute()
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(
                "Could not clear old chat history: %s", e
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

    def add_scrape_run(self, run: "ScrapeRunRecord") -> None:
        try:
            self._client.table("pipeline_scrape_runs").insert({
                "source":       run.source,
                "location":     run.location,
                "count_total":  run.count_total,
                "count_new":    run.count_new,
                "avg_score":    run.avg_score,
                "error_message": run.error_message,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }).execute()
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("Could not log scrape run: %s", e)

    def list_scrape_runs(self, limit: int = 50) -> list:
        try:
            result = (
                self._client.table("pipeline_scrape_runs")
                .select("*")
                .order("completed_at", desc=True)
                .limit(limit)
                .execute()
            )
            if result.data:
                return result.data
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("Could not fetch scrape runs: %s", e)
        return []

    def quality_stats_by_source(self) -> list[dict]:
        """Aggregate quality stats grouped by source."""
        try:
            result = self._client.table("pipeline_properties").select(
                "source, data_quality_score, status"
            ).execute()
            rows = result.data or []
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("Could not fetch quality stats: %s", e)
            return []

        from collections import defaultdict
        buckets: dict[str, dict] = defaultdict(lambda: {
            "count": 0,
            "scores": [],
            "by_status": defaultdict(int),
        })
        for row in rows:
            src = row.get("source") or "unknown"
            score = row.get("data_quality_score")
            status = row.get("status") or "unknown"
            buckets[src]["count"] += 1
            if score is not None:
                buckets[src]["scores"].append(score)
            buckets[src]["by_status"][status] += 1

        out = []
        for src, data in sorted(buckets.items()):
            scores = data["scores"]
            out.append({
                "source":      src,
                "count":       data["count"],
                "avg_score":   round(sum(scores) / len(scores), 1) if scores else None,
                "min_score":   min(scores) if scores else None,
                "max_score":   max(scores) if scores else None,
                "by_status":   dict(data["by_status"]),
            })
        return out

    def commit(self):
        pass

    def refresh(self, prop: PropertyRecord):
        pass


class ScrapeRunRecord:
    def __init__(self, source, location, count_total=0, count_new=0,
                 avg_score=None, error_message=None,
                 id=None, started_at=None, completed_at=None):
        self.id = id
        self.source = source
        self.location = location
        self.count_total = count_total
        self.count_new = count_new
        self.avg_score = avg_score
        self.error_message = error_message
        self.started_at = started_at
        self.completed_at = completed_at

    def to_dict(self):
        return {
            "id": self.id,
            "source": self.source,
            "location": self.location,
            "count_total": self.count_total,
            "count_new": self.count_new,
            "avg_score": self.avg_score,
            "error_message": self.error_message,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


def get_repo() -> Repository:
    return Repository()
