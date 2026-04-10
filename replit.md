# Property Pipeline

A private property management tool for Choice Properties. Scrape listings from Zillow, Realtor.com, and Redfin, manage them in a dashboard, and publish approved listings to the live website.

## Architecture

- **Backend**: Python/FastAPI on port 8000 (localhost only)
- **Frontend**: React + Vite on port 5000 (0.0.0.0, proxied)
- **Database**: SQLite at `backend/data/pipeline.db`
- **Image storage**: `backend/storage/images/{property_id}/`

## Running

Both services start with `bash start.sh` (the configured workflow):
- Backend: `python3 backend/main.py` → localhost:8000
- Frontend: Vite from workspace root → 0.0.0.0:5000

## Key Files

- `start.sh` — starts both backend and frontend
- `vite.config.js` — root-level Vite config (frontend root: ./frontend), proxies /api to localhost:8000
- `backend/main.py` — FastAPI entry point
- `backend/database/models.py` — SQLite Property schema
- `frontend/src/pages/` — Library, Scraper, Editor pages
- `frontend/src/components/` — Layout, PropertyCard, StatusBadge, ImageGallery

## Tech Notes

- **Tailwind v4** is installed — uses `@import "tailwindcss"` in CSS, and `@tailwindcss/postcss` plugin
- **React 19 + Vite 8** — latest versions
- **Python packages** installed via uv into `.pythonlibs/`
- **Node packages** installed at workspace root `node_modules/`

## Stages

All stages 1–6 are complete. Stage 7 (Publisher to Supabase/ImageKit) is locked pending owner credentials.

## API

- `GET /api/health` — health check
- `POST /api/scrape` — trigger HomeHarvest scrape
- `GET/PUT/DELETE /api/properties` — manage properties
- `GET /api/images/{id}/{filename}` — serve images
- `DELETE /api/properties/{id}/images/{index}` — delete image
- `PUT /api/properties/{id}/images/reorder` — reorder images
