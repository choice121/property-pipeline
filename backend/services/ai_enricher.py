"""
Free enrichment layer — no external APIs or paid services.

Uses template-based description generation and expanded rule-based extraction
to fill gaps that scraped data and the basic enrichers couldn't cover.
Same interface as the original proposal (enrich_property / _decide_tasks)
so it can be swapped for a real LLM later with zero router changes.
"""

import json
import logging

logger = logging.getLogger(__name__)


# ── Property type keyword classifier ──────────────────────────────────────────

PROPERTY_TYPE_KEYWORDS = {
    "apartment":  ["apartment", "apt ", "flat ", "unit in building", "apartment complex",
                   "multi-unit", "studio apartment"],
    "condo":      ["condo", "condominium", "co-op"],
    "townhouse":  ["townhouse", "town home", "townhome", "row home", "row house",
                   "end unit", "attached home"],
    "mobile":     ["mobile home", "manufactured home", "trailer", "manufactured housing"],
    "house":      ["single family", "single-family", "detached home", "detached house",
                   "ranch", "colonial", "split level", "split-level", "bungalow",
                   "craftsman", "cape cod", "tudor", "victorian"],
}


# ── Extended amenity/appliance extraction patterns ─────────────────────────────

EXTENDED_AMENITIES = [
    ("Pool",             ["pool", "swimming pool", "community pool"]),
    ("Hot Tub",          ["hot tub", "jacuzzi", "whirlpool"]),
    ("Gym / Fitness",    ["gym", "fitness center", "fitness room", "workout room", "exercise room"]),
    ("Basement",         ["basement", "finished basement", "lower level"]),
    ("Central Air",      ["central air", "central a/c", "central ac", "central cooling"]),
    ("Garage",           ["garage", "attached garage", "detached garage"]),
    ("Carport",          ["carport", "covered parking"]),
    ("Fenced Yard",      ["fenced yard", "fenced backyard", "privacy fence"]),
    ("Patio",            ["patio", "outdoor patio"]),
    ("Deck",             ["deck", "back deck", "front deck"]),
    ("Balcony",          ["balcony", "private balcony", "terrace"]),
    ("Fireplace",        ["fireplace", "wood-burning fireplace", "gas fireplace"]),
    ("Walk-in Closet",   ["walk-in closet", "walk in closet", "large closet"]),
    ("Hardwood Floors",  ["hardwood floor", "hardwood floors", "hardwood flooring"]),
    ("Storage",          ["storage unit", "storage room", "extra storage"]),
    ("Elevator",         ["elevator", "lift"]),
    ("Doorman",          ["doorman", "concierge"]),
    ("Rooftop",          ["rooftop", "roof deck", "rooftop access"]),
    ("EV Charging",      ["ev charging", "electric vehicle charging", "tesla charger"]),
    ("Smart Home",       ["smart home", "smart thermostat", "nest", "smart lock"]),
    ("Security System",  ["security system", "alarm system", "ring doorbell", "ring camera"]),
    ("Wheelchair Access",["wheelchair", "ada", "accessible", "handicap accessible"]),
    ("Den / Office",     ["den", "home office", "study", "office space"]),
]

EXTENDED_APPLIANCES = [
    ("Refrigerator",      ["refrigerator", "fridge"]),
    ("Range/Oven",        ["range", "oven", "stove", "gas stove", "electric stove", "gas range"]),
    ("Dishwasher",        ["dishwasher"]),
    ("Microwave",         ["microwave", "built-in microwave"]),
    ("Washer",            ["washer", "washing machine"]),
    ("Dryer",             ["dryer", "clothes dryer"]),
    ("Garbage Disposal",  ["garbage disposal", "disposal"]),
    ("Trash Compactor",   ["trash compactor"]),
    ("Freezer",           ["chest freezer", "standalone freezer"]),
    ("Wine Cooler",       ["wine cooler", "wine fridge", "wine refrigerator"]),
    ("Ice Maker",         ["ice maker", "ice machine"]),
]


# ── Helpers ────────────────────────────────────────────────────────────────────

def _parse_json_list(val) -> list:
    if not val:
        return []
    if isinstance(val, list):
        return val
    try:
        result = json.loads(val)
        return result if isinstance(result, list) else []
    except Exception:
        return []


def _add_inferred_to_prop(prop, feature: str):
    try:
        existing = json.loads(prop.inferred_features or "[]")
    except Exception:
        existing = []
    existing.append(feature)
    prop.inferred_features = json.dumps(existing)


# ── Task decision ──────────────────────────────────────────────────────────────

def _decide_tasks(prop) -> list[str]:
    tasks = []

    desc = prop.description or ""
    if not desc or len(desc.strip()) < 50:
        tasks.append("generate_description")

    if desc and len(desc.strip()) >= 30:
        existing_amenities = _parse_json_list(prop.amenities)
        existing_appliances = _parse_json_list(prop.appliances)
        if len(existing_amenities) < 3 or len(existing_appliances) < 2:
            tasks.append("extract_features")

    if prop.pets_allowed is None and desc and len(desc.strip()) >= 20:
        tasks.append("infer_pet_policy")

    raw_type = (prop.property_type or "").upper()
    if not prop.property_type or raw_type in ("UNKNOWN", "OTHER", ""):
        tasks.append("classify_property_type")

    return tasks


# ── Description generator ──────────────────────────────────────────────────────

def _generate_description(prop) -> str:
    bed   = prop.bedrooms
    bath  = prop.bathrooms or prop.total_bathrooms
    sqft  = prop.square_footage
    ptype = (prop.property_type or "property").lower().replace("_", " ")
    city  = prop.city or ""
    state = prop.state or ""

    bed_str  = f"{bed}-bedroom" if bed else ""
    if bath:
        bath_val = int(bath) if bath == int(bath) else bath
        bath_str = f"{bath_val}-bathroom"
    else:
        bath_str = ""

    descriptor_parts = [p for p in [bed_str, bath_str, ptype] if p]
    descriptor = " ".join(descriptor_parts) if descriptor_parts else "rental property"

    if sqft:
        lead = f"This {descriptor} offers {sqft:,} sq ft of living space"
    else:
        lead = f"This {descriptor} is available for rent"

    if city and state:
        lead += f" in {city}, {state}."
    elif city:
        lead += f" in {city}."
    else:
        lead += "."

    sentences = [lead]

    amenities  = _parse_json_list(prop.amenities)
    appliances = _parse_json_list(prop.appliances)

    if amenities:
        sentences.append(f"Features include {', '.join(amenities[:5])}.")
    if appliances:
        sentences.append(f"The kitchen comes equipped with {', '.join(appliances[:4])}.")

    highlights = []
    if prop.has_basement:
        highlights.append("a full basement")
    if prop.has_central_air:
        highlights.append("central air conditioning")
    if prop.garage_spaces:
        n = prop.garage_spaces
        highlights.append(f"a {n}-car garage" if n > 1 else "garage parking")
    if prop.laundry_type:
        highlights.append(f"{prop.laundry_type.lower()} laundry")
    if prop.heating_type:
        highlights.append(f"{prop.heating_type.lower()} heat")
    if prop.cooling_type and not prop.has_central_air:
        highlights.append(f"{prop.cooling_type.lower()} cooling")

    if highlights:
        sentences.append(f"The home also features {', '.join(highlights)}.")

    if prop.year_built:
        sentences.append(f"Built in {prop.year_built}.")

    if prop.pets_allowed is True:
        pet_types = _parse_json_list(prop.pet_types_allowed)
        if pet_types:
            sentences.append(f"Pets welcome — {', '.join(t.lower() for t in pet_types)} allowed.")
        else:
            sentences.append("Pets welcome.")
    elif prop.pets_allowed is False:
        sentences.append("No pets permitted.")

    if prop.security_deposit:
        sentences.append(f"Security deposit: ${prop.security_deposit:,}.")

    utilities = _parse_json_list(prop.utilities_included)
    if utilities:
        sentences.append(f"Utilities included: {', '.join(utilities)}.")

    if prop.available_date:
        sentences.append(f"Available {prop.available_date}.")

    return " ".join(sentences)


# ── Feature extractor ─────────────────────────────────────────────────────────

def _extract_features_from_text(text: str) -> tuple[list, list]:
    """Returns (new_amenities, new_appliances) found in text."""
    searchable = text.lower()
    found_amenities = [
        label for label, patterns in EXTENDED_AMENITIES
        if any(p in searchable for p in patterns)
    ]
    found_appliances = [
        label for label, patterns in EXTENDED_APPLIANCES
        if any(p in searchable for p in patterns)
    ]
    return found_amenities, found_appliances


# ── Pet policy from text ───────────────────────────────────────────────────────

def _infer_pet_policy(text: str):
    """Returns True (allowed), False (denied), or None (unclear)."""
    t = text.lower()
    no_pets  = ["no pets", "no animals", "pet-free", "pets not allowed",
                "no dogs allowed", "no cats allowed", "pet free building",
                "sorry no pets", "pets are not", "no pet"]
    yes_pets = ["pets ok", "pet friendly", "pets welcome", "dogs allowed",
                "cats allowed", "pets allowed", "pet-friendly", "pets considered",
                "pets negotiable", "small pets", "up to", "lbs allowed"]
    if any(k in t for k in no_pets):
        return False
    if any(k in t for k in yes_pets):
        return True
    return None


# ── Property type classifier ───────────────────────────────────────────────────

def _classify_property_type(prop) -> str | None:
    """
    Classify property type from title, description, and address keywords.
    Returns a normalized type string or None if uncertain.
    """
    searchable = " ".join(filter(None, [
        prop.description or "",
        prop.title or "",
        prop.address or "",
    ])).lower()

    for ptype, keywords in PROPERTY_TYPE_KEYWORDS.items():
        if any(k in searchable for k in keywords):
            return ptype
    return None


# ── Main enrichment entry point ────────────────────────────────────────────────

def enrich_property(prop_id: str, db) -> None:
    """
    Run free, rule-based enrichment on a property.
    Reads from and writes directly to the DB record.
    Never raises — always best-effort.
    """
    from database.models import AiEnrichmentLog, Property

    try:
        prop = db.query(Property).filter(Property.id == prop_id).first()
        if not prop:
            return

        tasks = _decide_tasks(prop)
        if not tasks:
            return

        changed   = False
        log_rows  = []

        if "generate_description" in tasks:
            new_desc = _generate_description(prop)
            if new_desc:
                log_rows.append(AiEnrichmentLog(
                    property_id=prop_id,
                    field="description",
                    method="template",
                    ai_value=new_desc[:500],
                ))
                prop.description = new_desc
                _add_inferred_to_prop(prop, "description_template_generated")
                changed = True
                logger.info("ai_enricher: generated description for %s", prop_id)

        if "extract_features" in tasks:
            text = prop.description or ""
            new_amenities, new_appliances = _extract_features_from_text(text)

            existing_amenities  = _parse_json_list(prop.amenities)
            existing_appliances = _parse_json_list(prop.appliances)

            merged_amenities  = list(dict.fromkeys(existing_amenities  + new_amenities))
            merged_appliances = list(dict.fromkeys(existing_appliances + new_appliances))

            if merged_amenities != existing_amenities:
                log_rows.append(AiEnrichmentLog(
                    property_id=prop_id,
                    field="amenities",
                    method="rule_extraction",
                    ai_value=json.dumps(merged_amenities),
                ))
                prop.amenities = json.dumps(merged_amenities)
                _add_inferred_to_prop(prop, "amenities_rule_extracted")
                changed = True

            if merged_appliances != existing_appliances:
                log_rows.append(AiEnrichmentLog(
                    property_id=prop_id,
                    field="appliances",
                    method="rule_extraction",
                    ai_value=json.dumps(merged_appliances),
                ))
                prop.appliances = json.dumps(merged_appliances)
                _add_inferred_to_prop(prop, "appliances_rule_extracted")
                changed = True

        if "infer_pet_policy" in tasks:
            result = _infer_pet_policy(prop.description or "")
            if result is not None:
                log_rows.append(AiEnrichmentLog(
                    property_id=prop_id,
                    field="pets_allowed",
                    method="rule_extraction",
                    ai_value=str(result),
                ))
                prop.pets_allowed = result
                _add_inferred_to_prop(prop, "pets_rule_inferred")
                changed = True

        if "classify_property_type" in tasks:
            ptype = _classify_property_type(prop)
            if ptype:
                log_rows.append(AiEnrichmentLog(
                    property_id=prop_id,
                    field="property_type",
                    method="rule_classification",
                    ai_value=ptype,
                ))
                prop.property_type = ptype
                _add_inferred_to_prop(prop, "property_type_rule_classified")
                changed = True

        if changed:
            db.add_all(log_rows)
            db.commit()
            logger.info(
                "ai_enricher: completed %d task(s) for %s",
                len(tasks), prop_id,
            )

    except Exception as e:
        logger.warning("ai_enricher: failed for %s: %s", prop_id, e)
        try:
            db.rollback()
        except Exception:
            pass
