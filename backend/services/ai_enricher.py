import json
import logging
import os

from services.pricing_service import apply_pricing_rules

logger = logging.getLogger(__name__)


def _deepseek_generate_description(prop) -> str | None:
    try:
        from openai import OpenAI
        api_key = os.environ.get("DEEPSEEK_API_KEY")
        if not api_key:
            return None
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

        bed = prop.bedrooms
        bath = prop.bathrooms
        sqft = prop.square_footage
        ptype = (prop.property_type or "property").lower().replace("_", " ")
        city = prop.city or ""
        state = prop.state or ""
        rent = f"${prop.monthly_rent:,.0f}/mo" if prop.monthly_rent else ""
        year = f"Built {prop.year_built}" if prop.year_built else ""
        amenities = []
        try:
            amenities = json.loads(prop.amenities or "[]")
        except Exception:
            pass
        appliances = []
        try:
            appliances = json.loads(prop.appliances or "[]")
        except Exception:
            pass

        details = "\n".join(filter(None, [
            f"Type: {ptype}",
            f"Bedrooms: {bed}" if bed is not None else None,
            f"Bathrooms: {bath}" if bath is not None else None,
            f"Square footage: {sqft:,} sqft" if sqft else None,
            year,
            f"Location: {city}, {state}" if city and state else (city or state or None),
            f"Monthly rent: {rent}" if rent else None,
            f"Amenities: {', '.join(amenities)}" if amenities else None,
            f"Appliances: {', '.join(appliances)}" if appliances else None,
            f"Parking: {prop.parking}" if prop.parking else None,
            f"Heating: {prop.heating_type}" if prop.heating_type else None,
            f"Cooling: {prop.cooling_type}" if prop.cooling_type else None,
            f"Laundry: {prop.laundry_type}" if prop.laundry_type else None,
        ]))

        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a copywriter for Choice Properties, a tenant-first rental marketplace. "
                        "Write welcoming, honest, professional rental listing descriptions. "
                        "Never mention tours, showings, credit scores, income requirements, or screening criteria. "
                        "Never invent facts. Write 2–4 short paragraphs. No bullet points. No title. "
                        "End with a soft apply-first call to action."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Write a rental listing description for this property:\n\n{details}\n\n"
                        "Return only the description text."
                    ),
                },
            ],
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.warning("ai_enricher: DeepSeek description generation failed: %s", e)
        return None


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
    ("Refrigerator",     ["refrigerator", "fridge"]),
    ("Range/Oven",       ["range", "oven", "stove", "gas stove", "electric stove", "gas range"]),
    ("Dishwasher",       ["dishwasher"]),
    ("Microwave",        ["microwave", "built-in microwave"]),
    ("Washer",           ["washer", "washing machine"]),
    ("Dryer",            ["dryer", "clothes dryer"]),
    ("Garbage Disposal", ["garbage disposal", "disposal"]),
    ("Trash Compactor",  ["trash compactor"]),
    ("Freezer",          ["chest freezer", "standalone freezer"]),
    ("Wine Cooler",      ["wine cooler", "wine fridge", "wine refrigerator"]),
    ("Ice Maker",        ["ice maker", "ice machine"]),
]


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


def _generate_description(prop) -> str:
    bed   = prop.bedrooms
    bath  = prop.bathrooms or prop.total_bathrooms
    sqft  = prop.square_footage
    ptype = (prop.property_type or "property").lower().replace("_", " ")
    city  = prop.city or ""
    state = prop.state or ""

    bed_str = "Studio" if bed == 0 else (f"{bed}-bedroom" if bed else "")
    if bath:
        bath_val = int(bath) if bath == int(bath) else bath
        bath_str = f"{bath_val}-bathroom"
    else:
        bath_str = ""

    descriptor_parts = [p for p in [bed_str, bath_str, ptype] if p]
    descriptor = " ".join(descriptor_parts) if descriptor_parts else "rental property"

    location = f"{city}, {state}" if city and state else city or state or ""

    paragraphs = []

    lead_parts = []
    if sqft:
        lead_parts.append(f"This {descriptor} offers {sqft:,} sq ft of living space{(' in ' + location) if location else ''}.")
    else:
        lead_parts.append(f"This {descriptor} is available for rent{(' in ' + location) if location else ''}.")

    if prop.year_built:
        lead_parts.append(f"Built in {prop.year_built}.")
    if prop.floors and prop.floors > 1:
        lead_parts.append(f"The home spans {prop.floors} stories.")
    if prop.lot_size_sqft:
        acres = round(prop.lot_size_sqft / 43560, 2)
        if acres >= 0.1:
            lead_parts.append(f"The lot is {acres} acres ({prop.lot_size_sqft:,} sq ft).")

    paragraphs.append(" ".join(lead_parts))

    interior = []
    amenities  = _parse_json_list(prop.amenities)
    appliances = _parse_json_list(prop.appliances)
    flooring   = _parse_json_list(prop.flooring)

    if amenities:
        interior.append(f"Features include {', '.join(amenities[:6])}.")
    if appliances:
        interior.append(f"The kitchen comes equipped with {', '.join(appliances[:5])}.")
    if flooring:
        interior.append(f"Flooring: {', '.join(flooring)}.")
    if prop.has_basement:
        interior.append("The property includes a full basement.")
    if prop.half_bathrooms:
        interior.append(f"There {'is' if prop.half_bathrooms == 1 else 'are'} also {prop.half_bathrooms} half bath{'s' if prop.half_bathrooms > 1 else ''}.")

    if interior:
        paragraphs.append(" ".join(interior))

    systems = []
    if prop.heating_type:
        systems.append(f"{prop.heating_type} heating")
    if prop.cooling_type or prop.has_central_air:
        systems.append(f"{prop.cooling_type or 'central air'} cooling")
    if prop.laundry_type:
        laundry_label = {
            "In-unit": "in-unit washer/dryer",
            "Hookups": "washer/dryer hookups",
            "Shared":  "shared laundry on-site",
        }.get(prop.laundry_type, prop.laundry_type.lower() + " laundry")
        systems.append(laundry_label)

    utilities = _parse_json_list(prop.utilities_included)
    if systems:
        paragraphs.append(f"The home features {', '.join(systems)}.")
    if utilities:
        paragraphs.append(f"Utilities included in rent: {', '.join(utilities)}.")

    outdoor = []
    if prop.garage_spaces:
        n = prop.garage_spaces
        outdoor.append(f"{'a ' + str(n) + '-car' if n > 1 else 'a'} garage")
    elif prop.parking:
        outdoor.append(f"parking: {prop.parking.lower()}")

    if outdoor:
        paragraphs.append(f"Outdoor amenities include {', '.join(outdoor)}.")

    policy = []
    if prop.pets_allowed is True:
        pet_types = _parse_json_list(prop.pet_types_allowed)
        pet_str = f"Pets welcome ({', '.join(t.lower() for t in pet_types)})" if pet_types else "Pets welcome"
        if prop.pet_weight_limit:
            pet_str += f" — up to {prop.pet_weight_limit} lbs"
        policy.append(pet_str + ".")
    elif prop.pets_allowed is False:
        policy.append("No pets permitted.")

    if prop.smoking_allowed is False:
        policy.append("Non-smoking property.")

    if prop.minimum_lease_months:
        policy.append(f"Minimum lease: {prop.minimum_lease_months} months.")
    elif prop.lease_terms:
        terms = _parse_json_list(prop.lease_terms)
        if terms:
            policy.append(f"Lease terms available: {', '.join(terms)}.")

    if policy:
        paragraphs.append(" ".join(policy))

    financial = []
    if prop.security_deposit:
        financial.append(f"Security deposit: ${prop.security_deposit:,}")
    if prop.last_months_rent:
        financial.append(f"last month's rent: ${prop.last_months_rent:,}")
    if prop.pet_deposit:
        financial.append(f"pet deposit: ${prop.pet_deposit:,}")
    if prop.admin_fee:
        financial.append(f"admin fee: ${prop.admin_fee:,}")
    if prop.move_in_special:
        financial.append(f"Move-in special: {prop.move_in_special}")

    if financial:
        paragraphs.append(". ".join(f.capitalize() for f in financial) + ".")

    if prop.available_date:
        paragraphs.append(f"Available starting {prop.available_date}.")

    return "\n\n".join(p for p in paragraphs if p)


def _extract_features_from_text(text: str) -> tuple[list, list]:
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


def _infer_pet_policy(text: str):
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


def _classify_property_type(prop) -> str | None:
    searchable = " ".join(filter(None, [
        prop.description or "",
        prop.title or "",
        prop.address or "",
    ])).lower()

    for ptype, keywords in PROPERTY_TYPE_KEYWORDS.items():
        if any(k in searchable for k in keywords):
            return ptype
    return None


def enrich_property(prop_id: str, repo) -> None:
    from database.repository import AiEnrichmentLog

    try:
        prop = repo.get(prop_id)
        if not prop:
            return

        tasks = _decide_tasks(prop)

        changed  = False
        log_rows = []

        pricing_changed = apply_pricing_rules(prop)
        if pricing_changed:
            if prop.monthly_rent is not None:
                log_rows.append(AiEnrichmentLog(
                    property_id=prop_id,
                    field="monthly_rent",
                    method="pricing_rule",
                    ai_value=str(prop.monthly_rent),
                ))
            if prop.application_fee is not None:
                log_rows.append(AiEnrichmentLog(
                    property_id=prop_id,
                    field="application_fee",
                    method="pricing_rule",
                    ai_value=str(prop.application_fee),
                ))
            changed = True

        if not tasks and not pricing_changed:
            return

        if "generate_description" in tasks:
            new_desc = _deepseek_generate_description(prop)
            method = "deepseek_llm"
            if not new_desc:
                new_desc = _generate_description(prop)
                method = "template"
            if new_desc:
                log_rows.append(AiEnrichmentLog(
                    property_id=prop_id,
                    field="description",
                    method=method,
                    ai_value=new_desc[:500],
                ))
                prop.description = new_desc
                _add_inferred_to_prop(prop, f"description_{method}_generated")
                changed = True
                logger.info("ai_enricher: generated description (%s) for %s", method, prop_id)

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
            repo.save(prop)
            repo.add_all_logs(log_rows)
            logger.info(
                "ai_enricher: completed %d task(s) for %s",
                len(tasks), prop_id,
            )

    except Exception as e:
        logger.warning("ai_enricher: failed for %s: %s", prop_id, e)
