import os
from datetime import datetime

from supabase import create_client


CORE_KEYS = {
    "SUPABASE_URL": "Connects this pipeline to the shared Choice Properties Supabase project.",
    "SUPABASE_SERVICE_ROLE_KEY": "Lets the backend read/write pipeline and live listing records securely.",
}

PUBLISHING_KEYS = {
    "IMAGEKIT_PRIVATE_KEY": "Lets the backend upload listing photos to ImageKit.",
    "IMAGEKIT_PUBLIC_KEY": "Identifies the ImageKit account for listing photo delivery.",
    "IMAGEKIT_URL_ENDPOINT": "Points the app to the correct ImageKit CDN endpoint.",
}

OPTIONAL_KEYS = {
    "CHOICE_LANDLORD_ID": "Optional override for landlord assignment. If absent, the backend tries to resolve the landlord from Supabase.",
    "SUPABASE_ANON_KEY": "Used by the public website and some static-site tooling.",
    "DEEPSEEK_API_KEY": "Enables AI autofill, rewrite, pricing, SEO, and scan tools.",
}


def _key_status(keys: dict[str, str]) -> list[dict]:
    return [
        {
            "key": key,
            "present": bool(os.environ.get(key, "").strip()),
            "description": description,
        }
        for key, description in keys.items()
    ]


def _missing(keys: dict[str, str]) -> list[str]:
    return [key for key in keys if not os.environ.get(key, "").strip()]


def _check_supabase() -> dict:
    missing = _missing(CORE_KEYS)
    if missing:
        return {
            "ok": False,
            "message": "Supabase is not configured.",
            "missing": missing,
            "checks": [],
        }

    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()

    if url.startswith("https://placeholder") or key == "placeholder_key":
        return {
            "ok": False,
            "message": "Using placeholder Supabase credentials. Configure real credentials for full functionality.",
            "missing": [],
            "checks": [{"name": "credentials", "ok": False, "note": "placeholder values detected"}],
        }

    checks = []
    try:
        client = create_client(url.rstrip("/"), key)

        # pipeline schema — tables owned by this pipeline project
        # Requires the `pipeline` schema to be exposed in Supabase's PostgREST settings.
        # If this check fails with PGRST106 "Invalid schema", follow the one-step
        # setup in SETUP_SUPABASE.md: expose the `pipeline` schema in the dashboard.
        pipeline_client = client.schema("pipeline")
        pipeline_client.table("pipeline_properties").select("id").limit(1).execute()
        checks.append({"name": "pipeline.pipeline_properties", "ok": True})

        # public schema — live-site table owned by the Choice website
        client.table("properties").select("id").limit(1).execute()
        checks.append({"name": "public.properties", "ok": True})

        return {
            "ok": True,
            "message": "Supabase connection and required tables verified.",
            "missing": [],
            "checks": checks,
        }
    except Exception as exc:
        raw_message = str(exc)
        if "Invalid API key" in raw_message or "401" in raw_message:
            message = (
                "Supabase rejected the configured API key. "
                "Replace SUPABASE_SERVICE_ROLE_KEY with a valid service-role key."
            )
        elif "PGRST106" in raw_message or "Invalid schema" in raw_message:
            message = (
                "Supabase connected, but the pipeline schema is not exposed. "
                "Follow the one-step setup in SETUP_SUPABASE.md to expose the "
                "`pipeline` schema in your Supabase dashboard."
            )
        elif "pipeline_properties" in raw_message or "pipeline" in raw_message:
            message = (
                "Supabase connected but pipeline tables not found. "
                "Expose the `pipeline` schema in Supabase dashboard settings."
            )
        else:
            message = "Supabase verification failed. Check SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY."
        return {
            "ok": False,
            "message": message,
            "missing": [],
            "checks": checks,
        }


def get_setup_status() -> dict:
    core_missing = _missing(CORE_KEYS)
    publishing_missing = _missing(PUBLISHING_KEYS)
    optional_missing = _missing(OPTIONAL_KEYS)
    supabase = _check_supabase()

    core_ready = not core_missing and supabase["ok"]
    publishing_ready = not publishing_missing
    fully_configured = core_ready and publishing_ready

    if fully_configured:
        summary = "Ready for live syncing and publishing."
    elif core_ready:
        summary = "Core app is ready; publishing setup is incomplete."
    elif core_missing:
        summary = "Required Supabase setup is missing."
    elif "pipeline schema" in supabase.get("message", ""):
        summary = "Supabase connected — expose the pipeline schema to complete setup."
    else:
        summary = "Supabase setup is present but failed verification."

    return {
        "checked_at": datetime.utcnow().isoformat(),
        "summary": summary,
        "core_ready": core_ready,
        "publishing_ready": publishing_ready,
        "fully_configured": fully_configured,
        "groups": {
            "core":       _key_status(CORE_KEYS),
            "publishing": _key_status(PUBLISHING_KEYS),
            "optional":   _key_status(OPTIONAL_KEYS),
        },
        "missing": {
            "core":       core_missing,
            "publishing": publishing_missing,
            "optional":   optional_missing,
        },
        "services": {
            "supabase": supabase,
            "imagekit": {
                "ok": not any(k.startswith("IMAGEKIT_") for k in publishing_missing),
                "message": (
                    "ImageKit credentials are present."
                    if not any(k.startswith("IMAGEKIT_") for k in publishing_missing)
                    else "ImageKit credentials are incomplete."
                ),
            },
        },
    }
