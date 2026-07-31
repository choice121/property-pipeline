# Property Pipeline — Replit Project Notes

## Project Overview

Internal admin tool for Choice Properties. Scrapes rental listings from multiple sources, lets you review/edit them in a dashboard, then publishes approved listings to the live Choice Properties website.

**Stack:**
- Backend: Python 3.11 + FastAPI (port 8000)
- Frontend: React 18 + Vite + Tailwind CSS (port 5000)
- Database: Supabase (PostgreSQL) — `pipeline` schema for staging, `public` schema for live listings
- Image CDN: ImageKit
- AI: Gemini 2.0 Flash (primary) + DeepSeek (fallback)
- Scraping: HomeHarvest library

**GitHub repo:** `choice121/property-pipeline`

---

## How to Start

```bash
bash start.sh
```

Opens at port 5000. Backend API at port 8000.

---

## Project Structure

```
backend/
  routers/        API endpoints (properties, scraper, publisher, ai, images, stats)
  services/       Business logic (scraper, publisher, AI enricher, image downloader)
  database/       Supabase client + repository pattern
  requirements.txt

frontend/
  src/
    pages/        Library, Editor, Scraper, Audit, Posters, Create
    components/   PropertyCard, PublishButton, ImageGallery, etc.
    api/          client.js — all API calls
  package.json
  vite.config.js  (frontend-level; root vite.config.js handles dev server + PWA)

vite.config.js    Root config — proxy /api → :8000, PWA, port 5000
start.sh          Startup script — checks credentials, starts both services
```

---

## Key Files

| File | Purpose |
|---|---|
| `backend/services/publisher_service.py` | Publishes a property to ImageKit + Supabase |
| `backend/services/scraper_service.py` | Normalizes HomeHarvest data into pipeline format |
| `backend/services/ai_service.py` | AI enrichment (descriptions, SEO, autofill) |
| `backend/database/repository.py` | All Supabase queries for pipeline schema |
| `backend/database/supabase_client.py` | Supabase client setup — use `get_pipeline_schema()` for pipeline tables |
| `frontend/src/pages/Library.jsx` | Property grid with bulk actions |
| `frontend/src/pages/Editor.jsx` | Full property edit form + publish button |
| `AI_HANDOFF.md` | Critical architecture notes for any AI working on this project |
| `ECOSYSTEM.md` | How this tool relates to the Choice website |

---

## Environment Variables

All stored as Replit env vars (shared environment). No `.env` file needed.

Required: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `DEEPSEEK_API_KEY`, `IMAGEKIT_PUBLIC_KEY`, `IMAGEKIT_PRIVATE_KEY`, `IMAGEKIT_URL_ENDPOINT`

Optional: `CHOICE_LANDLORD_ID`, `GEMINI_API_KEY`, `GEOAPIFY_API_KEY`, `GITHUB_TOKEN`

---

## User Preferences

- Push code changes to GitHub using the GitHub REST API (Git CLI is blocked in Replit main agent)
- Push files **sequentially**, not in parallel — parallel pushes cause SHA conflicts (409 errors)
- Library must always exclude published properties (`exclude_published=true`)
- Published property IDs must always be lowercase `prop-xxxxxxxx` — uppercase breaks live URLs
- Do not restructure the backend/frontend split or migrate to a different stack
- Always update `PROGRESS.md` after completing any work
