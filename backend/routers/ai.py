import difflib
import json
import logging
import os
import time
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from openai import OpenAI
from pydantic import BaseModel

from database.db import get_db
from database.repository import Repository, AiEnrichmentLog
from services.ai_client import (
    PLATFORM_CONTEXT,
    PROMPT_VERSION,
    call_deepseek,
    get_client,
    handle_deepseek_error,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Data Models ────────────────────────────────────────────────────────────────

class PropertyContext(BaseModel):
    address: str | None = None
    city: str | None = None
    state: str | None = None
    bedrooms: int | None = None
    bathrooms: float | None = None
    square_footage: int | None = None
    year_built: int | None = None
    monthly_rent: float | None = None
    property_type: str | None = None
    amenities: str | None = None
    appliances: str | None = None
    pets_allowed: bool | None = None
    parking: str | None = None
    heating_type: str | None = None
    cooling_type: str | None = None
    laundry_type: str | None = None
    utilities_included: str | None = None
    description: str | None = None
    lease_terms: str | None = None
    flooring: str | None = None
    has_basement: bool | None = None
    has_central_air: bool | None = None


class RewriteRequest(BaseModel):
    property: PropertyContext
    tone: str = "professional"


class LibraryStats(BaseModel):
    avg_rent_same_beds: float | None = None
    count_same_beds: int | None = None
    min_rent_same_beds: float | None = None
    max_rent_same_beds: float | None = None


class IssuesRequest(BaseModel):
    property: PropertyContext
    library_stats: LibraryStats | None = None


class SuggestRequest(BaseModel):
    property: PropertyContext
    field: str
    current_value: str | None = None


class ChatRequest(BaseModel):
    property: PropertyContext
    message: str
    history: list[dict] | None = None


class AutoFillRequest(BaseModel):
    property: PropertyContext
    fields: list[str]


# ── Property Summary Builder ───────────────────────────────────────────────────

def _build_property_summary(prop: PropertyContext) -> str:
    parts = []
    if prop.address:
        location = ", ".join(filter(None, [prop.address, prop.city, prop.state]))
        parts.append(f"Address: {location}")
    elif prop.city or prop.state:
        location = ", ".join(filter(None, [prop.city, prop.state]))
        parts.append(f"Location: {location}")
    if prop.property_type:
        parts.append(f"Property type: {prop.property_type}")
    if prop.bedrooms is not None:
        parts.append(f"Bedrooms: {prop.bedrooms}")
    if prop.bathrooms is not None:
        parts.append(f"Bathrooms: {prop.bathrooms}")
    if prop.square_footage:
        parts.append(f"Square footage: {prop.square_footage:,} sqft")
    if prop.year_built:
        parts.append(f"Year built: {prop.year_built}")
    if prop.monthly_rent:
        parts.append(f"Monthly rent: ${prop.monthly_rent:,.0f}")
    if prop.amenities:
        parts.append(f"Amenities: {prop.amenities}")
    if prop.appliances:
        parts.append(f"Appliances: {prop.appliances}")
    if prop.pets_allowed is not None:
        parts.append(f"Pets allowed: {'Yes' if prop.pets_allowed else 'No'}")
    if prop.parking:
        parts.append(f"Parking: {prop.parking}")
    if prop.heating_type:
        parts.append(f"Heating: {prop.heating_type}")
    if prop.cooling_type:
        parts.append(f"Cooling: {prop.cooling_type}")
    if prop.laundry_type:
        parts.append(f"Laundry: {prop.laundry_type}")
    if prop.utilities_included:
        parts.append(f"Utilities included: {prop.utilities_included}")
    if prop.flooring:
        parts.append(f"Flooring: {prop.flooring}")
    if prop.has_basement:
        parts.append("Has basement: Yes")
    if prop.has_central_air:
        parts.append("Central air: Yes")
    if prop.lease_terms:
        parts.append(f"Lease terms: {prop.lease_terms}")
    if prop.description:
        parts.append(f"\nExisting description (for reference only — rewrite from scratch):\n{prop.description}")
    return "\n".join(parts) if parts else "No property details provided."


# ── AI Endpoints ───────────────────────────────────────────────────────────────

@router.post("/ai/rewrite-description")
def rewrite_description(req: RewriteRequest):
    prop_summary = _build_property_summary(req.property)

    tone_map = {
        "professional": (
            "professional and polished — confident, clean, and authoritative. "
            "Use precise language. Avoid filler phrases. Read like a premium listing."
        ),
        "friendly": (
            "warm, conversational, and inviting — like a trusted friend describing the home. "
            "Use approachable language. Make the reader feel excited and welcome."
        ),
        "concise": (
            "short and direct — maximum 3 sentences per paragraph, 2 paragraphs total. "
            "Lead with the strongest features. Cut everything that isn't essential."
        ),
    }
    tone_instruction = tone_map.get(req.tone, tone_map["professional"])

    user_prompt = f"""Rewrite this rental listing description using the property details below.

PROPERTY DATA:
{prop_summary}

TONE: {tone_instruction}

HARD RULES — follow every one without exception:
1. NEVER mention tours, viewings, showings, or "seeing the property in person." Omit completely.
2. NEVER include credit scores, income requirements, income multipliers, background check language, "no Section 8", or any tenant screening criteria.
3. NEVER say "no pets." Either omit the pet policy entirely or say "ask about our pet policy."
4. NEVER invent facts. Only describe what is supported by the property data above.
5. NEVER copy boilerplate phrases like "don't miss this gem", "call today", "motivated landlord."
6. Focus on what makes this home livable and enjoyable: layout, light, space, comfort, location, amenities.
7. Structure: 2–4 paragraphs. No bullet points. No headline or title. Body text only.
8. End with a soft call to action about applying — e.g. "Ready to call this home? Submit your application today and take the first step."
9. Return ONLY the description text. Nothing else — no labels, no preamble, no quotes."""

    try:
        result = call_deepseek(PLATFORM_CONTEXT, user_prompt, temperature=0.75)
        return {"description": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("AI rewrite failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ai/detect-issues")
def detect_issues(req: IssuesRequest):
    prop_summary = _build_property_summary(req.property)

    library_context_block = ""
    if req.library_stats and req.library_stats.avg_rent_same_beds and req.property.monthly_rent:
        avg = req.library_stats.avg_rent_same_beds
        mn = req.library_stats.min_rent_same_beds or 0
        mx = req.library_stats.max_rent_same_beds or 0
        pct_diff = ((req.property.monthly_rent - avg) / avg * 100) if avg else 0
        library_context_block = f"""
LIBRARY PRICING CONTEXT (your other listings with same bedroom count):
- Average rent: ${avg:,.0f}/mo (across {req.library_stats.count_same_beds or '?'} listings)
- Range: ${mn:,.0f} – ${mx:,.0f}/mo
- This listing is {abs(pct_diff):.0f}% {'above' if pct_diff > 0 else 'below'} your library average for this bedroom count
- Flag as a pricing error if this listing is more than 50% above or below the library average (outlier risk)
"""

    desc = req.property.description or ""
    beds = req.property.bedrooms
    baths = req.property.bathrooms

    consistency_block = ""
    if desc and (beds is not None or baths is not None):
        consistency_block = f"""
DATA CONSISTENCY CHECK — look for contradictions between structured fields and the description text:
- Structured bedrooms: {beds if beds is not None else 'not set'}
- Structured bathrooms: {baths if baths is not None else 'not set'}
- pets_allowed field: {req.property.pets_allowed if req.property.pets_allowed is not None else 'not set'}
- Check if description mentions a different bedroom/bathroom count than the structured fields
- Check if description says "no pets" but pets_allowed is True (contradiction)
- Check if description mentions specific features that contradict other structured fields
"""

    user_prompt = f"""Perform a full quality control review of this rental listing before it is published.

PROPERTY DATA:
{prop_summary}
{library_context_block}
{consistency_block}

REVIEW CHECKLIST — evaluate every category below:

ERRORS (blocking issues — listing should not publish without fixing):
- Missing rent amount
- Missing address or location
- Missing bedroom or bathroom count
- Completely missing description
- Contradictory data between description text and structured fields (e.g. description says 3 beds but field says 2, or description says "no pets" but pets_allowed is True)
- Rent is implausibly low or high for the bedroom count and location (e.g. $200/mo for a 3BR home, or $15,000/mo for a studio)
- Rent is a library pricing outlier (>50% above or below your library average for the same bedroom count, if library context was provided)

WARNINGS (should fix before publishing — affects quality or trust):
- Description is too short (under 50 words)
- Description is generic, templated, or reads like copy-pasted boilerplate
- Description mentions tours, showings, or "contact to schedule" — violates platform rules
- Description includes screening criteria (credit score, income, background check) — violates platform rules
- Description includes hard "no pets" language — violates platform guidelines
- Description contains contact info (phone numbers, emails, "call today") — must be removed
- Missing square footage for a home listing
- No amenities listed at all
- No appliances listed
- Missing lease terms
- Missing parking info for a house or condo

SUGGESTIONS (nice to have — improves listing quality):
- Title is generic (e.g. "2BR Apartment in Chicago") — a specific compelling title would help
- Description could benefit from stronger opening line
- Amenities list seems incomplete for this property type/age
- Pet policy not addressed (if pets_allowed is True)
- Move-in special not mentioned (could attract more applicants)
- Utilities policy unclear
- Flooring not specified
- Year built would strengthen the listing

Return a JSON object with these keys:
- "issues": array where each item has:
  - "severity": one of "error", "warning", or "suggestion"
  - "field": the specific field name this relates to, or "general" for overall listing issues
  - "message": a clear, specific, actionable description of the issue (1–2 sentences max)
- "quality_score": integer 0–100 — AI-evaluated description quality score (0 = no/terrible description, 100 = compelling, complete, brand-voice compliant). Score the description content quality alone, not just whether fields are filled.

Rules:
- Only include real issues. Do not flag things that are fine.
- Do not hallucinate issues that don't exist in the data.
- Order issues by severity: errors first, then warnings, then suggestions."""

    try:
        raw = call_deepseek(PLATFORM_CONTEXT, user_prompt, temperature=0.2, json_mode=True)
        result = json.loads(raw)
        if isinstance(result, list):
            return {"issues": result, "quality_score": None}
        return {
            "issues": result.get("issues", []),
            "quality_score": result.get("quality_score", None),
        }
    except json.JSONDecodeError:
        return {"issues": [], "quality_score": None}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("AI issue detection failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ai/suggest-field")
def suggest_field(req: SuggestRequest):
    prop_summary = _build_property_summary(req.property)

    user_prompt = f"""Suggest the best value for the field "{req.field}" for this rental property.

PROPERTY DATA:
{prop_summary}

CURRENT VALUE FOR "{req.field}": {req.current_value if req.current_value else "Empty — needs a value."}

INSTRUCTIONS:
- Use the property type, year built, location, and other details to make an intelligent inference.
- Apply your knowledge of typical US rental properties to suggest a realistic value.
- Keep the suggestion concise and practical — just the value, no explanation.
- If this is a list field (amenities, appliances, etc.), return a comma-separated list.
- Do not guess wildly. If you cannot make a reasonable inference, return "Unknown".
- Return ONLY the suggested value. No quotes, no labels, no explanation."""

    try:
        result = call_deepseek(PLATFORM_CONTEXT, user_prompt, temperature=0.3)
        return {"suggestion": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("AI suggest field failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ai/chat")
def chat_with_property(req: ChatRequest):
    prop_summary = _build_property_summary(req.property)

    system_message = f"""{PLATFORM_CONTEXT}

---

## Your Current Task
You are helping a property manager edit and improve a specific listing in the Property Pipeline. You have full context of the listing below. You can:
- Answer questions about the listing
- Rewrite or improve the description (provide the full text when asked)
- Suggest values for specific fields
- Flag issues or inconsistencies
- Explain platform rules (why certain language should be removed, etc.)
- Help think through pricing, amenities, or lease terms

Always be direct and practical. If asked to rewrite something, provide the complete rewritten version immediately — don't ask clarifying questions unless truly necessary.

## Current Property
{prop_summary}"""

    messages = [{"role": "system", "content": system_message}]

    if req.history:
        for msg in req.history[-10:]:
            role = msg.get("role", "user")
            if role in ("user", "assistant"):
                messages.append({"role": role, "content": msg.get("content", "")})

    messages.append({"role": "user", "content": req.message})

    try:
        client = get_client()
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            temperature=0.7,
        )
        result = response.choices[0].message.content.strip()
        return {"reply": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("AI chat failed: %s", e)
        handle_deepseek_error(e)


# ── Auto-Fill ──────────────────────────────────────────────────────────────────

AUTOFILL_FIELD_DESCRIPTIONS = {
    "heating_type": "Type of heating system. Common values: 'Forced Air', 'Baseboard', 'Radiant', 'Heat Pump', 'Boiler'. Infer from property type and year built.",
    "cooling_type": "Type of cooling. Common values: 'Central Air', 'Window Units', 'Mini-Split', 'None'. Infer from year built and region.",
    "laundry_type": "Laundry situation. Common values: 'In-unit', 'In-unit hookups', 'Shared laundry', 'None'. Infer from property type and year built.",
    "parking": "Parking description. E.g. '1-car garage', '2-car garage', 'Driveway', 'Street parking', '1 assigned spot', '2 reserved spots'. Infer from property type.",
    "flooring": "Comma-separated flooring types present in the home. E.g. 'Hardwood, Tile' or 'Carpet, Laminate, Tile'. Infer from property age and type.",
    "lease_terms": "Comma-separated lease length options. E.g. '12-month' or '12-month, Month-to-month'. Standard is 12-month.",
    "showing_instructions": "Short showing note. On Choice Properties, tenants apply first. Use: 'Apply online to schedule a showing' or 'Apply to get started — showings scheduled after application review.'",
    "pet_details": "Pet policy summary if pets are allowed. E.g. 'Cats and small dogs welcome' or 'Pet-friendly — ask about our policy.' Never say 'no pets'.",
    "pet_types_allowed": "Comma-separated pet types if pets are allowed. E.g. 'Dogs, Cats' or 'Cats only'.",
    "amenities": "Comma-separated list of property amenities. Include relevant items from: Yard, Patio, Deck, Pool, Gym, Garage, Storage, Balcony, Fireplace, Basement, Dishwasher, High ceilings, Natural light, Smart thermostat.",
    "appliances": "Comma-separated list of included appliances. Common: Refrigerator, Dishwasher, Stove, Oven, Microwave, Washer, Dryer, Garbage disposal.",
    "description": "A full tenant-first listing description: 3–4 paragraphs, no bullet points, no headers, no tour language, no screening criteria. Warm, welcoming, and focused on livability.",
    "move_in_special": "Any move-in promotion if applicable. E.g. 'First month free', 'Reduced security deposit', 'No application fee'. If none is apparent, omit this field.",
    "utilities_included": "Comma-separated utilities included in rent. Common: Water, Trash, Sewer, Gas, Electric, Internet. Most US rentals include at minimum Water and Trash.",
}


@router.post("/ai/autofill")
def autofill_fields(req: AutoFillRequest):
    prop_summary = _build_property_summary(req.property)
    valid_fields = [f for f in req.fields if f in AUTOFILL_FIELD_DESCRIPTIONS]
    if not valid_fields:
        return {"suggestions": {}}

    fields_block = "\n".join(
        f'- "{f}": {AUTOFILL_FIELD_DESCRIPTIONS[f]}' for f in valid_fields
    )

    user_prompt = f"""Fill in the missing fields for this rental property listing using intelligent inference.

PROPERTY DATA:
{prop_summary}

FIELDS TO FILL IN:
{fields_block}

INSTRUCTIONS:
- Use the property type, year built, location, bedroom count, and all other available data to make smart inferences.
- Apply your knowledge of typical US rental market standards.
- For the "description" field: write a full 3–4 paragraph tenant-first listing description. No bullet points. No tours. No screening language.
- For "showing_instructions": always reference the apply-first model (e.g. "Apply online to schedule your showing").
- For comma-separated fields: return a plain comma-separated string, not a JSON array.
- Only include a field if you can provide a confident, realistic value. Skip fields you genuinely cannot infer.
- Do NOT invent specific facts (square footage, rent, exact address) — only infer qualitative fields.
- Return ONLY a raw JSON object. No markdown, no explanation, no wrapper."""

    try:
        raw = call_deepseek(PLATFORM_CONTEXT, user_prompt, temperature=0.3, json_mode=True)
        suggestions = json.loads(raw)
        filtered = {k: v for k, v in suggestions.items() if k in valid_fields}
        return {"suggestions": filtered}
    except json.JSONDecodeError:
        return {"suggestions": {}}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("AI autofill failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ── Bulk Operation Helpers ─────────────────────────────────────────────────────

def _get_inferred_tag(prop, prefix: str) -> str | None:
    """Read a tagged value from inferred_features JSON array, e.g. 'last_scanned:2026-04-16T...'"""
    try:
        features = json.loads(prop.inferred_features or "[]")
        for f in features:
            if isinstance(f, str) and f.startswith(prefix):
                return f[len(prefix):]
    except Exception:
        pass
    return None


def _set_inferred_tag(repo, prop_id: str, prop, prefix: str, value: str) -> None:
    """
    Write a tagged value into inferred_features, replacing any existing entry
    with the same prefix. Uses a lightweight targeted update so that updated_at
    is NOT changed — this preserves the 'edited since last scan' comparison.
    """
    try:
        features = json.loads(prop.inferred_features or "[]")
    except Exception:
        features = []
    features = [f for f in features if not (isinstance(f, str) and f.startswith(prefix))]
    features.append(f"{prefix}{value}")
    repo.update_inferred_features(prop_id, features)


def _bulk_clean_with_retry(description: str, prop_summary: str, max_retries: int = 3) -> dict:
    """
    Run _run_clean with per-call retry specifically for 429 rate limit errors.
    Waits 5s then 10s between attempts before giving up and re-raising.
    """
    for attempt in range(max_retries):
        try:
            return _run_clean(description, prop_summary)
        except HTTPException as e:
            if e.status_code == 429 and attempt < max_retries - 1:
                wait = 5 * (attempt + 1)
                logger.warning(
                    "Bulk clean: rate limit hit for property, retrying in %ds (attempt %d/%d)",
                    wait, attempt + 1, max_retries,
                )
                time.sleep(wait)
                continue
            raise
    return {"cleaned_description": None, "changes_made": False, "changes_summary": []}


# ── Bulk Scan ──────────────────────────────────────────────────────────────────

class BulkScanItem(BaseModel):
    id: str
    property: PropertyContext


class BulkScanRequest(BaseModel):
    properties: list[BulkScanItem]
    skip_recent: bool = True


@router.post("/ai/bulk-scan")
def bulk_scan(req: BulkScanRequest, repo: Repository = Depends(get_db)):
    if not req.properties:
        return {"results": [], "skipped": 0, "scanned": 0}

    TOKEN_BUDGET = 3000
    all_results = []
    batch: list[BulkScanItem] = []
    batch_tokens = 0
    skipped_count = 0
    now = datetime.now(timezone.utc)

    def _estimate_tokens(item: BulkScanItem) -> int:
        return len(_build_property_summary(item.property)) // 4

    def _run_batch(current_batch: list[BulkScanItem]) -> list[dict]:
        listings_block = ""
        for item in current_batch:
            summary = _build_property_summary(item.property)
            listings_block += f'\n---\nID: "{item.id}"\n{summary}\n'

        user_prompt = f"""You are a quality control assistant reviewing multiple rental listings at once.

For each listing below, quickly assess how many errors, warnings, and suggestions it has based on these rules:

ERRORS (critical — should not publish):
- Missing rent, missing address, missing bedrooms/bathrooms, no description at all, contradictory data

WARNINGS (should fix before publishing):
- Description too short or generic, tour/showing language, screening criteria in description, no amenities, no lease terms

SUGGESTIONS (nice improvements):
- Missing sqft, incomplete amenities, pet policy unclear, no move-in special mentioned

LISTINGS TO REVIEW:
{listings_block}

Return a JSON object with key "results" containing an array. One object per listing, in the same order. Each object:
- "id": the listing ID exactly as given
- "errors": integer count of errors found
- "warnings": integer count of warnings found
- "suggestions": integer count of suggestions found
- "top_issue": a single short string describing the most critical problem, or null if none"""

        try:
            raw = call_deepseek(PLATFORM_CONTEXT, user_prompt, temperature=0.1, json_mode=True)
            result = json.loads(raw)
            batch_results = result.get("results", result) if isinstance(result, dict) else result
            if isinstance(batch_results, list):
                return batch_results
            return []
        except Exception as e:
            logger.error("AI bulk scan batch failed: %s", e)
            return [
                {"id": item.id, "errors": 0, "warnings": 0, "suggestions": 0, "top_issue": None}
                for item in current_batch
            ]

    for item in req.properties:
        # ── Skip recently-scanned properties that haven't been edited since ──
        if req.skip_recent:
            try:
                prop = repo.get(item.id)
                if prop:
                    last_scanned_str = _get_inferred_tag(prop, "last_scanned:")
                    if last_scanned_str:
                        last_scanned = datetime.fromisoformat(last_scanned_str)
                        if (now - last_scanned) < timedelta(hours=24):
                            updated_str = prop.updated_at
                            if not updated_str or datetime.fromisoformat(
                                updated_str.replace("Z", "+00:00")
                            ) <= last_scanned:
                                all_results.append({
                                    "id": item.id,
                                    "errors": 0, "warnings": 0, "suggestions": 0,
                                    "top_issue": None,
                                    "skipped": True,
                                    "skip_reason": "scanned_recently",
                                })
                                skipped_count += 1
                                continue
            except Exception as e:
                logger.warning("Bulk scan: skip check failed for %s: %s", item.id, e)

        # ── Add to current token-budget batch ──
        item_tokens = _estimate_tokens(item)
        if batch and (batch_tokens + item_tokens > TOKEN_BUDGET):
            batch_results = _run_batch(batch)
            all_results.extend(batch_results)
            # Save scan timestamps for all processed items in this batch
            for scanned_item in batch:
                try:
                    prop = repo.get(scanned_item.id)
                    if prop:
                        _set_inferred_tag(repo, scanned_item.id, prop, "last_scanned:", now.isoformat())
                except Exception:
                    pass
            time.sleep(0.75)
            batch = []
            batch_tokens = 0

        batch.append(item)
        batch_tokens += item_tokens

    if batch:
        batch_results = _run_batch(batch)
        all_results.extend(batch_results)
        for scanned_item in batch:
            try:
                prop = repo.get(scanned_item.id)
                if prop:
                    _set_inferred_tag(repo, scanned_item.id, prop, "last_scanned:", now.isoformat())
            except Exception:
                pass

    return {"results": all_results, "skipped": skipped_count, "scanned": len(all_results) - skipped_count}


# ── AI Score ───────────────────────────────────────────────────────────────────

class ScoreRequest(BaseModel):
    property: PropertyContext


@router.post("/ai/score")
def get_ai_score(req: ScoreRequest):
    prop_summary = _build_property_summary(req.property)

    user_prompt = f"""You are a senior listing quality analyst for Choice Properties. Evaluate this rental listing and produce a detailed quality report.

PROPERTY DATA:
{prop_summary}

Produce a quality report in JSON with these exact keys:
- "score": integer 0–100 representing overall listing quality
- "grade": letter grade "A", "B", "C", "D", or "F"
- "headline": one sentence summarizing the listing's overall state (e.g. "Strong listing with a few minor gaps" or "Major issues prevent this from being publish-ready")
- "strengths": array of 2–4 short strings describing what this listing does well
- "critical_fixes": array of issues that MUST be resolved before publishing (empty array if none)
- "improvements": array of 2–4 short strings for things that would improve the listing
- "publish_ready": boolean — true only if there are zero critical fixes

Scoring guide:
- 90–100 (A): Complete, compelling, ready to publish
- 75–89 (B): Good listing, minor gaps
- 60–74 (C): Usable but needs work
- 45–59 (D): Significant gaps, not publish-ready
- 0–44 (F): Major problems, requires significant work"""

    try:
        raw = call_deepseek(PLATFORM_CONTEXT, user_prompt, temperature=0.2, json_mode=True)
        return json.loads(raw)
    except json.JSONDecodeError:
        return {
            "score": 0, "grade": "?",
            "headline": "Could not evaluate listing.",
            "strengths": [], "critical_fixes": [], "improvements": [],
            "publish_ready": False,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("AI score failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ── Pricing Intelligence ───────────────────────────────────────────────────────

class PricingRequest(BaseModel):
    property: PropertyContext


@router.post("/ai/pricing-intel")
def pricing_intel(req: PricingRequest):
    prop_summary = _build_property_summary(req.property)

    user_prompt = f"""You are a US rental market pricing expert. Evaluate whether this property's rent is priced appropriately for its market.

PROPERTY DATA:
{prop_summary}

Analyze the rent based on:
- Bedroom and bathroom count
- Square footage (if available)
- Property type
- Location (city/state if available)
- Year built and features/amenities
- General US rental market knowledge (note: this is model knowledge, not live market data)

Return a JSON object with these exact keys:
- "assessment": one of "very_low", "low", "fair", "high", "very_high", or "unknown" (use unknown only if rent is missing)
- "confidence": one of "high", "medium", "low" — how confident you are in the assessment
- "market_context": 1–2 sentences explaining the typical rent range for this type of property in this location
- "verdict": 1–2 sentences assessing whether this specific rent is appropriate
- "recommendation": one concrete, actionable sentence (e.g. "Consider pricing between $X–$Y to stay competitive" or "This rent is well-positioned for the market")
- "comparable_range": string like "$1,800–$2,200/mo" representing the typical market range for this type of property, or null if unknown
- "data_note": always include this string: "Pricing estimates are based on model training data and may not reflect current market conditions."

Return ONLY a raw JSON object."""

    try:
        raw = call_deepseek(PLATFORM_CONTEXT, user_prompt, temperature=0.2, json_mode=True)
        return json.loads(raw)
    except json.JSONDecodeError:
        return {
            "assessment": "unknown", "confidence": "low",
            "market_context": "", "verdict": "Could not evaluate pricing.",
            "recommendation": "", "comparable_range": None,
            "data_note": "Pricing estimates are based on model training data and may not reflect current market conditions.",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("AI pricing intel failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ── SEO Optimizer ──────────────────────────────────────────────────────────────

class SeoRequest(BaseModel):
    property: PropertyContext
    description: str | None = None


@router.post("/ai/seo-optimize")
def seo_optimize(req: SeoRequest):
    prop_summary = _build_property_summary(req.property)
    description = req.description or req.property.description or ""

    user_prompt = f"""You are an SEO expert specializing in real estate and rental listings. Analyze this listing for search engine visibility and organic traffic potential.

PROPERTY DATA:
{prop_summary}

CURRENT DESCRIPTION:
{description if description else "(No description yet)"}

Evaluate the listing's SEO strength and return a JSON object with these exact keys:
- "score": integer 0–100 representing SEO strength
- "missing_keywords": array of high-value search terms that should appear in the description but don't (e.g. "2 bedroom apartment for rent", city name, neighborhood, key amenities)
- "present_keywords": array of good SEO terms already present in the description
- "title_suggestion": a strong, keyword-rich listing title (e.g. "Spacious 3BR/2BA House for Rent in Austin, TX — Garage, Yard, Pets Welcome")
- "improvements": array of 3–5 specific, actionable SEO improvements (e.g. "Add the city name 'Chicago' in the first sentence", "Mention 'hardwood floors' which is a common search term")
- "optimized_opening": a rewritten first sentence or two that's more SEO-friendly, keeping the tenant-first tone and removing any tour/screening language"""

    try:
        raw = call_deepseek(PLATFORM_CONTEXT, user_prompt, temperature=0.3, json_mode=True)
        return json.loads(raw)
    except json.JSONDecodeError:
        return {
            "score": 0, "missing_keywords": [], "present_keywords": [],
            "title_suggestion": "", "improvements": [], "optimized_opening": "",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("AI SEO optimize failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ── AI Text Cleaner ─────────────────────────────────────────────────────────────

class CleanRequest(BaseModel):
    property_id: str | None = None
    property: PropertyContext


def _run_clean(description: str, prop_summary: str) -> dict:
    if not description or len(description.strip()) < 20:
        return {"cleaned_description": None, "changes_made": False, "changes_summary": []}

    user_prompt = f"""You are a content cleaning specialist for Choice Properties rental marketplace.

ORIGINAL DESCRIPTION:
{description}

PROPERTY CONTEXT:
{prop_summary}

CLEANING TASKS — apply every one:
1. REMOVE all contact information: phone numbers (any format), email addresses, website URLs, agent names, company names with contact details
2. REMOVE all tour/showing/viewing language: "call to schedule", "contact us to see", "book a showing", "schedule a tour", "see the unit", "arrange a viewing", "contact agent"
3. REMOVE all screening/gatekeeping language: credit score requirements (e.g. "must have 700+ credit"), income multipliers (e.g. "must earn 3x rent"), background check requirements, "no Section 8", eviction history requirements, employment/pay-stub demands, income verification language
4. REMOVE hard "no pets" language — either omit pet policy entirely or say "ask about our pet policy"
5. REWRITE the cleaned version in Choice Properties brand voice: welcoming, tenant-first, honest, professional, apply-first
6. NORMALIZE formatting: fix capitalization errors, remove excessive punctuation (!!!), remove HTML artifacts (&amp; &nbsp; etc), fix run-on sentences
7. KEEP all genuine property details: square footage, bedroom counts, amenities, appliances, location details, year built, etc.
8. END with a soft apply-first call to action (e.g. "Ready to call this home? Submit your application today.")

Return a JSON object with:
- "cleaned_description": the fully cleaned and rewritten description text (or null if description is empty/too short to clean)
- "changes_made": boolean — true if any meaningful changes were necessary
- "changes_summary": array of short strings describing what was removed or changed (e.g. ["Removed phone number", "Removed income requirement '3x rent'", "Removed tour scheduling language"])"""

    try:
        raw = call_deepseek(PLATFORM_CONTEXT, user_prompt, temperature=0.4, json_mode=True)
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"cleaned_description": None, "changes_made": False, "changes_summary": []}


@router.post("/ai/clean")
def clean_property_text(req: CleanRequest, repo: Repository = Depends(get_db)):
    prop_summary = _build_property_summary(req.property)
    description = req.property.description or ""

    result = _run_clean(description, prop_summary)

    if req.property_id and result.get("cleaned_description") and result.get("changes_made"):
        try:
            prop = repo.get(req.property_id)
            if prop:
                prop.description = result["cleaned_description"]
                try:
                    features = json.loads(prop.inferred_features or "[]")
                except Exception:
                    features = []
                features = [f for f in features if not f.startswith("text_cleaned_")]
                features.append(f"text_cleaned_{datetime.now(timezone.utc).strftime('%Y%m%d')}")
                prop.inferred_features = json.dumps(features)
                repo.save(prop)
                repo.add_log(AiEnrichmentLog(
                    property_id=req.property_id,
                    field="description",
                    method=f"ai_clean_{PROMPT_VERSION}",
                    ai_value=(result["cleaned_description"] or "")[:500],
                ))
        except Exception as e:
            logger.warning("Clean: failed to save back to DB for %s: %s", req.property_id, e)

    return result


# ── Bulk Clean ─────────────────────────────────────────────────────────────────

class BulkCleanRequest(BaseModel):
    property_ids: list[str]
    resume: bool = False


@router.post("/ai/bulk-clean")
def bulk_clean(req: BulkCleanRequest, repo: Repository = Depends(get_db)):
    """
    Bulk clean descriptions for a list of properties.

    resume=True: skip any property that was successfully cleaned in the last hour
    (checkpoint behaviour — safe to re-run after an interruption without
    re-processing already-completed properties).

    resume=False (default): process all properties regardless of prior clean status.
    """
    if not req.property_ids:
        return {"results": [], "cleaned": 0, "skipped": 0, "errors": 0}

    results = []
    cleaned = skipped = errors = 0
    now = datetime.now(timezone.utc)

    for i, prop_id in enumerate(req.property_ids):
        if i > 0:
            time.sleep(0.75)

        try:
            prop = repo.get(prop_id)
            if not prop:
                results.append({"id": prop_id, "status": "not_found"})
                errors += 1
                continue

            # ── Resume checkpoint: skip if already cleaned recently ──
            if req.resume:
                last_cleaned_str = _get_inferred_tag(prop, "last_cleaned:")
                if last_cleaned_str:
                    try:
                        last_cleaned = datetime.fromisoformat(last_cleaned_str)
                        if (now - last_cleaned) < timedelta(hours=1):
                            results.append({"id": prop_id, "status": "checkpoint_skip"})
                            skipped += 1
                            continue
                    except Exception:
                        pass

            if not prop.description or len(prop.description.strip()) < 20:
                results.append({"id": prop_id, "status": "skipped", "reason": "no_description"})
                skipped += 1
                continue

            prop_ctx = PropertyContext(
                address=prop.address, city=prop.city, state=prop.state,
                bedrooms=prop.bedrooms, bathrooms=prop.bathrooms,
                monthly_rent=prop.monthly_rent, property_type=prop.property_type,
                description=prop.description,
            )
            prop_summary = _build_property_summary(prop_ctx)

            # ── Per-property retry on 429 rate limit errors ──
            result = _bulk_clean_with_retry(prop.description, prop_summary)

            if result.get("cleaned_description") and result.get("changes_made"):
                prop.description = result["cleaned_description"]
                try:
                    features = json.loads(prop.inferred_features or "[]")
                except Exception:
                    features = []
                features = [f for f in features if not f.startswith("text_cleaned_")]
                features.append(f"text_cleaned_{now.strftime('%Y%m%d')}")
                prop.inferred_features = json.dumps(features)
                repo.save(prop)
                repo.add_log(AiEnrichmentLog(
                    property_id=prop_id,
                    field="description",
                    method=f"ai_clean_{PROMPT_VERSION}",
                    ai_value=(result["cleaned_description"] or "")[:500],
                ))
                # ── Save checkpoint timestamp ──
                _set_inferred_tag(repo, prop_id, prop, "last_cleaned:", now.isoformat())
                results.append({
                    "id": prop_id,
                    "status": "cleaned",
                    "changes": result.get("changes_summary", []),
                })
                cleaned += 1
            else:
                results.append({"id": prop_id, "status": "already_clean"})
                skipped += 1

        except HTTPException as e:
            results.append({"id": prop_id, "status": "error", "error": e.detail})
            errors += 1
        except Exception as e:
            logger.error("Bulk clean error for %s: %s", prop_id, e)
            results.append({"id": prop_id, "status": "error", "error": str(e)})
            errors += 1

    return {"results": results, "cleaned": cleaned, "skipped": skipped, "errors": errors}


# ── AI Title Generator ──────────────────────────────────────────────────────────

class GenerateTitleRequest(BaseModel):
    property_id: str | None = None
    property: PropertyContext


@router.post("/ai/generate-title")
def generate_title(req: GenerateTitleRequest, repo: Repository = Depends(get_db)):
    prop_summary = _build_property_summary(req.property)

    user_prompt = f"""You are a listing copywriter for Choice Properties. Generate a compelling, specific rental listing title.

PROPERTY DATA:
{prop_summary}

TITLE RULES:
- Be specific, not generic. BAD: "2BR Apartment in Chicago". GOOD: "Bright 2BR Corner Apartment with In-Unit Laundry in Lincoln Park"
- Lead with the strongest feature (size, layout, standout amenity, neighborhood, price if exceptional)
- Include bedrooms (use "Studio" for 0BR, "BR" abbreviation is fine)
- Include the city or neighborhood if known
- Mention 1–2 standout features: garage, yard, in-unit laundry, renovated kitchen, pet-friendly, city views, etc.
- Keep it under 80 characters if possible
- Capitalize properly (Title Case)
- Never mention tours, showings, screening criteria, or contact info
- Never invent facts — only use details from the property data

Return ONLY the title text. No quotes, no labels, no explanation."""

    try:
        result = call_deepseek(PLATFORM_CONTEXT, user_prompt, temperature=0.6)
        title = result.strip().strip('"').strip("'")

        if req.property_id and title:
            try:
                prop = repo.get(req.property_id)
                if prop:
                    prop.title = title
                    repo.save(prop)
                    repo.add_log(AiEnrichmentLog(
                        property_id=req.property_id,
                        field="title",
                        method=f"ai_title_{PROMPT_VERSION}",
                        ai_value=title[:500],
                    ))
            except Exception as e:
                logger.warning("Generate title: failed to save for %s: %s", req.property_id, e)

        return {"title": title}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("AI title generation failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ── LLM Feature Extraction ──────────────────────────────────────────────────────

class ExtractFeaturesRequest(BaseModel):
    property_id: str | None = None
    text: str
    existing_amenities: list[str] | None = None
    existing_appliances: list[str] | None = None


@router.post("/ai/extract-features")
def extract_features_llm(req: ExtractFeaturesRequest, repo: Repository = Depends(get_db)):
    if not req.text or len(req.text.strip()) < 20:
        return {"amenities": [], "appliances": []}

    existing_a = req.existing_amenities or []
    existing_ap = req.existing_appliances or []

    user_prompt = f"""You are a property data extractor. Read the rental listing text below and extract all mentioned amenities and appliances.

LISTING TEXT:
{req.text}

ALREADY CAPTURED (do not duplicate):
- Amenities: {', '.join(existing_a) if existing_a else 'none yet'}
- Appliances: {', '.join(existing_ap) if existing_ap else 'none yet'}

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
        new_amenities = result.get("amenities", [])
        new_appliances = result.get("appliances", [])

        if req.property_id and (new_amenities or new_appliances):
            try:
                prop = repo.get(req.property_id)
                if prop:
                    try:
                        cur_a = json.loads(prop.amenities or "[]")
                    except Exception:
                        cur_a = []
                    try:
                        cur_ap = json.loads(prop.appliances or "[]")
                    except Exception:
                        cur_ap = []

                    merged_a = list(dict.fromkeys(cur_a + new_amenities))
                    merged_ap = list(dict.fromkeys(cur_ap + new_appliances))

                    if merged_a != cur_a:
                        prop.amenities = json.dumps(merged_a)
                        repo.add_log(AiEnrichmentLog(
                            property_id=req.property_id,
                            field="amenities",
                            method=f"llm_extraction_{PROMPT_VERSION}",
                            ai_value=json.dumps(merged_a),
                        ))
                    if merged_ap != cur_ap:
                        prop.appliances = json.dumps(merged_ap)
                        repo.add_log(AiEnrichmentLog(
                            property_id=req.property_id,
                            field="appliances",
                            method=f"llm_extraction_{PROMPT_VERSION}",
                            ai_value=json.dumps(merged_ap),
                        ))
                    if merged_a != cur_a or merged_ap != cur_ap:
                        repo.save(prop)
            except Exception as e:
                logger.warning("Extract features: failed to save for %s: %s", req.property_id, e)

        return {"amenities": new_amenities, "appliances": new_appliances}
    except json.JSONDecodeError:
        return {"amenities": [], "appliances": []}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("AI feature extraction failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ── Phase 4A: Streaming Rewrite ─────────────────────────────────────────────────

@router.post("/ai/rewrite-description/stream")
def rewrite_description_stream(req: RewriteRequest):
    prop_summary = _build_property_summary(req.property)

    tone_map = {
        "professional": (
            "professional and polished — confident, clean, and authoritative. "
            "Use precise language. Avoid filler phrases. Read like a premium listing."
        ),
        "friendly": (
            "warm, conversational, and inviting — like a trusted friend describing the home. "
            "Use approachable language. Make the reader feel excited and welcome."
        ),
        "concise": (
            "short and direct — maximum 3 sentences per paragraph, 2 paragraphs total. "
            "Lead with the strongest features. Cut everything that isn't essential."
        ),
    }
    tone_instruction = tone_map.get(req.tone, tone_map["professional"])

    user_prompt = f"""Rewrite this rental listing description using the property details below.

PROPERTY DATA:
{prop_summary}

TONE: {tone_instruction}

HARD RULES — follow every one without exception:
1. NEVER mention tours, viewings, showings, or "seeing the property in person." Omit completely.
2. NEVER include credit scores, income requirements, income multipliers, background check language, "no Section 8", or any tenant screening criteria.
3. NEVER say "no pets." Either omit the pet policy entirely or say "ask about our pet policy."
4. NEVER invent facts. Only describe what is supported by the property data above.
5. NEVER copy boilerplate phrases like "don't miss this gem", "call today", "motivated landlord."
6. Focus on what makes this home livable and enjoyable: layout, light, space, comfort, location, amenities.
7. Structure: 2–4 paragraphs. No bullet points. No headline or title. Body text only.
8. End with a soft call to action about applying — e.g. "Ready to call this home? Submit your application today and take the first step."
9. Return ONLY the description text. Nothing else — no labels, no preamble, no quotes."""

    def generate():
        try:
            client = get_client()
            stream = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": PLATFORM_CONTEXT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.75,
                stream=True,
            )
            for chunk in stream:
                delta = chunk.choices[0].delta
                if delta.content:
                    yield f"data: {json.dumps({'content': delta.content})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Phase 4A: Streaming Chat ────────────────────────────────────────────────────

@router.post("/ai/chat/stream")
def chat_stream(req: ChatRequest):
    prop_summary = _build_property_summary(req.property)

    system_message = f"""{PLATFORM_CONTEXT}

---

## Your Current Task
You are helping a property manager edit and improve a specific listing in the Property Pipeline. You have full context of the listing below. You can:
- Answer questions about the listing
- Rewrite or improve the description (provide the full text when asked)
- Suggest values for specific fields
- Flag issues or inconsistencies
- Explain platform rules (why certain language should be removed, etc.)
- Help think through pricing, amenities, or lease terms

Always be direct and practical. If asked to rewrite something, provide the complete rewritten version immediately.

## Current Property
{prop_summary}"""

    messages = [{"role": "system", "content": system_message}]
    if req.history:
        for msg in req.history[-10:]:
            role = msg.get("role", "user")
            if role in ("user", "assistant"):
                messages.append({"role": role, "content": msg.get("content", "")})
    messages.append({"role": "user", "content": req.message})

    def generate():
        try:
            client = get_client()
            stream = client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                temperature=0.7,
                stream=True,
            )
            for chunk in stream:
                delta = chunk.choices[0].delta
                if delta.content:
                    yield f"data: {json.dumps({'content': delta.content})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Phase 4B: Neighborhood Context ─────────────────────────────────────────────

class NeighborhoodRequest(BaseModel):
    city: str | None = None
    state: str | None = None
    property_type: str | None = None
    address: str | None = None


@router.post("/ai/neighborhood-context")
def neighborhood_context(req: NeighborhoodRequest):
    if not req.city and not req.state:
        raise HTTPException(status_code=400, detail="City or state is required.")

    location = ", ".join(filter(None, [req.city, req.state]))
    prop_type = req.property_type or "rental property"

    user_prompt = f"""Write a short neighborhood context paragraph for a {prop_type} rental listing located in {location}.

INSTRUCTIONS:
- Write 2–3 sentences only
- Focus on what makes this location appealing for renters: commute access, transit options, walkability, nearby parks, restaurants, schools, employment hubs, or neighborhood character
- Tone: warm, honest, and welcoming — consistent with a tenant-first rental platform
- Do NOT mention real estate prices, "hot market," "high demand," or investment language
- Do NOT invent specific business names, street names, or landmarks you are not confident about
- Keep it grounded — describe the general character and lifestyle appeal of living in this area
- End the paragraph with a sentence that highlights a lifestyle benefit of the location

Return ONLY the paragraph text. No labels, no quotes, no headers."""

    try:
        result = call_deepseek(PLATFORM_CONTEXT, user_prompt, temperature=0.5)
        return {"neighborhood_context": result.strip()}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Neighborhood context failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ── Phase 4C: Duplicate Detection ──────────────────────────────────────────────

class DuplicateCheckRequest(BaseModel):
    property_id: str
    address: str | None = None
    source_listing_id: str | None = None


@router.post("/ai/check-duplicates")
def check_duplicates(req: DuplicateCheckRequest, repo: Repository = Depends(get_db)):
    if not req.address and not req.source_listing_id:
        return {"duplicates": [], "is_duplicate": False}

    try:
        all_props = repo.list()
    except Exception as e:
        logger.warning("Duplicate check: could not load properties: %s", e)
        return {"duplicates": [], "is_duplicate": False}

    address_lower = (req.address or "").lower().strip()
    candidates = []

    for prop in all_props:
        if str(prop.id) == str(req.property_id):
            continue

        if req.source_listing_id and prop.source_listing_id == req.source_listing_id:
            candidates.append({
                "id": str(prop.id),
                "address": prop.address,
                "similarity": 1.0,
                "match_type": "source_id",
                "status": prop.status,
            })
            continue

        if address_lower and prop.address:
            ratio = difflib.SequenceMatcher(
                None, address_lower, prop.address.lower().strip()
            ).ratio()
            if ratio >= 0.85:
                candidates.append({
                    "id": str(prop.id),
                    "address": prop.address,
                    "similarity": round(ratio, 2),
                    "match_type": "address",
                    "status": prop.status,
                })

    candidates.sort(key=lambda x: x["similarity"], reverse=True)
    return {
        "duplicates": candidates[:5],
        "is_duplicate": len(candidates) > 0,
    }


# ── Phase 5B: AI Feedback ───────────────────────────────────────────────────────

class FeedbackRequest(BaseModel):
    property_id: str
    field: str
    action: str
    ai_value: str | None = None


@router.post("/ai/feedback")
def save_ai_feedback(req: FeedbackRequest, repo: Repository = Depends(get_db)):
    if req.action not in ("accept", "reject"):
        raise HTTPException(status_code=400, detail="action must be 'accept' or 'reject'")
    log = AiEnrichmentLog(
        property_id=req.property_id,
        field=req.field,
        method=f"feedback_{req.action}_{PROMPT_VERSION}",
        ai_value=(req.ai_value or "")[:500] if req.ai_value else None,
        was_overridden=(req.action == "reject"),
    )
    try:
        repo.add_log(log)
    except Exception as e:
        logger.warning("Failed to save AI feedback: %s", e)
        raise HTTPException(status_code=500, detail="Failed to save feedback.")
    return {"ok": True}


# ── Phase 5D: Description History Endpoint ─────────────────────────────────────

@router.get("/ai/description-history/{property_id}")
def get_description_history(property_id: str, repo: Repository = Depends(get_db)):
    try:
        logs = repo.list_logs_by_field(property_id, "description_history", limit=10)
        return {
            "history": [
                {
                    "id": log.id,
                    "description": log.ai_value,
                    "saved_at": log.created_at,
                    "method": log.method,
                }
                for log in logs
                if log.ai_value
            ]
        }
    except Exception as e:
        logger.warning("Description history fetch failed: %s", e)
        return {"history": []}
