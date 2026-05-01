# Property Pipeline — Replit Workspace

## ECOSYSTEM OVERVIEW — Read This First

This project is one half of a two-project ecosystem. Both share the same Supabase database.

| Project | Repo | What it is |
|---|---|---|
| **This project** | [choice121/property-pipeline](https://github.com/choice121/property-pipeline) | Private internal tool: scrape → manage → publish listings |
| **Choice Website** | [choice121/Choice](https://github.com/choice121/Choice) | Public rental website tenants use to browse and apply |

See `ECOSYSTEM.md` (in this repo) for the full cross-project architecture, schema ownership, and rules.
See `AI_HANDOFF.md` for implementation status, known issues, and rules for incoming AI sessions.

---

## What This App Does

Scrapes property listings from Zillow, Realtor.com, Redfin, HotPads, Craigslist, Apartments.com, Opendoor, Invitation Homes, Progress Residential → stores them in a private staging database → lets the owner view, edit, and AI-enrich them → publishes approved listings to the live Choice Properties website with up to **40 photos** per listing.

**Live Website:** https://choice-properties-site.pages.dev/
**Property page format:** https://choice-properties-site.pages.dev/property.html?id={PROP-ID}

---

## System Status (May 2026) — Fully Operational ✅

- ✅ Supabase pipeline schema exposed (configured via Management API)
- ✅ 1,000+ properties in staging
- ✅ Publisher writing to `public.properties` + `public.property_photos`
- ✅ AI enrichment working (gemini-2.0-flash)
- ✅ All scrapers working (httpx proxy fix applied)
- ✅ Live sync running

---

## Architecture

- **Backend**: Python FastAPI on port 8000
- **Frontend**: React 18 + Vite on port 5000 (proxies `/api` → backend)
- **Pipeline Database**: Supabase `pipeline` schema
- **Live Publishing**: Supabase `public` schema — `public.properties`, `public.property_photos`
- **Image CDN**: ImageKit (same account as Choice website)
- **AI**: gemini-2.0-flash (primary) → Claude via OpenRouter → DeepSeek (fallbacks)

### Supabase Schema Split (CRITICAL)

Both this project and the Choice website use the **same** Supabase project (`tlfmwetmhthpyrytrcfo`).

```
pipeline schema (this project owns)     public schema (Choice website owns)
────────────────────────────────        ──────────────────────────────────
pipeline.pipeline_properties     ──→    public.properties  (published listings)
pipeline.pipeline_enrichment_log        public.property_photos (ImageKit URLs)
pipeline.pipeline_scrape_runs           public.landlords
pipeline.pipeline_chat_conversations    public.applications, public.leases …
```

**Code rule**: All pipeline table access uses `get_pipeline_schema()` from `backend/database/supabase_client.py`. All public table access (publisher, live_sync) uses `get_supabase()`.

---

## CRITICAL: Photos Are In property_photos Table

Choice website migration `20260426000002` **removed** `photo_urls` and `photo_file_ids` from `public.properties`. Photos now live in `public.property_photos`:

```
property_id   text   -- "PROP-BF860F35"
url           text   -- ImageKit CDN URL
file_id       text   -- ImageKit file ID
display_order int    -- 0-indexed
alt_text      text
```

**Never reference `photo_urls` or `photo_file_ids`** — those columns no longer exist. All code has been updated. See `publisher_service.py`, `live_sync_service.py`, and `live_images.py`.

---

## Supabase Setup — Already Complete

The `pipeline` schema is already exposed to PostgREST. No manual action needed. See `SETUP_SUPABASE.md` if you ever need to re-configure it.

---

## AI System

All AI features go through `backend/services/ai_client.py`.

**Active model**: `gemini-2.0-flash` (do NOT use `gemini-1.5-pro` — deprecated/removed)

### AI Endpoints (`backend/routers/ai.py`)
- `POST /ai/autofill` — suggests values for empty fields
- `POST /ai/rewrite-description` — generates polished listing descriptions (streaming)
- `POST /ai/detect-issues` — scans for errors/warnings/suggestions
- `POST /ai/suggest-field` — suggests a value for a single field
- `POST /ai/chat` — freeform assistant chat about the property (streaming)
- `POST /ai/bulk-scan` — batch scans up to N listings
- `POST /ai/score` — quality score (0–100) + grade (A–F)
- `POST /ai/pricing-intel` — market pricing analysis
- `POST /ai/seo-optimize` — SEO keyword analysis
- `POST /ai/clean` — Deep Clean Engine: strips boilerplate
- `POST /ai/bulk-clean` — library-wide bulk clean
- `POST /ai/generate-title` — specific listing title
- `POST /ai/extract-features` — LLM amenity/appliance extraction
- `POST /ai/neighborhood-context` — neighborhood paragraph
- `POST /ai/check-duplicates` — fuzzy duplicate detection

### AI Auto-Enrichment (`backend/services/ai_enricher.py`)
Runs automatically on scrape. Tasks: generate_description, extract_features, infer_pet_policy, classify_property_type, generate_title.

---

## Project Structure

```
property-pipeline/
├── ECOSYSTEM.md             ← Cross-project architecture (read before any cross-repo work)
├── SETUP_SUPABASE.md        ← Supabase setup reference (already configured)
├── AI_HANDOFF.md            ← AI implementation status, known issues, phase log
├── backend/
│   ├── database/
│   │   ├── supabase_client.py  ← get_supabase() [public] + get_pipeline_schema() [pipeline]
│   │   ├── repository.py       ← All CRUD — _pipeline for pipeline_ tables, _client for public
│   │   ├── db.py               ← get_db() FastAPI dependency
│   │   └── models.py           ← Re-exports PropertyRecord as Property
│   ├── routers/
│   │   ├── scraper.py          ← Scrape + POST /properties/{id}/redownload-images
│   │   ├── publisher.py        ← Publish, refresh-images, sync-fields
│   │   ├── live_images.py      ← Read/write property_photos table
│   │   ├── images.py           ← Local image management, watermark scan
│   │   ├── properties.py       ← CRUD endpoints for pipeline properties
│   │   ├── sync.py             ← Live sync from public.properties
│   │   └── ai.py               ← All AI endpoints
│   ├── services/
│   │   ├── publisher_service.py   ← Writes public.properties + property_photos (MAX_PHOTOS=40)
│   │   ├── live_sync_service.py   ← Reads public.properties + property_photos
│   │   ├── ai_client.py           ← gemini-2.0-flash, get_client(), PROMPT_VERSION
│   │   ├── ai_enricher.py         ← Auto-enrichment pipeline
│   │   ├── enrichment_queue.py    ← Rate-controlled enrichment serializer
│   │   ├── image_service.py       ← Download/reorder/delete local images
│   │   ├── watermark_filter.py    ← Detects branded watermarks
│   │   ├── setup_service.py       ← Validates credentials + schema accessibility
│   │   └── scrapers/
│   │       ├── apartments_scraper.py       ← proxy=get_proxy_url() (httpx 0.28)
│   │       ├── hotpads_scraper.py          ← proxy=get_proxy_url()
│   │       ├── craigslist_scraper.py       ← proxy=get_proxy_url()
│   │       ├── opendoor_scraper.py         ← proxy=get_proxy_url()
│   │       ├── invitation_homes_scraper.py ← proxy=get_proxy_url()
│   │       └── progress_residential_scraper.py ← proxy=get_proxy_url()
│   └── main.py             ← FastAPI entry point
├── frontend/
│   └── src/
│       ├── api/client.js       ← All API calls incl. redownloadImages()
│       ├── components/
│       │   ├── PropertyCard.jsx    ← Photo count chip with re-fetch button
│       │   ├── AiAssistant.jsx     ← 9-tab AI panel
│       │   └── PublishButton.jsx   ← Publish gate with pre-publish checks
│       └── pages/
│           ├── Library.jsx     ← Property grid
│           ├── Editor.jsx      ← Full property editor
│           └── Audit.jsx       ← Quality dashboard
├── start.sh                ← Unified startup script
└── supabase_migration.sql  ← LEGACY — do not re-run, tables already exist
```

---

## Key API Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/scrape` | Scrape listings (source, location, filters) |
| GET | `/api/properties` | List all pipeline properties |
| PUT | `/api/properties/{id}` | Update a property |
| POST | `/api/properties/{id}/redownload-images` | Clear + re-fetch images from source URLs |
| POST | `/api/publish/{id}` | Publish to Choice website |
| POST | `/api/publish/{id}/refresh-images` | Re-upload photos to ImageKit |
| POST | `/api/sync/from-live` | Pull updates from live public.properties |
| POST | `/api/img-batch/start` | Bulk download images for all properties |
| POST | `/api/setup/status` | Check credentials + schema health |

---

## Running the App

| Environment | Command |
|---|---|
| Replit | Click Run |
| Terminal | `bash start.sh` |

---

## Environment & Credentials

| Variable | Required | Purpose |
|---|---|---|
| `SUPABASE_URL` | ✅ | `https://tlfmwetmhthpyrytrcfo.supabase.co` |
| `SUPABASE_SERVICE_ROLE_KEY` | ✅ | Full DB access (pipeline + public schemas) |
| `SUPABASE_MANAGEMENT_API_TOKEN` | ✅ | Supabase Management API (PostgREST config) |
| `IMAGEKIT_PUBLIC_KEY` | ✅ | ImageKit upload auth |
| `IMAGEKIT_PRIVATE_KEY` | ✅ | ImageKit server-side upload |
| `IMAGEKIT_URL_ENDPOINT` | ✅ | ImageKit CDN base URL |
| `GEMINI_API_KEY` | ⚡ Primary AI | gemini-2.0-flash |
| `DEEPSEEK_API_KEY` | ⚡ Fallback AI | DeepSeek V3 |
| `OPENROUTER_API_KEY` | ⚡ Fallback AI | Claude via OpenRouter |
| `GITHUB_TOKEN` | ✅ | GitHub API for cross-repo updates |
| `CHOICE_LANDLORD_ID` | Optional | Auto-resolved from landlords table if unset |

All credentials are in Replit Secrets. Never commit `backend/.env`.

---

## Cross-Project Rules (for AI working on this repo)

- ✅ Read/write `pipeline` schema tables freely
- ✅ Write to `public.properties` and `public.property_photos` via the publisher only
- ❌ Never write to any other `public` schema table
- ❌ Never reference `photo_urls` or `photo_file_ids` columns — they do not exist
- ❌ Never run ad-hoc SQL — add migrations to `choice121/Choice/supabase/migrations/`
- ❌ Never alter `public.properties` column structure without checking `publisher_service.py`
- ❌ Never use `proxies=` with httpx — use `proxy=get_proxy_url()` (httpx 0.28 breaking change)
- ❌ Never use `gemini-1.5-pro` — deprecated, use `gemini-2.0-flash`

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
- FastAPI + Uvicorn, supabase-py ≥2.4, HomeHarvest, Pillow, httpx 0.28, openai-compatible SDK

### Frontend (Node)
- React 18, React Router v6, Vite 5, Tailwind CSS v4, TanStack Query, Axios

---

## GitHub

- Pipeline repo: `https://github.com/choice121/property-pipeline`
- Choice website repo: `https://github.com/choice121/Choice`
- Git CLI push is blocked in Replit main agent — use GitHub REST API (see `AI_HANDOFF.md`)
