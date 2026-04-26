"""Lock-in tests for the _compact_original_data helper in scraper_service.

These guard against regressions where large raw payloads sneak back into the
pipeline_properties.original_data column and inflate Supabase row size.

Run from the backend/ directory:
    PYTHONPATH=. python3 -m pytest tests/test_compact_original_data.py -v
"""

import json
import sys
import importlib

# Minimal env shim so scraper_service can be imported without real secrets
import os
os.environ.setdefault("SUPABASE_URL", "https://placeholder.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "placeholder")
os.environ.setdefault("IMAGEKIT_PUBLIC_KEY", "placeholder")
os.environ.setdefault("IMAGEKIT_PRIVATE_KEY", "placeholder")
os.environ.setdefault("IMAGEKIT_URL_ENDPOINT", "https://placeholder.imagekit.io")
os.environ.setdefault("DEEPSEEK_API_KEY", "placeholder")

import services.scraper_service as ss

_compact = ss._compact_original_data
_MAX = ss._ORIGINAL_DATA_MAX_BYTES
_KEEP = ss._ORIGINAL_DATA_KEEP_KEYS


def test_allowed_keys_are_kept():
    row = {k: f"val_{k}" for k in _KEEP}
    result = json.loads(_compact(row))
    assert set(result.keys()) == set(_KEEP)


def test_unknown_keys_are_dropped():
    row = {"mls_id": "ABC123", "photo_urls": ["http://x.com/a.jpg"] * 50, "description": "long text here"}
    result = json.loads(_compact(row))
    assert "photo_urls" not in result
    assert "description" not in result
    assert result["mls_id"] == "ABC123"


def test_underscore_keys_are_kept():
    row = {"_watermarked": True, "_skip_enrichment": False, "junk": "drop me"}
    result = json.loads(_compact(row))
    assert result["_watermarked"] is True
    assert result["_skip_enrichment"] is False
    assert "junk" not in result


def test_output_never_exceeds_max_bytes():
    huge_string = "x" * 100_000
    row = {k: huge_string for k in _KEEP}
    blob = _compact(row)
    assert len(blob.encode("utf-8")) <= _MAX, f"blob is {len(blob.encode())} bytes, max is {_MAX}"


def test_small_payload_unchanged():
    row = {"mls_id": "MLS-001", "list_price": 2500, "status": "active"}
    result = json.loads(_compact(row))
    assert result == {"mls_id": "MLS-001", "list_price": 2500, "status": "active"}


def test_empty_row_returns_empty_json():
    result = json.loads(_compact({}))
    assert result == {}


def test_none_values_are_preserved():
    row = {"mls_id": None, "list_price": None}
    result = json.loads(_compact(row))
    assert result["mls_id"] is None
    assert result["list_price"] is None


def test_output_is_valid_json():
    row = {"mls_id": "X", "hoa_fee": 150.0, "_internal": {"nested": True}}
    blob = _compact(row)
    parsed = json.loads(blob)
    assert parsed["mls_id"] == "X"
