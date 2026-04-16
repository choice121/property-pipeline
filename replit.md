# Property Pipeline

A private, standalone property management tool for Choice Properties.

## Overview

This app scrapes property listings from major platforms (Zillow, Realtor.com, Redfin), allows viewing and editing those listings in a private dashboard, and publishes them to the live Choice Properties website.

**Live Website:** https://choice-properties-site.pages.dev/
**Property page format:** https://choice-properties-site.pages.dev/property.html?id={PROP-ID}

## Architecture

- **Backend**: Python FastAPI running on port 8000
- **Frontend**: React 18 + Vite running on port 5000 (proxies /api to backend)
- **Pipeline Database**: Supabase (`pipeline_properties` and `pipeline_enrichment_log` tables) — data persists across any Replit account
- **Live Publishing**: Supabase (`properties` table) + ImageKit CDN for the Choice Properties website
- **Image storage**: Local at `backend/storage/images/` (temporary; images are re-downloadable from source URLs stored in Supabase)

## AI System (DeepSeek V3)

All AI features use the DeepSeek V3 model (`deepseek-chat`) via the OpenAI-compatible SDK (`base_url="https://api.deepseek.com"`).

### AI Endpoints (`backend/routers/ai.py`)
- `POST /ai/autofill` — suggests values for empty fields
- `POST /ai/rewrite-description` — generates polished listing descriptions
- `POST /ai/detect-issues` — scans for errors/warnings/suggestions
- `POST /ai/suggest-field` — suggests a value for a single field
- `POST /ai/chat` — freeform assistant chat about the property
- `POST /ai/bulk-scan` — batch scans up to N listings, returns per-property issue counts
- `POST /ai/score` — detailed quality score (0–100) + grade (A–F) + written evaluation
- `POST /ai/pricing-intel` — market pricing analysis (very_low/low/fair/high/very_high)
- `POST /ai/seo-optimize` — SEO keyword analysis + title suggestion + optimized opening

### AI Auto-Enrichment (`backend/services/ai_enricher.py`)
Runs automatically on scrape. When a listing has no description, tries DeepSeek LLM first (contextual, property-specific), falls back to template if DeepSeek fails.

### Frontend AI Features
- **AiAssistant** (`frontend/src/components/AiAssistant.jsx`): 7 tabs — Auto-Fill, Rewrite (with draft history), Issues, **Score**, **Pricing**, **SEO**, Chat
- **Library bulk scan** (`frontend/src/pages/Library.jsx`): "AI Scan (N)" button scans all visible listings, shows summary banner + per-card color badges
- **PropertyCard badges** (`frontend/src/components/PropertyCard.jsx`): AI health badge (red=errors, amber=warnings, green=clean) shown after a bulk scan
- **Publish gate** (`frontend/src/components/PublishButton.jsx`): Auto-checks for issues before publishing; blocks on errors, warns on warnings with override

## Project Structure

```
property-pipeline/
├── backend/
│   ├── database/           # Supabase client, repository pattern, model aliases
│   │   ├── supabase_client.py  # Lazy Supabase connection singleton
│   │   ├── repository.py       # PropertyRecord, AiEnrichmentLog, Repository class
│   │   ├── db.py               # get_db() dependency for FastAPI routers
│   │   └── models.py           # Re-exports PropertyRecord as Property for compatibility
│   ├── routers/            # API endpoints (health, scraper, properties, images, publisher)
│   ├── services/           # Business logic (scraping, image handling, watermark filtering, publishing)
│   ├── storage/images/     # Local property photo storage (temporary, re-downloadable)
│   └── main.py             # FastAPI entry point
├── supabase_migration.sql  # Run once in Supabase SQL Editor to create pipeline tables
├── frontend/
│   ├── src/
│   │   ├── api/            # Axios client and API definitions
│   │   ├── components/     # Reusable UI (PropertyCard, ImageGallery)
│   │   ├── pages/          # Views (Library, Scraper, Editor)
│   │   └── App.jsx         # Routing and main layout
│   ├── package.json        # Frontend dependencies (React 18, Vite 5, Tailwind v4)
│   └── vite.config.js      # Vite config with proxy to backend
├── start.sh                # Unified startup script
└── vite.config.js          # Root-level vite config (unused, frontend has its own)
```

## Running the App

The workflow runs `bash start.sh` which:
1. Starts the FastAPI backend using `.venv/bin/python main.py` on port 8000 in the background
2. Starts the Vite dev server from `frontend/` on port 5000, proxying `/api` calls to the backend

Python packages are installed in `.venv/` (created via `uv venv` + `uv pip install`). Frontend packages are in `frontend/node_modules/`.

## Replit Migration Notes

- The frontend is configured for Replit preview compatibility with `host: '0.0.0.0'`, port `5000`, `strictPort: true`, and `allowedHosts: true`.
- Frontend API calls stay same-origin (`/api`) and are proxied by Vite to the internal FastAPI backend at `127.0.0.1:8000`.
- Vite ignores Replit internal state folders (`.local`, `.cache`) so workflow log updates do not trigger browser reload loops.
- The backend uses `BACKEND_PORT` instead of `PORT` so Replit's frontend port does not accidentally move the API server onto port 5000.

## Key Dependencies

### Backend (Python)
- FastAPI + Uvicorn
- supabase-py (pipeline database — replaces SQLite/SQLAlchemy)
- HomeHarvest (property scraping)
- Pillow + httpx (image processing)
- python-dotenv

### Frontend (Node)
- React 18 + React Router v6
- Vite 5
- Tailwind CSS v4 + @tailwindcss/postcss
- TanStack Query (React Query)
- Axios

## Publishing and Filtering

- Stage 7 publishing sends approved listings to Supabase and ImageKit when the required environment variables are configured.
- Watermarked listings are blocked before display/save by `backend/services/watermark_filter.py`.
- Current blocked watermark brand terms are stored in `WATERMARKED_BRAND_TERMS`; add new brand text there to expand the denylist.
- The pipeline now preserves a richer property profile for publishing, including move-in costs, garage spaces, pet restrictions, lease terms, appliances, utilities, flooring, heating/cooling/laundry, basement/central-air flags, inferred features, and a completeness score.
- `backend/database/db.py` performs additive SQLite column migrations during startup so older local pipeline databases keep working as the property model expands.
- A local `choice-website/` copy of the Choice Properties static site has been added for the display-side update. It now includes website schema/display support for `total_bathrooms`, `has_basement`, and `has_central_air`, richer listing-card feature tags, richer property-detail structured data, and expanded search indexing for appliances/utilities/flooring/HVAC terms.
- The uploaded pipeline fix pass has been merged selectively while keeping the Replit import setup and current dependency ranges. Publishing now normalizes property types, checks Supabase for existing address/city/state duplicates before insert, preserves unknown pet status, strips known platform boilerplate from descriptions, caps ImageKit uploads at 25 photos, and supports refreshing photos or syncing edited fields for already-published properties.
- The scraper UI now includes a source selector and the backend stores the selected source on scraped/search results. The included backfill SQL files (`BACKFILL_PIPE1_property_types.sql`, `BACKFILL_PIPE2_remove_duplicates.sql`, `BACKFILL_PIPE4_landlord_id.sql`) are for manual Supabase cleanup of already-live records.

## Development Status

Stages 1-7 are implemented, with ongoing property data completeness and publishing reliability upgrades. Publishing requires Supabase, ImageKit, and landlord ID environment variables to be configured.
