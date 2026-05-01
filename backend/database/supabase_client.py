import os
from supabase import create_client, Client
from unittest.mock import MagicMock


_client: Client | None = None


class MockSupabaseClient:
    """Returned when Supabase credentials are absent or placeholder.
    Every operation raises a clear error so callers fail loudly instead of silently."""

    def __init__(self):
        err = Exception(
            "Supabase credentials are not configured. "
            "Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in Replit Secrets."
        )
        self.table = MagicMock(side_effect=err)

    def schema(self, _name: str):
        return self

    def __getattr__(self, name):
        return MagicMock(
            side_effect=Exception(
                "Supabase credentials are not configured. "
                "Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in Replit Secrets."
            )
        )


def _build_client() -> Client:
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = (os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")).strip()

    if not url or not key or url.startswith("https://placeholder") or key == "placeholder_key":
        return MockSupabaseClient()  # type: ignore

    return create_client(url.rstrip("/"), key)


def get_supabase() -> Client:
    """Returns the Supabase client pointing at the PUBLIC schema.
    Use for live-site tables: properties, property_photos, landlords, etc.
    These tables are owned by the Choice website (choice121/Choice repo).
    """
    global _client
    if _client is None:
        _client = _build_client()
    return _client


def get_pipeline_schema():
    """Returns a PostgREST client scoped to the PIPELINE private schema.

    Background
    ----------
    Pipeline tables (pipeline_properties, pipeline_enrichment_log,
    pipeline_scrape_runs, pipeline_chat_conversations) were originally in the
    public schema.  Choice website migration 20260426000002_pipeline_private_schema.sql
    moved them to a locked-down `pipeline` schema (service_role access only) for
    security hygiene.  All pipeline table access MUST go through this function.

    Usage
    -----
        client = get_pipeline_schema()
        client.table("pipeline_properties").select("*").execute()

    Never call get_supabase().table("pipeline_properties") — that looks in public
    and will fail with a schema-cache miss.
    """
    return get_supabase().schema("pipeline")
