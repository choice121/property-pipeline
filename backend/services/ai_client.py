import logging
import os
import time

from fastapi import HTTPException
from openai import OpenAI, AuthenticationError, RateLimitError, APIStatusError, APIConnectionError

logger = logging.getLogger(__name__)

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

PROMPT_VERSION = "v3"

_GEMINI_BASE_URL    = "https://generativelanguage.googleapis.com/v1beta/openai/"
_GEMINI_MODEL       = "gemini-2.0-flash"
_DEEPSEEK_BASE_URL  = "https://api.deepseek.com"
_DEEPSEEK_MODEL     = "deepseek-chat"
_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
_OPENROUTER_MODEL   = "anthropic/claude-3.5-sonnet"


def get_client() -> tuple[OpenAI, str]:
    """
    Returns (client, model_name).
    Priority: OpenRouter → Gemini → DeepSeek.
    """
    openrouter_key = os.environ.get("OPENROUTER_API_KEY")
    if openrouter_key:
        return (
            OpenAI(
                api_key=openrouter_key,
                base_url=_OPENROUTER_BASE_URL,
                default_headers={
                    "HTTP-Referer": "https://choiceproperties.app",
                    "X-Title": "Choice Properties Pipeline",
                },
            ),
            _OPENROUTER_MODEL,
        )

    gemini_key = os.environ.get("GEMINI_API_KEY")
    if gemini_key:
        return (
            OpenAI(api_key=gemini_key, base_url=_GEMINI_BASE_URL),
            _GEMINI_MODEL,
        )

    deepseek_key = os.environ.get("DEEPSEEK_API_KEY")
    if deepseek_key:
        return (
            OpenAI(api_key=deepseek_key, base_url=_DEEPSEEK_BASE_URL),
            _DEEPSEEK_MODEL,
        )

    raise HTTPException(
        status_code=500,
        detail="No AI API key configured. Set OPENROUTER_API_KEY, GEMINI_API_KEY, or DEEPSEEK_API_KEY.",
    )


def handle_deepseek_error(e: Exception):
    if isinstance(e, AuthenticationError):
        raise HTTPException(
            status_code=401,
            detail="Invalid AI API key. Please check your GEMINI_API_KEY or DEEPSEEK_API_KEY."
        )
    if isinstance(e, RateLimitError):
        raise HTTPException(
            status_code=429,
            detail="AI rate limit reached. Please wait a moment and try again."
        )
    if isinstance(e, APIStatusError):
        if e.status_code == 402:
            raise HTTPException(
                status_code=402,
                detail="AI API credit exhausted. Please top up your account."
            )
        if e.status_code == 429:
            raise HTTPException(
                status_code=429,
                detail="AI rate limit reached. Please wait a moment and try again."
            )
        raise HTTPException(
            status_code=500,
            detail=f"AI API error ({e.status_code}): {e.message}"
        )
    if isinstance(e, APIConnectionError):
        raise HTTPException(
            status_code=503,
            detail="Could not connect to AI provider. Please check your internet connection."
        )
    raise HTTPException(status_code=500, detail=str(e))


def verify_facts(generated_text: str, fact_data: dict) -> bool:
    """
    Basic fact verification to prevent AI hallucinations.
    Checks if generated content contradicts known facts about the property.
    Returns False if contradictions found, True if content appears factual.
    """
    text_lower = generated_text.lower()

    # Check bedroom/bathroom counts
    if "bedrooms" in fact_data and fact_data["bedrooms"] is not None:
        bed_count = fact_data["bedrooms"]
        # Look for contradictory bedroom mentions
        if bed_count == 0 and ("bedroom" in text_lower or "bed" in text_lower):
            if "studio" not in text_lower:
                return False
        elif bed_count > 0:
            # Check if text mentions different bedroom count
            import re
            bed_matches = re.findall(r'(\d+)\s*(?:bed|bedroom)', text_lower)
            if bed_matches and str(bed_count) not in bed_matches:
                return False

    # Check rent amounts
    if "monthly_rent" in fact_data and fact_data["monthly_rent"] is not None:
        rent = fact_data["monthly_rent"]
        # Look for rent figures that are way off (more than 50% difference)
        import re
        rent_matches = re.findall(r'\$([0-9,]+)', generated_text)
        for match in rent_matches:
            match_clean = int(match.replace(',', ''))
            if abs(match_clean - rent) / rent > 0.5:  # More than 50% difference
                return False

    # Check property type consistency
    if "property_type" in fact_data and fact_data["property_type"]:
        prop_type = fact_data["property_type"].lower()
        if prop_type == "apartment" and "house" in text_lower and "apartment" not in text_lower:
            return False
        if prop_type == "house" and "apartment" in text_lower and "house" not in text_lower:
            return False

    return True


def call_deepseek(
    system: str,
    user: str,
    temperature: float = 0.7,
    json_mode: bool = False,
    max_retries: int = 3,
    fact_check_data: dict | None = None,
) -> str:
    """
    Unified AI caller with retry logic and optional JSON mode.
    Uses Gemini if GEMINI_API_KEY is set, otherwise falls back to DeepSeek.

    - json_mode=True enforces valid JSON output from the model.
    - Retries up to max_retries times on rate limit or transient server errors.
    - Backs off exponentially: 1s, 2s, 4s between attempts.
    - Fails immediately on auth errors or credit exhaustion.
    - fact_check_data: dict of ground truth facts to verify against hallucinations
    """
    last_error = None

    for attempt in range(max_retries):
        try:
            client, model = get_client()
            kwargs = dict(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=temperature,
            )
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}

            response = client.chat.completions.create(**kwargs)
            result = response.choices[0].message.content.strip()

            # Fact verification layer
            if fact_check_data and not verify_facts(result, fact_check_data):
                logger.warning("AI output failed fact verification, retrying...")
                if attempt < max_retries - 1:
                    time.sleep(1)
                    continue
                else:
                    logger.warning("AI output failed fact verification, using anyway")
                    # Could implement fallback to template generation here

            return result

        except HTTPException:
            raise

        except (AuthenticationError, APIStatusError) as e:
            is_auth = isinstance(e, AuthenticationError)
            is_credit = isinstance(e, APIStatusError) and e.status_code == 402
            is_retryable = isinstance(e, APIStatusError) and e.status_code in (429, 500, 502, 503)

            if is_auth or is_credit:
                handle_deepseek_error(e)

            if is_retryable:
                last_error = e
                wait = 2 ** attempt
                logger.warning(
                    "AI API error %s, retrying in %ds (attempt %d/%d)",
                    getattr(e, "status_code", "?"), wait, attempt + 1, max_retries,
                )
                time.sleep(wait)
                continue

            handle_deepseek_error(e)

        except RateLimitError as e:
            last_error = e
            wait = 2 ** attempt
            logger.warning(
                "AI rate limit hit, retrying in %ds (attempt %d/%d)",
                wait, attempt + 1, max_retries,
            )
            time.sleep(wait)

        except APIConnectionError as e:
            last_error = e
            wait = 2 ** attempt
            logger.warning(
                "AI connection error, retrying in %ds (attempt %d/%d)",
                wait, attempt + 1, max_retries,
            )
            time.sleep(wait)

        except Exception as e:
            handle_deepseek_error(e)

    handle_deepseek_error(last_error)
