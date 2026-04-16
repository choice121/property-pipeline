import json
import logging

from services.ai_client import PLATFORM_CONTEXT, PROMPT_VERSION, call_deepseek
from services.pricing_service import apply_pricing_rules

logger = logging.getLogger(__name__)


# ── Property type keyword classification ───────────────────────────────────────

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

SIGNIFICANT_FIELDS = frozenset([
    "bedrooms", "bathrooms", "property_type", "monthly_rent",
    "amenities", "appliances", "description", "city", "state",
])


# ── JSON list helpers ──────────────────────────────────────────────────────────

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


# ── Task decision logic ────────────────────────────────────────────────────────

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

    title = (prop.title or "").strip()
    if not title or _is_generic_title(title):
        tasks.append("generate_title")

    return tasks


def _is_generic_title(title: str) -> bool:
    import re
    t = title.lower().strip()
    generic_patterns = [
        r'^\d+br?\s+(apartment|house|condo|townhouse|home|rental|property)\s+in\s+\w+$',
        r'^(studio|apartment|house|condo|townhouse|home|rental)\s+in\s+\w+',
        r'^(beautiful|nice|great|spacious|cozy)\s+\d+\s*(br|bed|bedroom)',
    ]
    for pat in generic_patterns:
        if re.match(pat, t):
            return True
    if len(t) < 15:
        return True
    return False


# ── Description generation ─────────────────────────────────────────────────────

def _llm_generate_description(prop) -> str | None:
    """
    Generate a listing description using the shared PLATFORM_CONTEXT and
    the same prompt quality as the manual rewrite endpoint. Falls back to
    the template builder if the LLM call fails.
    """
    try:
        bed = prop.bedrooms
        bath = prop.bathrooms
        sqft = prop.square_footage
        ptype = (prop.property_type or "property").lower().replace("_", " ")
        city = prop.city or ""
        state = prop.state or ""
        rent = f"${prop.monthly_rent:,.0f}/mo" if prop.monthly_rent else ""
        year = f"Built {prop.year_built}" if prop.year_built else ""

        amenities = _parse_json_list(prop.amenities)
        appliances = _parse_json_list(prop.appliances)

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

        user_prompt = f"""Write a rental listing description for this property.

PROPERTY DATA:
{details}

HARD RULES:
1. NEVER mention tours, viewings, showings, or "seeing the property in person."
2. NEVER include credit scores, income requirements, screening criteria, or "no Section 8."
3. NEVER say "no pets." Omit pet policy or say "ask about our pet policy."
4. NEVER invent facts. Only use what is in the data above.
5. Structure: 2–4 paragraphs. No bullet points. No title. Body text only.
6. End with a soft apply-first call to action.

Return ONLY the description text."""

        return call_deepseek(PLATFORM_CONTEXT, user_prompt, temperature=0.7)

    except Exception as e:
        logger.warning("ai_enricher: LLM description generation failed: %s", e)
        return None


def _template_generate_description(prop) -> str:
    """
    Rule-based fallback description builder. Used only when the LLM call fails.
    """
    bed = prop.bedrooms
    bath = prop.bathrooms or prop.total_bathrooms
    sqft = prop.square_footage
    ptype = (prop.property_type or "property").lower().replace("_", " ")
    city = prop.city or ""
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
    amenities = _parse_json_list(prop.amenities)
    appliances = _parse_json_list(prop.appliances)
    flooring = _parse_json_list(prop.flooring)

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
            "Shared": "shared laundry on-site",
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


# ── LLM Feature Extraction ─────────────────────────────────────────────────────

def _llm_extract_features(text: str, existing_amenities: list, existing_appliances: list) -> tuple[list, list]:
    """
    Use the LLM to extract amenities and appliances from listing text.
    Understands nuanced language that keyword lists miss.
    Falls back to empty lists if the call fails.
    """
    if not text or len(text.strip()) < 20:
        return [], []

    user_prompt = f"""You are a property data extractor. Read the rental listing text below and extract all mentioned amenities and appliances.

LISTING TEXT:
{text}

ALREADY CAPTURED (do not duplicate):
- Amenities: {', '.join(existing_amenities) if existing_amenities else 'none yet'}
- Appliances: {', '.join(existing_appliances) if existing_appliances else 'none yet'}

EXTRACTION RULES:
- Amenities: physical features and services (Pool, Gym, Garage, Balcony, Patio, Yard, Fireplace, EV Charging, Storage, Elevator, Doorman, Walk-in Closet, Hardwood Floors, Central Air, Basement, Hot Tub, Rooftop, Security System, Smart Home, etc.)
- Appliances: kitchen and laundry equipment (Refrigerator, Dishwasher, Washer, Dryer, Microwave, Range/Oven, Garbage Disposal, Ice Maker, Wine Cooler, etc.)
- Understand nuanced language: "covered 2-car parking structure with EV rough-in" → ["Garage", "EV Charging"]
- Use standard names (capitalize properly)
- Only include what is clearly mentioned or strongly implied
- Do NOT duplicate items already captured

Return a JSON object:
- "amenities": array of new amenity names not already captured
- "appliances": array of new appliance names not already captured"""

    try:
        raw = call_deepseek(PLATFORM_CONTEXT, user_prompt, temperature=0.1, json_mode=True)
        result = json.loads(raw)
        return result.get("amenities", []), result.get("appliances", [])
    except Exception as e:
        logger.warning("ai_enricher: LLM feature extraction failed: %s", e)
        return [], []


# ── Pet policy inference (rule-based, no LLM needed) ──────────────────────────

def _infer_pet_policy(text: str):
    t = text.lower()
    no_pets = ["no pets", "no animals", "pet-free", "pets not allowed",
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


# ── Property type classification (rule-based) ──────────────────────────────────

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


# ── Title generation ───────────────────────────────────────────────────────────

def _llm_generate_title(prop) -> str | None:
    try:
        bed = prop.bedrooms
        ptype = (prop.property_type or "home").lower().replace("_", " ")
        city = prop.city or ""
        state = prop.state or ""
        amenities = _parse_json_list(prop.amenities)
        parking = prop.parking or ""
        laundry = prop.laundry_type or ""
        sqft = prop.square_footage

        standouts = []
        if "Garage" in amenities or (parking and "garage" in parking.lower()):
            standouts.append("Garage")
        if "In-unit" in laundry or "In Unit" in laundry:
            standouts.append("In-Unit Laundry")
        if "Pool" in amenities:
            standouts.append("Pool")
        if "Balcony" in amenities:
            standouts.append("Balcony")
        if "Yard" in amenities or "Fenced Yard" in amenities:
            standouts.append("Private Yard")
        if sqft and sqft > 1500:
            standouts.append(f"{sqft:,} sqft")
        if prop.pets_allowed:
            standouts.append("Pet-Friendly")

        bed_str = "Studio" if bed == 0 else (f"{bed}BR" if bed else "")
        location = city or (state or "")

        user_prompt = (
            f"Property: {bed_str} {ptype} in {location}\n"
            + (f"Standout features: {', '.join(standouts[:3])}\n" if standouts else "")
            + "Generate a compelling, specific rental listing title (under 80 chars, Title Case, "
            + "no tour/screening language, no invented facts). Return ONLY the title text."
        )

        result = call_deepseek(PLATFORM_CONTEXT, user_prompt, temperature=0.6)
        title = result.strip().strip('"').strip("'")
        return title if len(title) > 10 else None

    except Exception as e:
        logger.warning("ai_enricher: title generation failed: %s", e)
        return None


# ── Main enrichment entry point ────────────────────────────────────────────────

def enrich_property(prop_id: str, repo) -> None:
    from database.repository import AiEnrichmentLog

    try:
        prop = repo.get(prop_id)
        if not prop:
            return

        tasks = _decide_tasks(prop)

        changed = False
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
            new_desc = _llm_generate_description(prop)
            method = f"deepseek_llm_{PROMPT_VERSION}"
            if not new_desc:
                new_desc = _template_generate_description(prop)
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
            existing_amenities = _parse_json_list(prop.amenities)
            existing_appliances = _parse_json_list(prop.appliances)

            new_amenities, new_appliances = _llm_extract_features(
                prop.description or "",
                existing_amenities,
                existing_appliances,
            )

            merged_amenities = list(dict.fromkeys(existing_amenities + new_amenities))
            merged_appliances = list(dict.fromkeys(existing_appliances + new_appliances))

            if merged_amenities != existing_amenities:
                log_rows.append(AiEnrichmentLog(
                    property_id=prop_id,
                    field="amenities",
                    method=f"llm_extraction_{PROMPT_VERSION}",
                    ai_value=json.dumps(merged_amenities),
                ))
                prop.amenities = json.dumps(merged_amenities)
                _add_inferred_to_prop(prop, "amenities_llm_extracted")
                changed = True

            if merged_appliances != existing_appliances:
                log_rows.append(AiEnrichmentLog(
                    property_id=prop_id,
                    field="appliances",
                    method=f"llm_extraction_{PROMPT_VERSION}",
                    ai_value=json.dumps(merged_appliances),
                ))
                prop.appliances = json.dumps(merged_appliances)
                _add_inferred_to_prop(prop, "appliances_llm_extracted")
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

        if "generate_title" in tasks:
            new_title = _llm_generate_title(prop)
            if new_title:
                log_rows.append(AiEnrichmentLog(
                    property_id=prop_id,
                    field="title",
                    method=f"ai_title_{PROMPT_VERSION}",
                    ai_value=new_title[:500],
                ))
                prop.title = new_title
                _add_inferred_to_prop(prop, "title_ai_generated")
                changed = True
                logger.info("ai_enricher: generated title for %s", prop_id)

        if changed:
            repo.save(prop)
            repo.add_all_logs(log_rows)
            logger.info(
                "ai_enricher: completed %d task(s) for %s",
                len(tasks), prop_id,
            )

    except Exception as e:
        logger.warning("ai_enricher: failed for %s: %s", prop_id, e)
