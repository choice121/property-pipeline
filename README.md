# Property Pipeline

An internal admin tool for Choice Properties. Scrapes rental listings, lets you review and edit them, then publishes approved listings to the Choice Properties website.

---

## What It Does

1. **Scrape** — Pull listings from Zillow, Redfin, Realtor.com, Apartments.com, HotPads, Craigslist, and more
2. **Review** — Browse all scraped properties in the Library with photos, quality scores, and status
3. **Edit** — Open any property and edit every field before publishing
4. **Publish** — Upload photos to ImageKit and push the listing to the live Choice Properties website

Nothing touches the live site until you click Publish.

---

## How to Run

Dependencies install automatically. Just start the app:

```bash
bash start.sh
```

- **Frontend** — React dashboard at `http://localhost:5000`
- **Backend** — FastAPI at `http://localhost:8000`

---

## Required Secrets

All credentials are stored as Replit environment variables. Do not add a `.env` file.

| Variable | Purpose |
|---|---|
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Full DB access (pipeline + public schema) |
| `DEEPSEEK_API_KEY` | AI enrichment (descriptions, SEO) |
| `IMAGEKIT_PUBLIC_KEY` | Photo uploads |
| `IMAGEKIT_PRIVATE_KEY` | Photo uploads (server-side) |
| `IMAGEKIT_URL_ENDPOINT` | ImageKit CDN base URL |
| `GEMINI_API_KEY` | AI enrichment (primary model) |
| `GEOAPIFY_API_KEY` | Geocoding |
| `GITHUB_TOKEN` | GitHub API (for pushing code changes) |
| `CHOICE_LANDLORD_ID` | Optional — auto-resolved from Supabase if unset |

---

## Architecture

```
property-pipeline/
├── backend/              # FastAPI (Python 3.11) — port 8000
│   ├── routers/          # API endpoints
│   ├── services/         # Scraping, publishing, AI, images
│   ├── database/         # Supabase client + repository
│   └── requirements.txt
├── frontend/             # React + Vite — port 5000
│   └── src/
│       ├── pages/        # Library, Editor, Scraper, Audit, Posters
│       └── components/
├── vite.config.js        # Vite config (root — used for dev + build)
├── start.sh              # Startup script
└── replit.md             # Project notes and preferences
```

---

## Ecosystem

This tool shares a Supabase database with the [Choice website](https://github.com/choice121/Choice).

| Schema | Owner |
|---|---|
| `pipeline.*` | This tool (scraping, staging) |
| `public.*` | Choice website (live listings) |

When you publish a property, this tool writes to `public.properties` and `public.property_photos` — which the Choice website reads immediately.

See `ECOSYSTEM.md` for full cross-project details.
