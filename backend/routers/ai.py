import json
import logging
import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from google import genai

logger = logging.getLogger(__name__)
router = APIRouter()


def _get_client():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY is not configured.")
    return genai.Client(api_key=api_key)


def _call_gemini(prompt: str) -> str:
    client = _get_client()
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
    )
    return response.text.strip()


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


def _build_property_summary(prop: PropertyContext) -> str:
    parts = []
    if prop.address:
        location = ", ".join(filter(None, [prop.address, prop.city, prop.state]))
        parts.append(f"Address: {location}")
    if prop.property_type:
        parts.append(f"Type: {prop.property_type}")
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
        parts.append(f"\nCurrent description:\n{prop.description}")
    return "\n".join(parts)


@router.post("/ai/rewrite-description")
def rewrite_description(req: RewriteRequest):
    prop_summary = _build_property_summary(req.property)
    tone_instruction = {
        "professional": "professional and polished, suitable for a premium rental marketplace",
        "friendly": "warm and inviting, written in a conversational tone",
        "concise": "short and punchy — highlight only the top features in 2-3 sentences",
    }.get(req.tone, "professional and polished")

    prompt = f"""You are a real estate copywriter. Write a compelling rental property listing description.

Property details:
{prop_summary}

Instructions:
- Tone: {tone_instruction}
- Highlight the best features naturally
- Do NOT invent facts not present in the property details
- Write 2-4 short paragraphs
- Do NOT include a headline or title — just the body text
- Do NOT use bullet points
- Return only the description text, nothing else"""

    try:
        result = _call_gemini(prompt)
        return {"description": result}
    except Exception as e:
        logger.error("AI rewrite failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ai/detect-issues")
def detect_issues(req: IssuesRequest):
    prop_summary = _build_property_summary(req.property)

    prompt = f"""You are a quality control assistant for rental property listings. Review the property below and identify any issues, inconsistencies, or things that could be improved before publishing.

Property details:
{prop_summary}

Return a JSON array of issue objects. Each object must have:
- "severity": "error", "warning", or "suggestion"
- "field": the property field name the issue relates to (or "general")
- "message": a short, clear description of the issue

Focus on:
- Missing critical information (rent, beds/baths, address)
- Inconsistencies (e.g. bathrooms don't add up)
- Description quality problems (too short, generic, or vague)
- Pricing anomalies (e.g. very high or low rent for the area/size)
- Policy gaps (no pet policy, no lease terms)

Return ONLY a raw JSON array, no markdown, no explanation."""

    try:
        raw = _call_gemini(prompt)
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        issues = json.loads(raw)
        return {"issues": issues}
    except json.JSONDecodeError:
        return {"issues": [], "raw": raw}
    except Exception as e:
        logger.error("AI issue detection failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ai/suggest-field")
def suggest_field(req: SuggestRequest):
    prop_summary = _build_property_summary(req.property)

    prompt = f"""You are a real estate data assistant. Based on the property details below, suggest a good value for the field "{req.field}".

Property details:
{prop_summary}

{("Current value: " + req.current_value) if req.current_value else "This field is currently empty."}

Instructions:
- Return only the suggested value as plain text
- Keep it concise and realistic
- Base your suggestion on the other property details
- Do not include explanations or quotes"""

    try:
        result = _call_gemini(prompt)
        return {"suggestion": result}
    except Exception as e:
        logger.error("AI suggest field failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ai/chat")
def chat_with_property(req: ChatRequest):
    prop_summary = _build_property_summary(req.property)

    history_text = ""
    if req.history:
        for msg in req.history[-6:]:
            role = "You" if msg.get("role") == "user" else "Assistant"
            history_text += role + ": " + msg.get("content", "") + "\n"

    history_section = ("Previous conversation:\n" + history_text) if history_text else ""

    prompt = f"""You are a helpful assistant for a property manager using an internal listing tool called Property Pipeline. You have full context of the current property being edited.

Property details:
{prop_summary}

{history_section}
User: {req.message}

Instructions:
- Answer helpfully and concisely based on the property context
- You can help edit descriptions, suggest values, flag issues, or answer questions
- Stay focused on the property and listing tasks
- If asked to write or rewrite something, provide the full text directly
- Keep responses brief unless a longer answer is needed"""

    try:
        result = _call_gemini(prompt)
        return {"reply": result}
    except Exception as e:
        logger.error("AI chat failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
