import logging

logger = logging.getLogger(__name__)

US_STATE_ABBREVS = {
    "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA",
    "KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ",
    "NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT",
    "VA","WA","WV","WI","WY","DC",
}

ALLOWED_PROPERTY_TYPES = {
    "house", "apartment", "condo", "townhouse", "mobile", "land",
    "SINGLE_FAMILY", "APARTMENT", "APARTMENTS", "CONDO", "CONDOS",
    "CONDO_TOWNHOME", "TOWNHOMES", "TOWNHOME", "MULTI_FAMILY",
    "DUPLEX_TRIPLEX", "MOBILE", "LAND", "FARM",
}

VALIDATION_RULES = {
    "monthly_rent": {
        "type": int,
        "min": 200,
        "max": 50_000,
        "required": True,
    },
    "bedrooms": {
        "type": int,
        "min": 0,
        "max": 20,
    },
    "bathrooms": {
        "type": float,
        "min": 0.5,
        "max": 20,
    },
    "square_footage": {
        "type": int,
        "min": 100,
        "max": 50_000,
    },
    "year_built": {
        "type": int,
        "min": 1800,
        "max": 2030,
    },
    "state": {
        "choices": US_STATE_ABBREVS,
    },
    "property_type": {
        "choices": ALLOWED_PROPERTY_TYPES,
    },
}


def validate(prop: dict) -> tuple[dict, list[str]]:
    """
    Validate and lightly coerce a normalized property dict.
    Returns (cleaned_prop, errors).
    Errors are non-blocking — the caller decides whether to reject or warn.
    """
    errors = []
    cleaned = {**prop}

    for field, rules in VALIDATION_RULES.items():
        val = cleaned.get(field)

        if val is None:
            if rules.get("required"):
                errors.append(f"{field}: required but missing")
            continue

        if "choices" in rules:
            if val not in rules["choices"]:
                errors.append(f"{field}: '{val}' is not an allowed value")
            continue

        if "type" in rules:
            try:
                coerced = rules["type"](val)
                cleaned[field] = coerced
                val = coerced
            except (ValueError, TypeError):
                errors.append(f"{field}: cannot coerce '{val}' to {rules['type'].__name__}")
                continue

        if "min" in rules and val < rules["min"]:
            errors.append(f"{field}: {val} is below minimum ({rules['min']})")
            cleaned[field] = None

        if "max" in rules and val > rules["max"]:
            errors.append(f"{field}: {val} is above maximum ({rules['max']})")
            cleaned[field] = None

    return cleaned, errors


def validate_and_warn(prop: dict) -> dict:
    """
    Run validation, log warnings for any errors, and return the cleaned prop.
    Never raises — validation is always non-blocking.

    NOTE: kept for backward compatibility. New code should prefer
    `validate_and_filter` which actually rejects unsalvageable rows instead
    of just logging.
    """
    try:
        cleaned, errors = validate(prop)
        for err in errors:
            logger.warning("Validation warning for property %s: %s", prop.get("source_listing_id", "?"), err)
        return cleaned
    except Exception as e:
        logger.warning("Validator crashed unexpectedly: %s", e)
        return prop


# Phase 3 (3.1): hard-reject thresholds. A row that fails any of these is
# unusable as a rental listing and should never be persisted — better to drop
# it cleanly with a counted reason than save garbage and let it pollute the
# library + the dashboard counts. Values chosen from the audit (C4):
#   • monthly_rent < $200  → demonstrably a misparsed/decimal/list-price field
#   • monthly_rent missing → no point persisting a "rental" with no rent
#   • address  missing     → cannot dedupe, cannot geocode, cannot publish
HARD_MIN_RENT = 200


def validate_and_filter(prop: dict) -> tuple[dict | None, str | None]:
    """
    Validate, coerce, and hard-reject unsalvageable rows.

    Returns:
      (cleaned_prop, None) on success — caller should persist `cleaned_prop`.
      (None, reason)        on rejection — caller should increment
                            metrics.validation_rejected with `reason`.

    Rejection reasons (stable strings — used in metrics + logs):
      "missing_rent" | "rent_below_min" | "missing_address" | "validator_crash"
    """
    try:
        cleaned, _errors = validate(prop)
    except Exception as e:
        logger.warning("Validator crashed unexpectedly: %s", e)
        return None, "validator_crash"

    address = cleaned.get("address")
    if not address or not str(address).strip():
        return None, "missing_address"

    rent = cleaned.get("monthly_rent")
    if rent is None:
        return None, "missing_rent"
    if rent < HARD_MIN_RENT:
        return None, "rent_below_min"

    return cleaned, None
