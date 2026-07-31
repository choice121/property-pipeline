# Progress Log

Single source of truth for all work done on this project.
Every AI that works here **must** add an entry before finishing.

---

## Current Status

**All features complete and operational.**
**Last Updated:** 2026-07-30
**Last Worked On By:** Replit Agent

---

## Completed Work

### [2026-07-30] — Cleanup: Remove unnecessary files, update documentation

**What was done:**
- Deleted all one-time SQL migration/backfill scripts (already applied to Supabase)
- Deleted Docker files (Dockerfile, docker-compose.yml, .dockerignore) — not used on Replit
- Deleted root main.py stub, pyproject.toml, uv.lock (unused uv/pip artifacts)
- Deleted Makefile (docker-based, irrelevant on Replit)
- Deleted all stage planning docs (STAGES.md, stages/) — all 7 stages complete
- Deleted SETUP_SUPABASE.md, PIPELINE_PROGRESS.md, docs/ — superseded/one-time
- Deleted attached_assets/ — old development session screenshots and PDFs
- Deleted choice-website/ — separate project, belongs in its own repo
- Deleted empty backend junk (=8.0.0, properties.db, data/, storage/)
- Rewrote README.md, AI_HANDOFF.md, PROGRESS.md, replit.md — clean and current

---

### [2026-07-30] — Feature: Hide published properties from library

**What was done:**
- Added `exclude_published` param to `backend/database/repository.py` `list()` — filters `choice_property_id IS NULL`
- Exposed `exclude_published: bool` query param on `GET /api/properties` in `backend/routers/properties.py`
- Updated Library.jsx to always pass `exclude_published: true` — published properties disappear from library immediately on next refresh
- Removed "Published" option from Library status filter dropdown (no longer relevant)
- Library count dropped from 412 → 316, confirming 96 published properties removed from view

---

### [2026-07-30] — AI Enrichment: Triggered bulk run

**What was done:**
- Called `POST /api/ai/bulk-enrich` — 15 properties queued (rest already had descriptions + score ≥ 60)
- Enrichment runs in background via DeepSeek/Gemini

---

### [2026-07-30] — Fix: Published property URLs returning "Not Found"

**What was done:**
- Root cause: `publisher_service.py` generated IDs as `PROP-XXXXXXXX` (uppercase), but the Choice website queries Supabase as `prop-xxxxxxxx` (lowercase). PostgreSQL text equality is case-sensitive → 404.
- Fixed `publisher_service.py`: changed `"PROP-" + uuid.uuid4().hex[:8].upper()` → `"prop-" + uuid.uuid4().hex[:8]`
- Migrated all 144 existing uppercase records in `public.properties` to lowercase — 0 errors

---

### [2026-04-11] — Bulk Publish: 50 properties live

**What was done:**
- Discovered HomeHarvest returns `list_price_min/max` for apartment complexes where `list_price` is NULL
- Updated `scraper_service.py` to fall back to `list_price_min` when `list_price` is null
- Scraped 200 properties each from Austin, Nashville, Denver, Atlanta, Phoenix, Charlotte (1,000+ total)
- Published 50 properties in one automated run — 0 failures
- Supabase now has 58+ active listings across 6 cities

---

### [2026-04-11] — Stages 1–7 Complete

All 7 stages implemented and verified:
- Stage 1: FastAPI + React/Vite project skeleton
- Stage 2: HomeHarvest scraping engine (all sources)
- Stage 3: Image downloading and local storage
- Stage 4: React app shell with routing
- Stage 5: Property Library UI (grid, search, filter, sort)
- Stage 6: Property Editor UI (full form, image management)
- Stage 7: Publisher (ImageKit upload + Supabase insert)

---

## Known Issues / Open Items

- `pets_allowed` and `smoking_allowed` are force-set to `True` in `publisher_service.py` regardless of scraped/edited values — needs fixing
- `neighborhood` field is scraped and published but not editable in the Editor UI

---

## How to Add an Entry

```
### [DATE] — Description

**What was done:**
- Specific changes made

**Issues encountered:**
- Problems found and how they were resolved

**Next step:**
- What the next AI should do (if anything)
```
