import os
from supabase import create_client, Client
from unittest.mock import MagicMock

_client: Client | None = None


class MockSupabaseClient:
    """Mock Supabase client that raises errors for all operations when using placeholder credentials."""

    def __init__(self):
        self.table = MagicMock(side_effect=Exception("Using placeholder Supabase credentials. Configure real credentials for database access."))

    def __getattr__(self, name):
        # Return a mock for any attribute access
        return MagicMock(side_effect=Exception("Using placeholder Supabase credentials. Configure real credentials for database access."))


def get_supabase() -> Client:
    global _client
    if _client is None:
        url = os.environ.get("SUPABASE_URL", "").strip()
        key = (os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")).strip()

        # Check for placeholder credentials
        if url.startswith("https://placeholder") or key == "placeholder_key" or not url or not key:
            _client = MockSupabaseClient()  # type: ignore
        else:
            _client = create_client(url.rstrip("/"), key)
    return _client
