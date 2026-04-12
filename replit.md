# Property Pipeline

A private, standalone property management tool for Choice Properties.

## Overview

This app scrapes property listings from major platforms (Zillow, Realtor.com, Redfin), allows viewing and editing those listings in a private dashboard, and eventually publishes them to a live website.

## Architecture

- **Backend**: Python FastAPI running on port 8000
- **Frontend**: React 18 + Vite running on port 5000 (proxies /api to backend)
- **Database**: SQLite stored at `backend/data/pipeline.db`
- **Image storage**: Local at `backend/storage/images/`

## Project Structure

```
property-pipeline/
├── backend/
│   ├── data/               # SQLite database (pipeline.db)
│   ├── database/           # SQLAlchemy models and DB config (db.py, models.py)
│   ├── routers/            # API endpoints (health, scraper, properties, images, publisher)
│   ├── services/           # Business logic (scraping, image handling)
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

## Development Status

Stages 1-6 complete. Stage 7 (Publisher to Supabase/ImageKit) requires external credentials to be set in `.env`.
