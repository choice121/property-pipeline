import json
import logging
import re
from datetime import datetime, timezone, timedelta

import httpx

logger = logging.getLogger(__name__)

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ChoiceBot/1.0)"}


def _target_fields_complete(prop) -> bool:
    """Return True only if all fields this fetcher handles are already populated."""
    try:
        lease = json.loads(prop.lease_terms or "[]")
    except Exception:
        lease = []
    try:
        utils = json.loads(prop.utilities_included or "[]")
    except Exception:
        utils = []
    return bool(
        prop.heating_type
        and prop.cooling_type
        and prop.laundry_type
        and lease
        and utils
        and prop.available_date
        and prop.security_deposit
        and prop.parking
    )


def _get_fetch_timestamp(prop) -> str | None:
    """Read stored detail_fetched timestamp from inferred_features."""
    try:
        features = json.loads(prop.inferred_features or "[]")
        for f in features:
            if isinstance(f, str) and f.startswith("detail_fetched:"):
                return f[len("detail_fetched:"):]
    except Exception:
        pass
    return None

EXTRACTORS = {
    "available_date": [
        r"Available\s+([A-Z][a-z]+ \d{1,2},? \d{4})",
        r"Move[- ]in[:\s]+([A-Z][a-z]+ \d{4})",
        r"Available\s+((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4})",
        r"(?i)date\s+available[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        r"(?i)available\s+(immediately|now)",
    ],
    "security_deposit": [
        r"[Ss]ecurity [Dd]eposit[:\s]+\$([0-9,]+)",
        r"\$([0-9,]+)\s+(?:security )?deposit",
        r"[Dd]eposit[:\s]+\$([0-9,]+)",
    ],
    "lease_terms": [
        r"(\d{1,2})[- ]month lease",
        r"lease term[:\s]+(\d{1,2}) months",
        r"minimum lease[:\s]+(\d{1,2}) months",
    ],
    "pets_allowed_yes": [
        r"(?i)pets\s+(ok|allowed|welcome|permitted|friendly)",
        r"(?i)pet[- ]friendly",
        r"(?i)dogs?\s+(ok|allowed|welcome|permitted)",
        r"(?i)cats?\s+(ok|allowed|welcome|permitted)",
        r"(?i)small pets allowed",
    ],
    "pets_allowed_no": [
        r"(?i)no\s+pets",
        r"(?i)pets?\s+not\s+allowed",
        r"(?i)pet[- ]free",
        r"(?i)sorry[,\s]+no pets",
        r"(?i)no animals",
    ],
    "laundry_in_unit": [
        r"(?i)in[- ]unit laundry",
        r"(?i)washer\s*(and|&|/)\s*dryer\s+in\s+unit",
        r"(?i)w/?d\s+in\s+unit",
        r"(?i)washer dryer included",
    ],
    "laundry_hookups": [
        r"(?i)washer[- ]dryer hookups?",
        r"(?i)laundry hookups?",
        r"(?i)w/?d\s+hookup",
    ],
    "laundry_shared": [
        r"(?i)shared laundry",
        r"(?i)laundry\s+on[- ]site",
        r"(?i)laundry\s+room",
        r"(?i)coin[- ]operated laundry",
        r"(?i)communal laundry",
    ],
    "heating_types": {
        "Forced Air":  [r"(?i)forced[- ]air", r"(?i)gas forced"],
        "Electric":    [r"(?i)electric heat", r"(?i)electric baseboard"],
        "Baseboard":   [r"(?i)baseboard heat"],
        "Radiant":     [r"(?i)radiant heat", r"(?i)in[- ]floor heat"],
        "Gas":         [r"(?i)gas heat(?!er)", r"(?i)natural gas heat"],
        "Heat Pump":   [r"(?i)heat pump"],
        "Steam":       [r"(?i)steam heat", r"(?i)steam radiator"],
    },
    "cooling_types": {
        "Central Air":  [r"(?i)central air", r"(?i)central a/c", r"(?i)central cooling"],
        "Window Units": [r"(?i)window a/?c", r"(?i)window air"],
        "Mini-Split":   [r"(?i)mini[- ]split", r"(?i)ductless"],
        "Heat Pump":    [r"(?i)heat pump cooling"],
    },
    "utilities_included": {
        "Water":    [r"(?i)water\s+included", r"(?i)water\s+paid"],
        "Sewer":    [r"(?i)sewer\s+included", r"(?i)sewer\s+paid"],
        "Trash":    [r"(?i)trash\s+included", r"(?i)garbage\s+included", r"(?i)refuse\s+included"],
        "Gas":      [r"(?i)gas\s+included", r"(?i)gas\s+paid"],
        "Electric": [r"(?i)electric\s+included", r"(?i)electricity\s+included", r"(?i)electric\s+paid"],
        "Internet": [r"(?i)internet\s+included", r"(?i)wifi?\s+included", r"(?i)wi-fi\s+included"],
        "Cable":    [r"(?i)cable\s+included", r"(?i)cable\s+tv\s+included"],
    },
    "parking": [
        r"(?i)(\d+)\s+(?:car|vehicle)\s+garage",
        r"(?i)garage\s+parking[:\s]+(\d+)",
        r"(?i)(\d+)\s+off[- ]street\s+parking",
        r"(?i)driveway\s+for\s+(\d+)",
    ],
}


def _re_search_any(patterns, text):
    for p in patterns:
        m = re.search(p, text)
        if m:
            return m
    return None


def fetch_missing_fields(prop_id: str, repo) -> None:
    prop = repo.get(prop_id)
    if not prop:
        return
    # Skip if every field this fetcher handles is already populated
    if _target_fields_complete(prop):
        return
    # Skip if we already fetched this source URL recently (within 7 days) —
    # prevents hammering source sites for listings that just didn't have the data
    fetch_ts = _get_fetch_timestamp(prop)
    if fetch_ts:
        try:
            fetched_at = datetime.fromisoformat(fetch_ts)
            if (datetime.now(timezone.utc) - fetched_at) < timedelta(days=7):
                return
        except Exception:
            pass
    if not prop.source_url:
        return

    try:
        with httpx.Client(timeout=12, follow_redirects=True, headers=HEADERS) as client:
            resp = client.get(prop.source_url)
        if resp.status_code != 200:
            return
        html = resp.text
    except Exception as e:
        logger.debug("detail_fetcher: failed to fetch %s: %s", prop.source_url, e)
        return

    changed = False
    try:
        inferred = json.loads(prop.inferred_features or "[]")
    except Exception:
        inferred = []

    if not prop.available_date:
        m = _re_search_any(EXTRACTORS["available_date"], html)
        if m:
            prop.available_date = m.group(1)
            inferred.append("available_date_from_html")
            changed = True

    if not prop.security_deposit:
        m = _re_search_any(EXTRACTORS["security_deposit"], html)
        if m:
            try:
                prop.security_deposit = int(m.group(1).replace(",", ""))
                inferred.append("security_deposit_from_html")
                changed = True
            except ValueError:
                pass

    current_terms = []
    try:
        current_terms = json.loads(prop.lease_terms or "[]")
    except Exception:
        pass
    if not current_terms:
        m = _re_search_any(EXTRACTORS["lease_terms"], html)
        if m:
            months = m.group(1)
            prop.lease_terms = json.dumps([f"{months} months"])
            if not prop.minimum_lease_months:
                try:
                    prop.minimum_lease_months = int(months)
                except ValueError:
                    pass
            inferred.append("lease_terms_from_html")
            changed = True

    if prop.pets_allowed is None:
        if _re_search_any(EXTRACTORS["pets_allowed_no"], html):
            prop.pets_allowed = False
            inferred.append("pets_denied_from_html")
            changed = True
        elif _re_search_any(EXTRACTORS["pets_allowed_yes"], html):
            prop.pets_allowed = True
            inferred.append("pets_allowed_from_html")
            changed = True

    if not prop.laundry_type:
        if _re_search_any(EXTRACTORS["laundry_in_unit"], html):
            prop.laundry_type = "In-unit"
            inferred.append("laundry_from_html")
            changed = True
        elif _re_search_any(EXTRACTORS["laundry_hookups"], html):
            prop.laundry_type = "Hookups"
            inferred.append("laundry_from_html")
            changed = True
        elif _re_search_any(EXTRACTORS["laundry_shared"], html):
            prop.laundry_type = "Shared"
            inferred.append("laundry_from_html")
            changed = True

    if not prop.heating_type:
        for heat_label, patterns in EXTRACTORS["heating_types"].items():
            if _re_search_any(patterns, html):
                prop.heating_type = heat_label
                inferred.append("heating_from_html")
                changed = True
                break

    if not prop.cooling_type:
        for cool_label, patterns in EXTRACTORS["cooling_types"].items():
            if _re_search_any(patterns, html):
                prop.cooling_type = cool_label
                if cool_label == "Central Air":
                    prop.has_central_air = True
                inferred.append("cooling_from_html")
                changed = True
                break

    try:
        current_utils = json.loads(prop.utilities_included or "[]")
    except Exception:
        current_utils = []
    if not current_utils:
        found_utils = []
        for util_label, patterns in EXTRACTORS["utilities_included"].items():
            if _re_search_any(patterns, html):
                found_utils.append(util_label)
        if found_utils:
            prop.utilities_included = json.dumps(found_utils)
            inferred.append("utilities_from_html")
            changed = True

    if not prop.parking:
        m = _re_search_any(EXTRACTORS["parking"], html)
        if m:
            try:
                spots = int(m.group(1))
                prop.parking = f"{spots} garage space{'s' if spots != 1 else ''}"
                if not prop.garage_spaces:
                    prop.garage_spaces = spots
                inferred.append("parking_from_html")
                changed = True
            except (ValueError, IndexError):
                pass

    # Stamp the fetch timestamp so we don't re-hit the source URL unnecessarily,
    # even if we didn't extract any new fields (source page may not have them).
    now_ts = datetime.now(timezone.utc).isoformat()
    inferred = [f for f in inferred if not (isinstance(f, str) and f.startswith("detail_fetched:"))]
    inferred.append(f"detail_fetched:{now_ts}")
    prop.inferred_features = json.dumps(inferred)

    if changed:
        try:
            repo.save(prop)
            logger.info("detail_fetcher: enriched fields for property %s", prop_id)
        except Exception as e:
            logger.warning("detail_fetcher: save failed for %s: %s", prop_id, e)
    else:
        # Save only the timestamp update — no fields changed but mark as visited
        try:
            repo.save(prop)
        except Exception:
            pass
