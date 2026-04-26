"""Phase 5.6 — Fixture-based parser tests for all custom scrapers.

Each test feeds a recorded fixture payload into the scraper's parser function
and asserts that ≥ N expected fields are extracted correctly. These tests do
NOT make network calls — they prove that our parser logic is correct and will
catch regressions when an upstream changes its schema.

Run from the project root:
    PYTHONPATH=backend python3 -m pytest backend/tests/test_scraper_parsers.py -v

Or without pytest (direct execution):
    cd backend && PYTHONPATH=. python3 tests/test_scraper_parsers.py
"""

import json
import os
import sys
import xml.etree.ElementTree as ET

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


# ── Craigslist ────────────────────────────────────────────────────────────────

def test_craigslist_rss_parser_extracts_price_and_coords():
    from services.scrapers.craigslist_scraper import _parse_rss_entry

    with open(os.path.join(FIXTURES, "craigslist_rss.xml"), encoding="utf-8") as f:
        xml_text = f.read()

    root = ET.fromstring(xml_text.encode("utf-8"))
    items = root.findall(".//item")
    assert len(items) == 2, "fixture should have 2 RSS items"

    result = _parse_rss_entry(items[0], {})
    assert result is not None, "parser returned None"
    assert result["source"] == "craigslist"
    assert result["monthly_rent"] == 1750
    assert result["bedrooms"] == 2
    assert result["square_footage"] == 900
    assert abs(result["lat"] - 30.2671) < 0.001
    assert abs(result["lng"] - (-97.7430)) < 0.001
    assert result["source_listing_id"] == "cl-1234567890"


def test_craigslist_rss_parser_house_type():
    from services.scrapers.craigslist_scraper import _parse_rss_entry

    with open(os.path.join(FIXTURES, "craigslist_rss.xml"), encoding="utf-8") as f:
        xml_text = f.read()

    root = ET.fromstring(xml_text.encode("utf-8"))
    items = root.findall(".//item")
    result = _parse_rss_entry(items[1], {})
    assert result is not None
    assert result["monthly_rent"] == 2200
    assert result["bedrooms"] == 3
    assert result["property_type"] == "Single Family"


def test_craigslist_original_data_is_compact():
    from services.scrapers.craigslist_scraper import _parse_rss_entry

    with open(os.path.join(FIXTURES, "craigslist_rss.xml"), encoding="utf-8") as f:
        xml_text = f.read()

    root = ET.fromstring(xml_text.encode("utf-8"))
    result = _parse_rss_entry(root.findall(".//item")[0], {})
    od = json.loads(result["original_data"])
    assert set(od.keys()) <= {"listing_id", "property_url", "list_price"}, \
        f"original_data has unexpected keys: {set(od.keys())}"
    assert len(result["original_data"].encode()) <= 4096


# ── HotPads ───────────────────────────────────────────────────────────────────

def test_hotpads_normalize_extracts_all_core_fields():
    from services.scrapers.hotpads_scraper import _normalize

    with open(os.path.join(FIXTURES, "hotpads_listing.json"), encoding="utf-8") as f:
        listing = json.load(f)

    result = _normalize(listing)
    assert result is not None, "_normalize returned None"
    assert result["source"] == "hotpads"
    assert result["address"] == "123 Main St"
    assert result["city"] == "Austin"
    assert result["state"] == "TX"
    assert result["zip"] == "78701"
    assert result["monthly_rent"] == 1850
    assert result["bedrooms"] == 2
    assert result["bathrooms"] == 1.5
    assert result["square_footage"] == 950
    assert result["pets_allowed"] is True
    photos = json.loads(result["original_image_urls"])
    assert len(photos) == 2


def test_hotpads_original_data_is_compact():
    from services.scrapers.hotpads_scraper import _normalize

    with open(os.path.join(FIXTURES, "hotpads_listing.json"), encoding="utf-8") as f:
        listing = json.load(f)

    result = _normalize(listing)
    od = json.loads(result["original_data"])
    allowed = {"listing_id", "property_url", "list_price", "status"}
    assert set(od.keys()) <= allowed, f"unexpected keys: {set(od.keys()) - allowed}"
    assert len(result["original_data"].encode()) <= 4096


# ── InvitationHomes ───────────────────────────────────────────────────────────

def test_invitation_homes_normalize_decodes_svelte_flat_array():
    from services.scrapers.invitation_homes_scraper import _normalize

    with open(os.path.join(FIXTURES, "invitation_homes_data.json"), encoding="utf-8") as f:
        data = json.load(f)

    node = data["nodes"][0]
    raw = node["data"]
    # property dict is at index 5 in our fixture
    prop_dict = raw[5]

    result = _normalize(prop_dict, raw)
    assert result is not None, "_normalize returned None"
    assert result["source"] == "invitation_homes"
    assert result["address"] == "456 Oak Ave"
    assert result["city"] == "Dallas"
    assert result["state"] == "TX"
    assert result["bedrooms"] == 3
    assert result["monthly_rent"] == 2100
    assert result["pets_allowed"] is True
    amenities = json.loads(result["amenities"])
    assert "Pool" in amenities
    assert "Garage" in amenities


def test_invitation_homes_original_data_is_compact():
    from services.scrapers.invitation_homes_scraper import _normalize

    with open(os.path.join(FIXTURES, "invitation_homes_data.json"), encoding="utf-8") as f:
        data = json.load(f)

    raw = data["nodes"][0]["data"]
    prop_dict = raw[5]
    result = _normalize(prop_dict, raw)
    od = json.loads(result["original_data"])
    # All keys must be in the allow-list OR start with _
    for key in od:
        assert key.startswith("_") or key in {
            "listing_id", "property_url", "list_price", "status",
            "mls_id", "list_date", "last_sold_date", "last_sold_price",
            "tax", "hoa_fee", "neighborhoods", "neighborhood",
            "agent_name", "broker_name", "office_name", "property_id",
            "list_price_min", "list_price_max",
        }, f"disallowed key in original_data: {key!r}"


# ── Progress Residential ──────────────────────────────────────────────────────

def test_progress_residential_normalize_json_extracts_all_core_fields():
    from services.scrapers.progress_residential_scraper import _normalize_json

    with open(os.path.join(FIXTURES, "progress_residential_api.json"), encoding="utf-8") as f:
        data = json.load(f)

    homes = data["properties"]
    assert len(homes) == 2

    result = _normalize_json(homes[0])
    assert result is not None, "_normalize_json returned None"
    assert result["source"] == "progress_residential"
    assert result["address"] == "789 Pine St"
    assert result["city"] == "Phoenix"
    assert result["state"] == "AZ"
    assert result["bedrooms"] == 3
    assert result["bathrooms"] == 2.0
    assert result["monthly_rent"] == 1950
    assert result["square_footage"] == 1400
    assert abs(result["lat"] - 33.4484) < 0.001


def test_progress_residential_original_data_is_compact():
    from services.scrapers.progress_residential_scraper import _normalize_json

    with open(os.path.join(FIXTURES, "progress_residential_api.json"), encoding="utf-8") as f:
        data = json.load(f)

    result = _normalize_json(data["properties"][0])
    od = json.loads(result["original_data"])
    allowed = {"listing_id", "property_url", "list_price", "status"}
    assert set(od.keys()) <= allowed, f"unexpected keys: {set(od.keys()) - allowed}"
    assert len(result["original_data"].encode()) <= 4096


def test_progress_residential_handles_missing_optional_fields():
    from services.scrapers.progress_residential_scraper import _normalize_json

    minimal = {
        "id": "PR-MIN",
        "address": "1 Test Rd",
        "city": "Phoenix",
        "state": "AZ",
        "rent": 1500,
    }
    result = _normalize_json(minimal)
    assert result is not None
    assert result["bedrooms"] is None
    assert result["bathrooms"] is None
    assert result["square_footage"] is None
    assert result["monthly_rent"] == 1500


# ── image_service helpers ─────────────────────────────────────────────────────

def test_merge_download_stats_appends_summary():
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from routers.scraper import _merge_download_stats

    result = _merge_download_stats("[]", {"ok": 8, "watermarked": 2, "transient": 1})
    features = json.loads(result)
    assert len(features) == 1
    summary = features[0]
    assert "_img_ok=8" in summary
    assert "_img_failed=3" in summary


def test_merge_download_stats_deduplicates_on_repeat_call():
    from routers.scraper import _merge_download_stats

    first = _merge_download_stats("[]", {"ok": 5, "error": 1})
    second = _merge_download_stats(first, {"ok": 10, "low_quality": 2})
    features = json.loads(second)
    img_entries = [f for f in features if f.startswith("_img_")]
    assert len(img_entries) == 1, "should have exactly one _img_ summary entry"
    assert "_img_ok=10" in img_entries[0]


if __name__ == "__main__":
    tests = [
        test_craigslist_rss_parser_extracts_price_and_coords,
        test_craigslist_rss_parser_house_type,
        test_craigslist_original_data_is_compact,
        test_hotpads_normalize_extracts_all_core_fields,
        test_hotpads_original_data_is_compact,
        test_invitation_homes_normalize_decodes_svelte_flat_array,
        test_invitation_homes_original_data_is_compact,
        test_progress_residential_normalize_json_extracts_all_core_fields,
        test_progress_residential_original_data_is_compact,
        test_progress_residential_handles_missing_optional_fields,
        test_merge_download_stats_appends_summary,
        test_merge_download_stats_deduplicates_on_repeat_call,
    ]
    passed = failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"  FAIL  {t.__name__}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
