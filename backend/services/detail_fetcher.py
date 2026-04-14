import json
import logging
import re

import httpx

logger = logging.getLogger(__name__)

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ChoiceBot/1.0)"}

EXTRACTORS = {
    "available_date": [
        r"Available\s+([A-Z][a-z]+ \d{1,2},? \d{4})",
        r"Move[- ]in[:\s]+([A-Z][a-z]+ \d{4})",
        r"(?i)available\s+(immediately|now)",
    ],
    "security_deposit": [
        r"[Ss]ecurity [Dd]eposit[:\s]+\$([0-9,]+)",
        r"\$([0-9,]+)\s+(?:security )?deposit",
    ],
    "lease_terms": [
        r"(\d{1,2})[- ]month lease",
        r"lease term[:\s]+(\d{1,2}) months",
    ],
}


def fetch_missing_fields(prop_id: str, db) -> None:
    """
    For properties with data_quality_score < 70, fetch the listing's source URL
    and extract missing fields via regex patterns.
    Updates the DB record in place — never raises.
    """
    from database.models import Property

    prop = db.query(Property).filter(Property.id == prop_id).first()
    if not prop:
        return
    if (prop.data_quality_score or 0) >= 70:
        return
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
        for pattern in EXTRACTORS["available_date"]:
            m = re.search(pattern, html, re.IGNORECASE)
            if m:
                prop.available_date = m.group(1)
                inferred.append("available_date_from_html")
                changed = True
                break

    if not prop.security_deposit:
        for pattern in EXTRACTORS["security_deposit"]:
            m = re.search(pattern, html, re.IGNORECASE)
            if m:
                try:
                    prop.security_deposit = int(m.group(1).replace(",", ""))
                    inferred.append("security_deposit_from_html")
                    changed = True
                    break
                except ValueError:
                    pass

    current_terms = []
    try:
        current_terms = json.loads(prop.lease_terms or "[]")
    except Exception:
        pass
    if not current_terms:
        for pattern in EXTRACTORS["lease_terms"]:
            m = re.search(pattern, html, re.IGNORECASE)
            if m:
                prop.lease_terms = json.dumps([f"{m.group(1)} months"])
                inferred.append("lease_terms_from_html")
                changed = True
                break

    if changed:
        prop.inferred_features = json.dumps(inferred)
        try:
            db.commit()
            logger.info("detail_fetcher: enriched fields for property %s", prop_id)
        except Exception as e:
            db.rollback()
            logger.warning("detail_fetcher: commit failed for %s: %s", prop_id, e)
