import json
from types import SimpleNamespace

import pytest

from services import publisher_service


def _property(**overrides):
    values = {
        "id": "PP-TEST",
        "choice_property_id": None,
        "title": "Marketing title that must not publish",
        "address": "123 Main St",
        "city": "Austin",
        "state": "TX",
        "zip": "78701",
        "county": "Travis",
        "lat": 30.2672,
        "lng": -97.7431,
        "neighborhood": None,
        "property_type": "APARTMENT",
        "year_built": 2020,
        "floors": 4,
        "unit_number": None,
        "total_units": 120,
        "bedrooms": 2,
        "bathrooms": 1.5,
        "half_bathrooms": 1,
        "total_bathrooms": 1.5,
        "square_footage": 900,
        "lot_size_sqft": None,
        "garage_spaces": None,
        "has_basement": None,
        "has_central_air": None,
        "monthly_rent": 1800,
        "security_deposit": 2400,
        "last_months_rent": None,
        "application_fee": 0,
        "pet_deposit": 300,
        "admin_fee": None,
        "move_in_special": "Available now",
        "available_date": "2026-11-15",
        "lease_terms": '["12 months"]',
        "minimum_lease_months": 12,
        "pets_allowed": True,
        "pet_types_allowed": '["dogs"]',
        "pet_weight_limit": 50,
        "pet_details": "Cats and dogs considered",
        "smoking_allowed": True,
        "utilities_included": "[]",
        "parking": None,
        "parking_fee": None,
        "amenities": "[]",
        "appliances": "[]",
        "flooring": "[]",
        "heating_type": None,
        "cooling_type": None,
        "laundry_type": None,
        "virtual_tour_url": "https://example.com/tour",
        "description": (
            "Bright apartment with original oak flooring. Rent is $1,650 per month. "
            "Security deposit is $2,400. Available November 15th. Pets are considered. "
            "No smoking. Tour this home today. Call agent at 555-123-4567."
        ),
        "original_data": json.dumps({
            "building_name": "Main Street Apartments",
            "is_multi_unit": True,
            "price_range": "$1,400-$2,400",
            "unit_options": [
                {
                    "unit_number": "A101",
                    "unit_floor": 1,
                    "bedrooms": 2,
                    "bathrooms": 1.5,
                    "square_footage": 900,
                    "monthly_rent": 1800,
                    "photo_urls": ["https://cdn.example.com/unit-A101.jpg", "javascript:alert(1)"],
                    "available_date": "2026-11-15",
                    "pet_policy": "Cats allowed",
                },
                {
                    "source_kind": "floor_plan",
                    "floor_plan_name": "The Oak",
                    "bedrooms": 1,
                    "bathrooms": 1,
                    "square_footage": 700,
                    "starting_rent": 1450,
                    "rent_basis": "base_rent",
                },
            ],
            "media": [
                {
                    "kind": "floor_plan",
                    "title": "Two Bedroom",
                    "url": "https://cdn.example.com/plan.jpg",
                },
                {
                    "kind": "tour",
                    "url": "https://example.com/tour",
                },
            ],
        }),
        "original_image_urls": json.dumps([
            {"url": "https://cdn.example.com/hero.jpg", "width": 1200, "height": 800},
            "https://cdn.example.com/living-room.jpg",
        ]),
        "local_image_paths": "[]",
        "data_quality_score": 90,
        "nearby_schools": "[]",
        "poster_landlord_id": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_clean_description_preserves_authentic_facts_and_strips_policy_content():
    cleaned = publisher_service._clean_description(
        "Original source wording: renovated kitchen and hardwood floors. "
        "Rent is $1,650 per month. Security deposit is $2,400. "
        "Available now. Pets are welcome. No smoking. "
        "Beware of rental scams and do not pay by Zelle. "
        "Call agent at 555-123-4567. Application fee is waived."
    )

    assert cleaned == (
        "Original source wording: renovated kitchen and hardwood floors. "
        "Rent is $1,650 per month. "
        "Application Fee: $50. Submit your rental application today at Choice Properties."
    )


def test_publish_record_keeps_multifamily_type_and_sanitized_unit_inventory(monkeypatch):
    monkeypatch.setattr(publisher_service, "_get_landlord_id", lambda: None)
    record = publisher_service._build_supabase_record(_property(), [])

    assert record["title"] == "123 Main St, Austin, TX 78701"
    assert record["property_type"] == "apartment"
    assert record["status"] == "private_placement"
    assert record["application_fee"] == 50
    assert record["security_deposit"] == 1450
    assert record["pets_allowed"] is None
    assert record["pet_types_allowed"] is None
    assert record["smoking_allowed"] is None
    assert record["available_date"] is None
    assert record["lease_terms"] is None
    assert record["description"].endswith(
        "Application Fee: $50. Submit your rental application today at Choice Properties."
    )
    assert "$1,650 per month" in record["description"]
    assert "unit_options" in record
    assert record["unit_options"] == [
        {
            "source_kind": "unit",
            "source_order": 0,
            "source_id": "0-A101",
            "unit_number": "A101",
            "unit_floor": "1",
            "building_name": None,
            "floor_plan_name": None,
            "bedrooms": 2,
            "bathrooms": 1.5,
            "square_footage": 900,
            "monthly_rent": 1800,
            "rent_basis": None,
            "photo_urls": ["https://cdn.example.com/unit-A101.jpg"],
        },
        {
            "source_kind": "floor_plan",
            "source_order": 1,
            "source_id": "1-The Oak",
            "floor_plan_name": "The Oak",
            "building_name": None,
            "bedrooms": 1,
            "bathrooms": 1,
            "square_footage": 700,
            "starting_rent": 1450,
            "rent_basis": "base_rent",
            "image_url": None,
        },
    ]
    assert record["building_name"] == "Main Street Apartments"
    assert record["is_multi_unit"] is True


def test_unit_option_normalization_does_not_promote_starting_rent_or_unclassified_rows():
    options = publisher_service._build_unit_options({
        "unit_options": [
            {"source_kind": "unit", "unit_number": "B204", "starting_rent": 1600, "building_name": "North Tower"},
            {
                "source_kind": "unit",
                "unit_number": "B204",
                "monthly_rent": 1600,
                "unit_floor": "2",
                "photos": ["https://cdn.example.com/b204.jpg", "javascript:alert(1)"],
            },
            {"source_kind": "floor_plan", "floor_plan_name": "Studio", "starting_rent": 1200, "image_url": "https://cdn.example.com/studio.jpg"},
            {"source_kind": "unit", "unit_number": "Apartment 2B", "monthly_rent": 1400},
            {"bedrooms": 2, "bathrooms": 1, "square_footage": 900},
        ],
    })

    assert options == [
        {
            "source_kind": "unit",
            "source_order": 0,
            "unit_number": "B204",
            "building_name": "North Tower",
            "monthly_rent": 1600,
            "unit_floor": "2",
            "photo_urls": ["https://cdn.example.com/b204.jpg"],
        },
        {
            "source_kind": "floor_plan",
            "source_order": 2,
            "floor_plan_name": "Studio",
            "starting_rent": 1200,
            "image_url": "https://cdn.example.com/studio.jpg",
        },
    ]


def test_publisher_prefers_original_cdn_photo_order_and_publishes_floor_plan_media(monkeypatch):
    class FakeQuery:
        def __init__(self, client, table):
            self.client = client
            self.table = table
            self.payload = None

        def insert(self, payload):
            self.payload = payload
            self.client.inserted[self.table] = payload
            return self

        def execute(self):
            if self.table == "properties":
                return SimpleNamespace(data=[{"id": "prop-test1234"}])
            return SimpleNamespace(data=[])

    class FakeClient:
        def __init__(self):
            self.inserted = {}

        def table(self, name):
            return FakeQuery(self, name)

    class FakeRepo:
        deleted = None

        def delete(self, prop_id):
            self.deleted = prop_id

    client = FakeClient()
    repo = FakeRepo()
    monkeypatch.setattr(publisher_service, "_get_supabase", lambda: client)
    monkeypatch.setattr(publisher_service, "_get_landlord_id", lambda: None)
    monkeypatch.setattr(publisher_service, "_check_duplicate_in_supabase", lambda *_: None)
    monkeypatch.setattr(
        publisher_service,
        "_upload_images_to_imagekit",
        lambda *_: pytest.fail("original CDN photos must not be re-uploaded"),
    )

    result = publisher_service.publish(_property(), repo, inventory_reviewed=True)

    assert result["listing_status"] == "private_placement"
    assert result["photo_count"] == 2
    assert result["floor_plan_count"] == 1
    assert repo.deleted == "PP-TEST"
    photos = client.inserted["property_photos"]
    assert [photo["url"] for photo in photos] == [
        "https://cdn.example.com/hero.jpg",
        "https://cdn.example.com/living-room.jpg",
    ]
    assert photos[0]["is_hero"] is True
    assert photos[0]["display_order"] == 1
    assert client.inserted["property_media"][0]["kind"] == "floor_plan"
    assert client.inserted["property_media"][0]["url"] == "https://cdn.example.com/plan.jpg"
    assert client.inserted["property_units"][0]["monthly_rent"] == 1800
    assert client.inserted["property_units"][0]["photo_urls"] == ["https://cdn.example.com/unit-A101.jpg"]
    assert client.inserted["property_units"][0]["review_status"] == "approved"
    assert client.inserted["property_floor_plans"][0]["starting_rent"] == 1450
    assert client.inserted["property_floor_plans"][0]["review_status"] == "approved"


def test_public_visibility_requires_explicit_status(monkeypatch):
    monkeypatch.setattr(publisher_service, "_get_landlord_id", lambda: None)
    private = publisher_service._build_supabase_record(_property(), [])
    public = publisher_service._build_supabase_record(_property(), [], listing_status="active")

    assert private["status"] == "private_placement"
    assert public["status"] == "active"
    with pytest.raises(ValueError, match="visibility"):
        publisher_service.publish(_property(), object(), listing_status=["active"])


def test_publisher_requires_inventory_review_before_apartment_publication():
    with pytest.raises(ValueError, match="Review and confirm apartment"):
        publisher_service.publish(_property(), object())
