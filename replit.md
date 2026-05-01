# Property Pipeline — Replit Workspace

## ECOSYSTEM OVERVIEW — Read This First

This project is one half of a two-project ecosystem. Both share the same Supabase database.

| Project | Repo | What it is |
|---|---|---|
| **This project** | [choice121/property-pipeline](https://github.com/choice121/property-pipeline) | Private internal tool: scrape → manage → publish listings |
| **Choice Website** | [choice121/Choice](https://github.com/choice121/Choice) | Public rental website tenants use to browse and apply |

See `ECOSYSTEM.md` (in this repo) for the full cross-project architecture, schema ownership, and rules.

---

## What This App Does

Scrapes property listings from Zillow, Realtor.com, and Redfin → stores them in a private staging database → lets the owner view, edit, and AI-enrich them → publishes approved listings to the live Choice Properties website.

**Live Website:** https://choice-properties-site.pages.dev/
**Property page format:** https://choice-properties-site.pages.dev/property.html?id={PROP-ID}

---

## Architecture

- **Backend**: Python FastAPI on port 8000
- **Frontend**: React 18 + Vite on port 5000 (proxies `/api` → backend)
- **Pipeline Database**: Supabase `pipeline` schema — `pipeline.pipeline_properties`, `pipeline.pipeline_enrichment_log`, `pipeline.pipeline_scrape_runs`, `pipeline.pipeline_chat_conversations`
- **Live Publishing**: Supabase `public` schema — `public.properties`, `public.property_photos`
- **Image CDN**: ImageKit (same account as Choice website)
- **AI**: DeepSeek V3 via OpenAI-compatible SDK

### Supabase Schema Split (CRITICAL)

Both this project and the Choice website use the **same** Supabase project (`tlfmwetmhthpyrytrcfo`).

```
pipeline schema (this project owns)     public schema (Choice website owns)
────────────────────────────────        ──────────────────────────────────
pipeline.pipeline_properties     ──→    public.properties  (published listings)
pipeline.pipeline_enrichment_log        public.property_photos
pipeline.pipeline_scrape_runs           public.landlords
pipeline.pipeline_chat_conversations    public.applications, public.leases …
```

The pipeline tables were moved to the private `pipeline` schema by Choice website migration `20260426000002_pipeline_private_schema.sql`. The backend accesses them via `client.schema("pipeline")`.

**Code rule**: All pipeline table access uses `get_pipeline_schema()` from `backend/database/supabase_client.py`. All public table access (publisher, live_sync) uses `get_supabase()`.

---

## One-Time Supabase Setup Required

Before the app is fully operational, expose the `pipeline` schema in Supabase:

1. Go to: **https://supabase.com/dashboard/project/tlfmwetmhthpyrytrcfo/settings/api**
2. Add `pipeline` to **"Extra schemas to expose in your API"**
3. Save → Recheck in the app

Full details in `SETUP_SUPABASE.md`.

---

## AI System (DeepSeek V3)

All AI features use `deepseek-chat` via `base_url="https://api.deepseek.com"`.

### AI Endpoints (`backend/routers/ai.py`)
- `POST /ai/autofill` — suggests values for empty fields
- `POST /ai/rewrite-description` — generates polished listing descriptions (streaming)
- `POST /ai/detect-issues` — scans for errors/warnings/suggestions; returns `{"issues":[...], "quality_score":N}`
- `POST /ai/suggest-field` — suggests a value for a single field
- `POST /ai/chat` — freeform assistant chat about the property (streaming)
- `POST /ai/bulk-scan` — batch scans up to N listings
- `POST /ai/score` — quality score (0–100) + grade (A–F) + evaluation
- `POST /ai/pricing-intel` — market pricing analysis
- `POST /ai/seo-optimize` — SEO keyword analysis + title + opening
- `POST /ai/clean` — Deep Clean Engine: strips boilerplate, rewrites in brand voice
- `POST /ai/bulk-clean` — library-wide bulk clean
- `POST /ai/generate-title` — specific, compelling listing title
- `POST /ai/extract-features` — LLM amenity/appliance extraction
- `POST /ai/neighborhood-context` — 2–3 sentence neighborhood paragraph
- `POST /ai/check-duplicates` — fuzzy address duplicate detection

### AI Auto-Enrichment (`backend/services/ai_enricher.py`)
Runs automatically on scrape. Tasks: generate_description, extract_features, infer_pet_policy, classify_property_type, generate_title.

---

## Project Structure

```
property-pipeline/
├── ECOSYSTEM.md             ← Cross-project architecture (read before any cross-repo work)
├── SETUP_SUPABASE.md        ← One-time Supabase setup guide
├── AI_HANDOFF.md            ← AI implementation status + rules for incoming AI sessions
├── backend/
│   ├── database/
│   │   ├── supabase_client.py  ← get_supabase() [public] + get_pipeline_schema() [pipeline]
│   │   ├── repository.py       ← All CRUD — uses _pipeline for pipeline_ tables
│   │   ├── db.py               ← get_db() FastAPI dependency
│   │   └── models.py           ← Re-exports PropertyRecord as Property
│   ├── routers/            ← API endpoints
│   ├── services/           ← Business logic
│   │   ├── publisher_service.py  ← Writes to public.properties + property_photos
│   │   ├── live_sync_service.py  ← Reads from public.properties
│   │   └── setup_service.py      ← Validates credentials + schema accessibility
│   └── main.py             ← FastAPI entry point
├── frontend/
│   └── src/
│       ├── components/     ← PropertyCard, AiAssistant, PublishButton, etc.
│       └── pages/          ← Library, Scraper, Editor, Audit
├── start.sh                ← Unified startup script
└── supabase_migration.sql  ← LEGACY — tables already exist in pipeline schema, do not re-run
```

---

## Running the App

| Environment | Command |
|---|---|
| Replit | Click Run |
| Terminal | `bash start.sh` or `make` |
| Docker | `docker-compose up --build` |

---

## Environment & Credentials

| Variable | Required | Purpose |
|---|---|---|
| `SUPABASE_URL` | ✅ Yes | `https://tlfmwetmhthpyrytrcfo.supabase.co` |
| `SUPABASE_SERVICE_ROLE_KEY` | ✅ Yes | Full DB access (pipeline + public schemas) |
| `IMAGEKIT_PUBLIC_KEY` | ✅ For publishing | ImageKit upload auth |
| `IMAGEKIT_PRIVATE_KEY` | ✅ For publishing | ImageKit server-side upload |
| `IMAGEKIT_URL_ENDPOINT` | ✅ For publishing | ImageKit CDN base URL |
| `DEEPSEEK_API_KEY` | ⚡ Recommended | All AI features |
| `SUPABASE_ANON_KEY` | Optional | Used by public website tooling |
| `CHOICE_LANDLORD_ID` | Optional | Auto-resolved from landlords table if unset |

---

## Cross-Project Rules (for AI working on this repo)

- ✅ Read/write `pipeline` schema tables freely
- ✅ Write to `public.properties` and `public.property_photos` via the publisher only
- ❌ Never write to any other `public` schema table
- ❌ Never run ad-hoc SQL — add migrations to `choice121/Choice/supabase/migrations/`
- ❌ Never alter `public.properties` column structure without checking `publisher_service.py`
- ❌ Never drop the `pipeline` schema or revoke service_role access from it

## If You Need to Understand the Choice Website

- Architecture: `choice121/Choice/README.md`
- AI instructions for Choice: `choice121/Choice/.github/copilot-instructions.md`
- Edge Functions: `choice121/Choice/supabase/functions/`
- The Choice website deploys to Cloudflare Pages — it is NOT hosted on Replit
- Supabase migrations for the entire ecosystem: `choice121/Choice/supabase/migrations/`

---

## Mobile-First Architecture

The frontend is built phone-first. Property managers use this on a phone in the field.

- **PWA**: Installable, service worker, offline-first via TanStack Query
- **Touch**: BottomSheet, PullToRefresh, SwipeableCard, long-press multi-select
- **Imagery**: ImageKit transformations via `frontend/src/utils/imageUrl.js`

---

## Key Dependencies

### Backend (Python 3.11)
- FastAPI + Uvicorn, supabase-py ≥2.4, HomeHarvest, Pillow, httpx, openai-compatible SDK

### Frontend (Node)
- React 18, React Router v6, Vite 5, Tailwind CSS v4, TanStack Query, Axios

---

## GitHub

- Pipeline repo: `https://github.com/choice121/property-pipeline`
- Choice website repo: `https://github.com/choice121/Choice`
- Push instructions: use `GITHUB_TOKEN` env var (see `AI_HANDOFF.md`)
