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
- `POST /ai/detect-issues` — scans for errors/warnings/suggestions; returns `{"issues":[...], "quality_score":N}`
- `POST /ai/suggest-field` — suggests a value for a single field
- `POST /ai/chat` — freeform assistant chat about the property
- `POST /ai/bulk-scan` — batch scans up to N listings, returns per-property issue counts
- `POST /ai/score` — detailed quality score (0–100) + grade (A–F) + written evaluation
- `POST /ai/pricing-intel` — market pricing analysis (very_low/low/fair/high/very_high)
- `POST /ai/seo-optimize` — SEO keyword analysis + title suggestion + optimized opening
- `POST /ai/clean` — Deep Clean Engine: strips contact info, tour language, screening requirements; rewrites in brand voice; saves to DB
- `POST /ai/bulk-clean` — Library-wide bulk clean: processes all properties sequentially, persists to DB
- `POST /ai/generate-title` — Generates a specific, compelling listing title; saves to DB
- `POST /ai/extract-features` — LLM amenity/appliance extraction from free text; merges with existing, saves to DB

### AI Auto-Enrichment (`backend/services/ai_enricher.py`)
Runs automatically on scrape and re-runs after significant property edits. Tasks: generate_description, extract_features, infer_pet_policy, classify_property_type, generate_title. Re-enrichment triggered on PUT /properties/:id when any SIGNIFICANT_FIELDS change (bedrooms, bathrooms, property_type, monthly_rent, amenities, appliances, description, city, state) for unpublished properties.

### Frontend AI Features
- **AiAssistant** (`frontend/src/components/AiAssistant.jsx`): 9 tabs — Auto-Fill, Rewrite (draft history), **Clean**, **Title**, Issues, Score, Pricing, SEO, Chat. Receives `propertyId` prop for server-side save-back.
- **Library bulk scan** (`frontend/src/pages/Library.jsx`): "AI Scan (N)" button scans all visible listings, shows summary banner + per-card color badges
- **Library bulk clean** (`frontend/src/pages/Library.jsx`): "Clean All" button runs bulk-clean on all properties with descriptions
- **PropertyCard badges** (`frontend/src/components/PropertyCard.jsx`): AI health badge (red=errors, amber=warnings, green=clean) shown after a bulk scan
- **Publish gate** (`frontend/src/components/PublishButton.jsx`): Auto-checks for issues before publishing; blocks on errors, warns on warnings with override
- **Editor auto-detect** (`frontend/src/pages/Editor.jsx`): After every save, runs detect-issues in background and shows inline quality badge with error/warning count + quality score
- **Audit Dashboard** (`frontend/src/pages/Audit.jsx`): Library-wide table at `/audit` — completeness bars, issue counts post-scan, last-updated, staleness, sortable/filterable, Clean All + Scan All buttons

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

### Any environment — single command

| Environment | Command |
|---|---|
| Replit | Click the Run button (triggers `bash start.sh`) |
| Terminal / any AI builder | `make` or `bash start.sh` |
| Docker / any machine | `docker-compose up --build` |

### What `start.sh` does (in order)
1. Sources `backend/.env` at the OS shell level — all vars are exported before any process starts
2. Runs a startup validator that prints a clear status table for every required and optional credential
3. Verifies Python dependencies are available in the Replit environment
4. Verifies root Node dependencies are installed
5. Starts FastAPI (Uvicorn) on `127.0.0.1:8000` in the background
6. Starts Vite on `0.0.0.0:5000` from the root dependency install (proxies `/api` → backend)

### Useful make commands
```
make          # start everything
make setup    # install deps only, don't start
make check    # validate all credentials without starting
make stop     # kill running services
make docker-up   # run via Docker Compose
```

## Environment & Credentials

Credentials should be provided through Replit environment variables/secrets. `backend/.env` is only a local-development fallback and is ignored by git.

**Required (app will not start without these):**
- `SUPABASE_URL` — Supabase project URL
- `SUPABASE_SERVICE_ROLE_KEY` — Supabase service-role JWT

**Required for publishing (ImageKit):**
- `IMAGEKIT_PUBLIC_KEY`
- `IMAGEKIT_PRIVATE_KEY`
- `IMAGEKIT_URL_ENDPOINT`

**Optional (features degrade gracefully if absent):**
- `SUPABASE_ANON_KEY` — used by public website tooling
- `DEEPSEEK_API_KEY` — enables all AI features
- `CHOICE_LANDLORD_ID` — auto-resolved from Supabase if not set

See `backend/.env.example` for a clean template.

## GitHub Actions CI

Every push to `main`/`master` automatically:
1. Installs all Python and Node dependencies
2. Validates all required credentials from the runtime environment
3. Builds the frontend
4. Runs a backend smoke test against the live Supabase connection

If credentials are broken or missing, the CI fails immediately and shows exactly which variable is the problem.

## Replit-Specific Notes

- The frontend is configured for Replit preview compatibility with `host: '0.0.0.0'`, port `5000`, `strictPort: true`, and `allowedHosts: true`.
- Startup uses Replit-managed Python and Node dependencies directly instead of creating a virtual environment.
- Frontend API calls stay same-origin (`/api`) and are proxied by Vite to the internal FastAPI backend at `127.0.0.1:8000`.
- Vite ignores Replit internal state folders (`.local`, `.cache`) so workflow log updates do not trigger browser reload loops.
- The backend uses `BACKEND_PORT` instead of `PORT` so Replit's frontend port does not accidentally move the API server.
- Background live-site sync is skipped when setup is missing or invalid, preventing repeated startup errors.

## Mobile-First Architecture (added April 2026)

The frontend is built phone-first. Property managers are expected to use this on a phone in the field.

**Installable PWA**
- `vite-plugin-pwa` generates a service worker that caches the app shell, ImageKit images (CacheFirst, 30-day expiry), and recently-fetched listings (NetworkFirst with 4s timeout).
- Manifest at `frontend/public/manifest.webmanifest`; "Add to Home Screen" works on iOS and Android.
- Auto-updates via `registerType: 'autoUpdate'`.

**Touch-first interactions**
- `frontend/src/components/BottomSheet.jsx` — swipe-down-to-dismiss bottom sheet (hosts the AI Assistant on mobile via a floating action button in the Editor).
- `frontend/src/components/PullToRefresh.jsx` — wraps the Library list; refetches the properties query on pull.
- `frontend/src/components/SwipeableCard.jsx` — reusable swipe-to-action drawer for cards.
- `frontend/src/utils/longPress.js` — long-press hook used by the Library to enter multi-select mode.
- `frontend/src/utils/haptics.js` — small haptic feedback wrappers (Vibration API).

**Responsive imagery (ImageKit)**
- `frontend/src/utils/imageUrl.js` exports `transformImage()` and `responsiveImage()` which add `tr=w-…,q-…,f-auto,pr-true` parameters when the source is an ImageKit URL.
- `PropertyCard`, `LiveImageGallery`, and `ImageGallery` request appropriate sizes via `srcSet`/`sizes` plus `loading="lazy"` and `decoding="async"`.
- The Vite config exposes `VITE_IMAGEKIT_URL_ENDPOINT` from the `IMAGEKIT_URL_ENDPOINT` secret so the frontend can detect ImageKit assets.

**Per-page mobile layouts**
- `Layout.jsx` — top header on every screen, plus a fixed bottom tab bar on mobile (`Library / Scrape / Create / Audit`) with safe-area padding.
- `Editor.jsx` — sticky bottom save bar on mobile + AI floating action button that opens the AI Assistant in a bottom sheet. Records every visit to `recentlyViewed` localStorage on load.
- `Audit.jsx` — uses the table on `md+` screens and a card list on smaller screens, color-coded by issue severity.
- `Library.jsx` — `SkeletonCard` placeholders during load, pull-to-refresh, long-press to enter bulk-select mode, and a horizontal-scroll "Recently viewed" strip (`components/RecentlyViewedStrip.jsx`) of properties opened in the last 24 hours, persisted via `utils/recentlyViewed.js`.

**TanStack Query defaults**
- `staleTime: 30s`, `gcTime: 5m`, `networkMode: 'offlineFirst'`, `refetchOnWindowFocus: false`, set in `main.jsx` so navigating between tabs feels instant and the app stays usable on flaky mobile networks.

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
