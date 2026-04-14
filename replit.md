# Property Pipeline

A private, standalone property management tool for Choice Properties.

## Overview

This app scrapes property listings from major platforms (Zillow, Realtor.com, Redfin), allows viewing and editing those listings in a private dashboard, and eventually publishes them to a live website.

## Architecture

- **Backend**: Python FastAPI running on port 8000
- **Frontend**: React 18 + Vite running on port 5000 (proxies /api to backend)
- **Database**: SQLite stored at `backend/data/pipeline.db` for local staging; Supabase is used for live publishing
- **Image storage**: Local at `backend/storage/images/`; ImageKit is used for live publishing

## Project Structure

```
property-pipeline/
├── backend/
│   ├── data/               # SQLite database (pipeline.db)
│   ├── database/           # SQLAlchemy models and DB config (db.py, models.py)
│   ├── routers/            # API endpoints (health, scraper, properties, images, publisher)
│   ├── services/           # Business logic (scraping, image handling, watermark filtering, publishing)
│   ├── storage/images/     # Local property photo storage
│   └── main.py             # FastAPI entry point
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
1. Starts the FastAPI backend (`python3 main.py`) on port 8000 in the background using `BACKEND_PORT=8000`
2. Starts the Vite dev server from the repository root on port 5000, serving the `frontend/` app through the root Vite config

## Replit Migration Notes

- The frontend is configured for Replit preview compatibility with `host: '0.0.0.0'`, port `5000`, `strictPort: true`, and `allowedHosts: true`.
- Frontend API calls stay same-origin (`/api`) and are proxied by Vite to the internal FastAPI backend at `127.0.0.1:8000`.
- Vite ignores Replit internal state folders (`.local`, `.cache`) so workflow log updates do not trigger browser reload loops.
- The backend uses `BACKEND_PORT` instead of `PORT` so Replit's frontend port does not accidentally move the API server onto port 5000.

## Key Dependencies

### Backend (Python)
- FastAPI + Uvicorn
- SQLAlchemy (SQLite)
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
