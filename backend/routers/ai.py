import json
import logging
import os

from fastapi import APIRouter, HTTPException
from openai import OpenAI, AuthenticationError, RateLimitError, APIStatusError, APIConnectionError
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Platform Knowledge ─────────────────────────────────────────────────────────
# This context is injected into every AI call as the system message.
# It teaches the AI everything it needs to know about Choice Properties,
# the US rental market, and how to produce high-quality listing content.

PLATFORM_CONTEXT = """
You are an expert AI assistant embedded in the Choice Properties Property Pipeline — an internal tool used by property managers and landlords to prepare rental listings before publishing them on the Choice Properties marketplace.

## About Choice Properties
Choice Properties is a tenant-first rental marketplace. The platform's core philosophy is:
- **Apply first, tour later** — tenants submit an application before scheduling a viewing. All language about "scheduling a showing", "contact us to see the unit", or "tours available" must be removed from listings.
- **No gatekeeping language** — listings must never mention credit score minimums, income multipliers (e.g. "must earn 3x rent"), background check requirements, "no Section 8", or any screening criteria. These are handled transparently by the platform.
- **Inclusive and welcoming** — listings should feel accessible and warm, not exclusive or intimidating.
- **Honest and accurate** — never invent details. Only use facts supported by the data provided.

## Your Role
You help prepare listings that are complete, accurate, attractive, and tenant-friendly. You understand the full data lifecycle: properties are scraped from Zillow, Realtor.com, and Redfin, then enriched and edited before being published live.

## US Rental Market Knowledge
Use this knowledge when inferring fields or evaluating pricing:

### Property Types and Typical Features
- **Single Family Home**: Usually has a garage or driveway parking, often has a basement (especially in Midwest/Northeast), typically forced air heating, central air common in homes built after 1980, in-unit laundry common after 2000, private yard.
- **Apartment / Multi-unit**: Usually shared laundry or no laundry (older buildings), window units or mini-splits, baseboard heat in older buildings, limited parking.
- **Condo / Townhouse**: Often HOA amenities (gym, pool), in-unit laundry typical in newer builds, assigned parking common, central air standard in modern builds.
- **Duplex/Triplex**: Often older buildings, shared laundry, may have yard access, parking varies.

### Age-Based Inferences
- Built before 1970: Likely radiator/baseboard heat, window AC units, no in-unit laundry, older appliances
- Built 1970–1990: Forced air becoming standard, central air in warmer states, shared laundry
- Built 1990–2010: Central HVAC standard, in-unit washer/dryer hookups common, dishwasher standard
- Built after 2010: Modern finishes, in-unit laundry standard, stainless appliances, smart features possible

### Lease Terms
- Standard US lease: 12-month is the default. Month-to-month as a secondary option is common.
- Short-term (3–6 month): Common in university towns, luxury units, and furnished rentals.

### Utilities
- Most US rentals: Tenant pays electric + gas. Landlord covers water, trash, sewer.
- Apartments: Sometimes water/trash included. Rarely all utilities included.
- Luxury rentals: May include more utilities as a differentiator.

### Pricing Context
- Evaluate rent reasonableness based on bedrooms and location (state/city if available).
- Obvious red flags: A 3BR home for $400/mo (too low, likely an error) or a studio for $8,000/mo (too high unless luxury market).
- When no city is available, use bedrooms and sqft as the main pricing signal.

### Pet Policies
- If pets_allowed is True: suggest "Dogs and cats welcome" or "Pet-friendly home — ask about our pet policy."
- If pets_allowed is False or unknown: omit pet policy from descriptions. Never say "no pets" in listing copy.
- Pet weight limits and breed restrictions are handled on the platform — do not include in copy.

### Common Amenities by Property Type
- Houses: yard, garage, driveway, storage, patio/deck
- Apartments: gym, pool, rooftop, doorman, concierge, elevator, common areas
- All: dishwasher, in-unit laundry, hardwood floors, high ceilings, natural light, updated kitchen/bath

## Listing Quality Standards
A great listing has:
1. A compelling description (3–4 paragraphs, no bullet points, no headers)
2. Accurate bedroom/bathroom counts
3. A stated monthly rent
4. At least one photo
5. A complete address
6. Key amenities and appliances listed
7. Clear lease terms
8. A welcoming, screening-free tone

A poor listing has:
- A generic or missing description
- Missing rent
- Boilerplate language copied from source sites
- Gatekeeping language (income requirements, credit minimums)
- Tour-first language
- Contradictory data (e.g. 2 beds but description says 3)
"""


# ── Client & Error Handling ────────────────────────────────────────────────────

def _get_client():
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="DEEPSEEK_API_KEY is not configured.")
    return OpenAI(api_key=api_key, base_url="https://api.deepseek.com")


def _handle_deepseek_error(e: Exception):
    if isinstance(e, AuthenticationError):
        raise HTTPException(
            status_code=401,
            detail="Invalid DeepSeek API key. Please check your DEEPSEEK_API_KEY in backend/.env."
        )
    if isinstance(e, RateLimitError):
        raise HTTPException(
            status_code=429,
            detail="DeepSeek rate limit reached. You are sending too many requests. Please wait a moment and try again."
        )
    if isinstance(e, APIStatusError):
        if e.status_code == 402:
            raise HTTPException(
                status_code=402,
                detail="DeepSeek credit exhausted. Your account balance is too low. Please top up at platform.deepseek.com to continue using AI features."
            )
        if e.status_code == 429:
            raise HTTPException(
                status_code=429,
                detail="DeepSeek rate limit reached. Please wait a moment and try again."
            )
        raise HTTPException(
            status_code=500,
            detail=f"DeepSeek API error ({e.status_code}): {e.message}"
        )
    if isinstance(e, APIConnectionError):
        raise HTTPException(
            status_code=503,
            detail="Could not connect to DeepSeek. Please check your internet connection and try again."
        )
    raise HTTPException(status_code=500, detail=str(e))


def _call_deepseek(system: str, user: str, temperature: float = 0.7) -> str:
    try:
        client = _get_client()
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
        )
        return response.choices[0].message.content.strip()
    except HTTPException:
        raise
    except Exception as e:
        _handle_deepseek_error(e)


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


class IssuesRequest(BaseModel):
    property: PropertyContext


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
2. NEVER include credit scores, income requirements, income multipliers, background check language, "no Section 8", rental history requirements, or any tenant screening criteria.
3. NEVER say "no pets." Either omit the pet policy entirely or say "ask about our pet policy."
4. NEVER invent facts. Only describe what is supported by the property data above.
5. NEVER copy boilerplate phrases like "don't miss this gem", "call today", "motivated landlord."
6. Focus on what makes this home livable and enjoyable: layout, light, space, comfort, location, amenities.
7. Structure: 2–4 paragraphs. No bullet points. No headline or title. Body text only.
8. End with a soft call to action about applying — e.g. "Ready to call this home? Submit your application today and take the first step."
9. Return ONLY the description text. Nothing else — no labels, no preamble, no quotes."""

    try:
        result = _call_deepseek(PLATFORM_CONTEXT, user_prompt, temperature=0.75)
        return {"description": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("AI rewrite failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ai/detect-issues")
def detect_issues(req: IssuesRequest):
    prop_summary = _build_property_summary(req.property)

    user_prompt = f"""Perform a full quality control review of this rental listing before it is published.

PROPERTY DATA:
{prop_summary}

REVIEW CHECKLIST — evaluate every category below:

ERRORS (blocking issues — listing should not publish without fixing):
- Missing rent amount
- Missing address or location
- Missing bedroom or bathroom count
- Completely missing description
- Contradictory data (e.g. description says 3 beds but field says 2)
- Rent is implausibly low or high for the bedroom count and location

WARNINGS (should fix before publishing — affects quality or trust):
- Description is too short (under 50 words)
- Description is generic, templated, or reads like copy-pasted boilerplate
- Description mentions tours, showings, or "contact to schedule" — violates platform rules
- Description includes screening criteria (credit score, income, background check) — violates platform rules
- Description includes hard "no pets" language — violates platform guidelines
- Missing square footage for a home listing
- No amenities listed at all
- No appliances listed
- Missing lease terms
- Missing parking info for a house or condo

SUGGESTIONS (nice to have — improves listing quality):
- Description could benefit from stronger opening line
- Amenities list seems incomplete for this property type/age
- Pet policy not addressed (if pets_allowed is True)
- Move-in special not mentioned (could attract more applicants)
- Utilities policy unclear
- Flooring not specified
- Year built would strengthen the listing

Return a JSON array. Each item must have exactly these keys:
- "severity": one of "error", "warning", or "suggestion"
- "field": the specific field name this relates to, or "general" for overall listing issues
- "message": a clear, specific, actionable description of the issue (1–2 sentences max)

Rules:
- Only include real issues. Do not flag things that are fine.
- Do not hallucinate issues that don't exist in the data.
- Order by severity: errors first, then warnings, then suggestions.
- Return ONLY a raw JSON array. No markdown, no explanation, no wrapper object."""

    try:
        raw = _call_deepseek(PLATFORM_CONTEXT, user_prompt, temperature=0.2)
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        issues = json.loads(raw)
        return {"issues": issues}
    except json.JSONDecodeError:
        return {"issues": [], "raw": raw}
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
        result = _call_deepseek(PLATFORM_CONTEXT, user_prompt, temperature=0.3)
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
        client = _get_client()
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
        _handle_deepseek_error(e)


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
        raw = _call_deepseek(PLATFORM_CONTEXT, user_prompt, temperature=0.3)
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        suggestions = json.loads(raw)
        filtered = {k: v for k, v in suggestions.items() if k in valid_fields}
        return {"suggestions": filtered}
    except json.JSONDecodeError:
        return {"suggestions": {}, "raw": raw}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("AI autofill failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ── Bulk Scan ──────────────────────────────────────────────────────────────────

class BulkScanItem(BaseModel):
    id: str
    property: PropertyContext


class BulkScanRequest(BaseModel):
    properties: list[BulkScanItem]


@router.post("/ai/bulk-scan")
def bulk_scan(req: BulkScanRequest):
    if not req.properties:
        return {"results": []}

    BATCH_SIZE = 8
    all_results = []

    for i in range(0, len(req.properties), BATCH_SIZE):
        batch = req.properties[i:i + BATCH_SIZE]
        listings_block = ""
        for item in batch:
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

Return a JSON array. One object per listing, in the same order. Each object:
- "id": the listing ID exactly as given
- "errors": integer count of errors found
- "warnings": integer count of warnings found
- "suggestions": integer count of suggestions found
- "top_issue": a single short string describing the most critical problem, or null if none

Return ONLY a raw JSON array. No markdown, no explanation."""

        try:
            raw = _call_deepseek(PLATFORM_CONTEXT, user_prompt, temperature=0.1)
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            batch_results = json.loads(raw)
            all_results.extend(batch_results)
        except Exception as e:
            logger.error("AI bulk scan batch failed: %s", e)
            for item in batch:
                all_results.append({"id": item.id, "errors": 0, "warnings": 0, "suggestions": 0, "top_issue": None})

    return {"results": all_results}


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
- 0–44 (F): Major problems, requires significant work

Return ONLY a raw JSON object. No markdown, no explanation."""

    try:
        raw = _call_deepseek(PLATFORM_CONTEXT, user_prompt, temperature=0.2)
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        result = json.loads(raw)
        return result
    except json.JSONDecodeError:
        return {"score": 0, "grade": "?", "headline": "Could not evaluate listing.", "strengths": [], "critical_fixes": [], "improvements": [], "publish_ready": False}
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
- Current US rental market conditions (2024–2025)

Return a JSON object with these exact keys:
- "assessment": one of "very_low", "low", "fair", "high", "very_high", or "unknown" (use unknown only if rent is missing)
- "confidence": one of "high", "medium", "low" — how confident you are in the assessment
- "market_context": 1–2 sentences explaining the typical rent range for this type of property in this location
- "verdict": 1–2 sentences assessing whether this specific rent is appropriate
- "recommendation": one concrete, actionable sentence (e.g. "Consider pricing between $X–$Y to stay competitive" or "This rent is well-positioned for the market")
- "comparable_range": string like "$1,800–$2,200/mo" representing the typical market range for this type of property, or null if unknown

Return ONLY a raw JSON object. No markdown, no explanation."""

    try:
        raw = _call_deepseek(PLATFORM_CONTEXT, user_prompt, temperature=0.2)
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        result = json.loads(raw)
        return result
    except json.JSONDecodeError:
        return {"assessment": "unknown", "confidence": "low", "market_context": "", "verdict": "Could not evaluate pricing.", "recommendation": "", "comparable_range": None}
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
- "optimized_opening": a rewritten first sentence or two that's more SEO-friendly, keeping the tenant-first tone and removing any tour/screening language

Return ONLY a raw JSON object. No markdown, no explanation."""

    try:
        raw = _call_deepseek(PLATFORM_CONTEXT, user_prompt, temperature=0.3)
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        result = json.loads(raw)
        return result
    except json.JSONDecodeError:
        return {"score": 0, "missing_keywords": [], "present_keywords": [], "title_suggestion": "", "improvements": [], "optimized_opening": ""}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("AI SEO optimize failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
