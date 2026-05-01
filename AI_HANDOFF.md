# AI Handoff Guide — Property Pipeline

Read this file completely before touching any code. It is mandatory.

---

## ECOSYSTEM CONTEXT — Read Before Anything Else

This project is half of a two-project ecosystem sharing one Supabase database.

| Project | Repo | Role |
|---|---|---|
| **This project** | [choice121/property-pipeline](https://github.com/choice121/property-pipeline) | Internal scraping + publishing tool |
| **Choice Website** | [choice121/Choice](https://github.com/choice121/Choice) | Public rental listing website |

**Supabase project ID** (shared by both): `tlfmwetmhthpyrytrcfo`

**How they relate**: This pipeline scrapes properties, stages them in the `pipeline` database schema, then publishes approved ones to the `public` schema — where the Choice website reads them.

Full cross-project rules and architecture: `ECOSYSTEM.md` in this repo.

---

## Current System State (as of May 2026)

**Everything is working end-to-end.** The pipeline is fully operational.

- ✅ Supabase pipeline schema exposed (done via Management API — no dashboard action needed)
- ✅ 1,000+ properties in `pipeline.pipeline_properties`
- ✅ Publisher writes to `public.properties` + `public.property_photos`
- ✅ AI enrichment working (gemini-2.0-flash)
- ✅ Image download, watermark scan, bulk publish all working
- ✅ Live sync (pipeline ← public.properties) working
- ✅ All scrapers working (apartments, hotpads, craigslist, opendoor, invitation_homes, progress_residential, realtor, zillow, redfin)

---

## Critical: Supabase Schema Architecture

```
pipeline schema (this project)       public schema (Choice website)
──────────────────────────────        ──────────────────────────────
pipeline.pipeline_properties  ──→    public.properties
pipeline.pipeline_enrichment_log     public.property_photos
pipeline.pipeline_scrape_runs        public.landlords
pipeline.pipeline_chat_conversations public.applications, leases …
```

**Why the pipeline schema?** Choice website migration `20260426000002_pipeline_private_schema.sql` moved pipeline tables from `public` to a private `pipeline` schema for security. The pipeline backend accesses them via `client.schema("pipeline")`.

**Code rule**: Use `get_pipeline_schema()` (not `get_supabase()`) for ALL pipeline_ table access. See `backend/database/supabase_client.py`.

**Supabase schema exposure**: Already configured. The `pipeline` schema is exposed in PostgREST via the Supabase Management API. If you ever need to re-do this, use:
```python
# PATCH https://api.supabase.com/v1/projects/tlfmwetmhthpyrytrcfo/config/database/postgrest
# Body: {"db_schema": "public,graphql_public,pipeline"}
# Auth: Bearer <SUPABASE_MANAGEMENT_API_TOKEN from Replit Secrets>
```

---

## CRITICAL: property_photos Table (Not Columns on properties)

Choice website migration `20260426000002` **removed** `photo_urls` and `photo_file_ids` from `public.properties`. Photos now live exclusively in `public.property_photos`.

### property_photos table schema:
```sql
id               uuid (auto)
property_id      text  -- matches public.properties.id (e.g. "PROP-BF860F35")
url              text  -- ImageKit CDN URL
file_id          text  -- ImageKit file ID (for deletion/refresh)
display_order    int   -- 0-indexed, controls gallery order
alt_text         text
caption          text
watermark_status text
width            int
height           int
created_at       timestamptz
updated_at       timestamptz
```

### NEVER do this (columns removed):
```python
record["photo_urls"] = ...       # WRONG — column does not exist
record["photo_file_ids"] = ...   # WRONG — column does not exist
```

### ALWAYS do this instead:
```python
# Read photos:
client.table("property_photos").select("*").eq("property_id", choice_id).execute()

# Write photos after publish:
client.table("property_photos").insert([
    {"property_id": choice_id, "url": r["url"], "file_id": r["file_id"],
     "display_order": i, "alt_text": ""}
    for i, r in enumerate(imagekit_results)
]).execute()
```

---

## Photo Limit

`backend/services/publisher_service.py` caps uploads at **40 photos** per property:
```python
MAX_PHOTOS = 40  # line ~118
```

The download pipeline (`image_service.download_images`) has no limit — it downloads all source URLs. The cap is only applied when uploading to ImageKit at publish time.

---

## Re-Download Images Endpoint

A per-property image re-download endpoint exists at:
```
POST /api/properties/{id}/redownload-images
```

This endpoint:
1. Wipes the local image cache for the property (deletes files from disk)
2. Clears `local_image_paths` in the database
3. Queues a background re-download from `original_image_urls`
4. Returns immediately: `{"ok": true, "queued": N}`

The frontend `PropertyCard.jsx` shows a photo count chip on each card (e.g. `31/47`) that triggers this endpoint when clicked.

---

## AI Client

**File**: `backend/services/ai_client.py`

**Active model**: `gemini-2.0-flash` (updated from deprecated `gemini-1.5-pro`)

**Priority order**: OpenRouter (Claude) → Gemini → DeepSeek. The first available key wins.

```python
_GEMINI_MODEL = "gemini-2.0-flash"   # NOT gemini-1.5-pro (deprecated/removed)
```

**NEVER use `gemini-1.5-pro`** — it was removed from the Google API and returns 404.

---

## httpx Proxy Parameter

All scrapers use httpx 0.28.x. The proxy parameter changed in 0.28:

```python
# WRONG (httpx < 0.28 — causes TypeError):
with httpx.Client(proxies=get_proxy_map(), ...) as client:

# CORRECT (httpx 0.28+):
with httpx.Client(proxy=get_proxy_url(), ...) as client:
```

All 6 custom scrapers (apartments, craigslist, hotpads, opendoor, invitation_homes, progress_residential) already use `proxy=get_proxy_url()`. Do not revert to `proxies=`.

---

## Phase Completion Log

### Phase 1 — Reliability Fixes ✅
- Shared AI client, retry logic, JSON mode, PROMPT_VERSION

### Phase 2 — Bulk Operation Rate Control ✅
- 750ms delay, 429 retry, token-aware batching, checkpoint/resume

### Phase 3 — Smarter Auto-Enrichment ✅
- LLM feature extraction, enrichment queue, fingerprint-based triggers

### Phase 4 — New Intelligence Features ✅
- Streaming SSE for rewrite/chat, neighborhood context, duplicate detection

### Phase 5 — UX and Tracking Improvements ✅
- Publish readiness bar, AI feedback buttons, description history

### Phase 6 — Cross-Project Integration & Schema Fix ✅
- `pipeline` schema exposed via Management API
- `supabase_client.py`: `get_pipeline_schema()` added
- `repository.py`: all pipeline_ tables via `self._pipeline`
- `setup_service.py`: verifies both schemas
- Cross-project docs: `ECOSYSTEM.md`, `SETUP_SUPABASE.md`, `AI_HANDOFF.md`, `replit.md`
- Choice repo: `copilot-instructions.md`, `CODEOWNERS`, `ECOSYSTEM.md` updated

### Phase 7 — Image System Overhaul + Scraper Fixes ✅
- `live_sync_service.py`: removed dead `photo_urls`/`photo_file_ids` refs, reads from `property_photos`
- `publisher_service.py`: publish + refresh_images write to `property_photos`; `MAX_PHOTOS` raised to 40
- `live_images.py`: fully rewritten to use `property_photos` table
- All 6 scrapers: fixed `proxies=` → `proxy=` (httpx 0.28 compatibility)
- `ai_client.py`: updated model to `gemini-2.0-flash` (was deprecated `gemini-1.5-pro`)
- New endpoint: `POST /api/properties/{id}/redownload-images`
- `PropertyCard.jsx`: photo count chip with one-click re-fetch

### Phase 8 — Poster Attribution + Scrape Run Schema Fix ✅
- Supabase migration: added 7 columns to `pipeline.pipeline_properties` — `agent_name`, `broker_name`, `neighborhood`, `tax_value`, `hoa_fee`, `agent_image_url`, `poster_landlord_id`
- `backend/services/poster_service.py`: resolves/creates landlord profiles by normalised name dedup, uploads avatar to ImageKit, in-process cache
- `backend/services/scraper_service.py`: extracts `agent_image_url` in `normalize_row()`
- `backend/routers/scraper.py`: calls `poster_service.resolve_poster_landlord()` after enrichment
- `backend/services/publisher_service.py`: prefers `prop.poster_landlord_id` over global fallback landlord
- `backend/routers/posters.py`: GET /posters, GET /posters/{id}, POST /posters/recalculate, DELETE /posters/cache
- `frontend/src/pages/Posters.jsx`: Poster Attribution page with profile list + property detail drawer
- Nav/routing: Posters tab added to desktop nav and mobile bottom bar
- Bug fix: `avatar_url` stored as JSON string cleaned up in DB; `_safe_avatar()` helper in posters router makes it resilient going forward
- Schema fix: added all 7 missing columns to `pipeline_scrape_runs` (`count_duplicate`, `count_watermarked`, `count_validation_rejected`, `count_image_failed`, `meta_json`, `idempotency_key`, `partial`) — scrape run logging now works fully
- Migrations pushed to `choice121/Choice`: `20260502000001_add_count_duplicate_to_scrape_runs.sql`, `20260502000002_complete_scrape_runs_columns.sql`

---

## Next Action for Incoming AI

All phases 1–8 are complete. The system is fully operational.

**Start by checking for any open issues:**
1. Check logs for errors on startup
2. Run a test scrape to confirm scrapers are healthy
3. Test AI enrichment on a property

---

## Architecture Decisions

### get_pipeline_schema() vs get_supabase()
- `get_supabase()` → public schema → use for: publisher (properties, property_photos), live_sync, landlords
- `get_pipeline_schema()` → pipeline schema → use for: ALL pipeline_ tables in repository.py
- Never mix these up. Using `get_supabase().table("pipeline_properties")` fails silently or with schema-cache error.

### Shared AI Client
Single source of truth for all AI config in `backend/services/ai_client.py`. Both `routers/ai.py` and `services/ai_enricher.py` import from here. Never duplicate model config.

### JSON Mode
Structured endpoints use `json_mode=True`. Plain-text endpoints (rewrite-description, chat, generate-title) do not.

### Publisher Flow
`publisher_service.py` → upsert `public.properties` → upload photos to ImageKit → insert rows into `public.property_photos`. Never writes to pipeline_ tables. Photos are capped at 40.

### Landlord ID Resolution
`_get_landlord_id()` in `publisher_service.py` is cached in `_cached_landlord_id`. It checks `CHOICE_LANDLORD_ID` env var first, then queries `public.landlords` and caches the result for the session. No action needed.

---

## Project Structure (Key Files)

```
ECOSYSTEM.md                      ← Cross-project bible
SETUP_SUPABASE.md                 ← Schema exposure guide (already done)
AI_HANDOFF.md                     ← This file
backend/
  database/
    supabase_client.py            ← get_supabase() [public] + get_pipeline_schema() [pipeline]
    repository.py                 ← All CRUD; _pipeline for pipeline_ tables, _client for public
  services/
    ai_client.py                  ← AI config (gemini-2.0-flash), get_client(), call_deepseek()
    ai_enricher.py                ← Auto-enrichment on scrape
    enrichment_queue.py           ← Rate-controlled enrichment serializer
    publisher_service.py          ← Publish → public.properties + property_photos (MAX_PHOTOS=40)
    live_sync_service.py          ← Sync live → pipeline (reads property_photos, not dead columns)
    image_service.py              ← Download, reorder, delete local images
    setup_service.py              ← Validates credentials + schema accessibility
    watermark_filter.py           ← Detects branded watermarks in photos
    scrapers/
      apartments_scraper.py       ← proxy=get_proxy_url() ← IMPORTANT
      hotpads_scraper.py          ← proxy=get_proxy_url()
      craigslist_scraper.py       ← proxy=get_proxy_url()
      opendoor_scraper.py         ← proxy=get_proxy_url()
      invitation_homes_scraper.py ← proxy=get_proxy_url()
      progress_residential_scraper.py ← proxy=get_proxy_url()
  routers/
    ai.py                         ← All AI endpoints
    properties.py                 ← CRUD endpoints for pipeline properties
    publisher.py                  ← Publish, refresh-images, sync-fields, set-listing-status
    scraper.py                    ← Scrape + POST /properties/{id}/redownload-images
    live_images.py                ← Read/write property_photos (NOT dead photo_urls column)
    images.py                     ← Local image management, watermark scan
    sync.py                       ← Live sync endpoint
frontend/
  src/
    api/client.js                 ← All API calls including redownloadImages()
    components/
      PropertyCard.jsx            ← Photo count chip with re-fetch button
      AiAssistant.jsx             ← 9-tab AI panel
      PublishButton.jsx           ← Publish gate
    pages/
      Library.jsx                 ← Property grid
      Editor.jsx                  ← Full property editor
      Audit.jsx                   ← Quality dashboard
```

---

## Non-Negotiable Rules

### Schema boundaries
- pipeline_ tables → always `self._pipeline` in repository.py
- public tables → always `self._client` or `get_supabase()`
- Never write to public schema tables OTHER than properties + property_photos

### Photos
- NO `photo_urls` or `photo_file_ids` anywhere — those columns were removed
- Always use `public.property_photos` table for reading and writing photo data

### No hardcoded credentials
All credentials are in Replit Secrets. Never commit backend/.env.

### Preserve original data
`original_data` written once on scrape, never changed. `edited_fields` tracks changes.

### No ad-hoc SQL
New tables/columns → add a migration to `choice121/Choice/supabase/migrations/`

### Update this file
After completing any work, add the phase to the Phase Completion Log above and update Current System State.

### Cross-repo changes
When making changes that affect the Choice website's database structure, also update `choice121/Choice`. Use the GitHub API with the `GITHUB_TOKEN` from Replit Secrets.

---

## What This Project Is

A private property management tool for the owner of Choice Properties.

1. Scrape listings from Zillow, Realtor.com, Redfin, HotPads, Craigslist, Apartments.com, Opendoor, Invitation Homes, Progress Residential
2. View and edit in a private dashboard
3. AI-enrich (titles, descriptions, features, quality scores)
4. Publish approved listings to the live Choice Properties website (up to 40 photos per listing)

Nothing touches the live website until the owner explicitly publishes a listing.

---

## Choice Website — What AI Working Here Needs to Know

The Choice website (`choice121/Choice`) is a **static HTML/CSS/JS site** deployed on **Cloudflare Pages**.

- **No Node.js server, no Python, no Express** — everything runs in the browser + Supabase
- **Backend logic**: Supabase Edge Functions (Deno/TypeScript) in `supabase/functions/`
- **Database migrations**: `supabase/migrations/` — all changes go here
- **Deployment**: Push to `main` → GitHub CI validates → Cloudflare Pages auto-deploys
- **Replit role in Choice**: editing only — Replit is NOT the host

### Choice website tables this pipeline touches (public schema):
- `public.properties` — publisher writes here when a listing is approved
- `public.property_photos` — publisher writes ImageKit URLs here (NOT photo_urls/photo_file_ids — those columns are gone)

### Choice website tables this pipeline NEVER touches:
- `public.applications`, `public.leases`, `public.landlords` (read-only for landlord lookup), `public.sign_events` — all belong to the Choice website's lease/application workflow

---

## Credentials & Environment

| Variable | Purpose |
|---|---|
| SUPABASE_URL | `https://tlfmwetmhthpyrytrcfo.supabase.co` |
| SUPABASE_SERVICE_ROLE_KEY | Full DB access (pipeline + public schema) |
| SUPABASE_MANAGEMENT_API_TOKEN | Supabase Management API (schema exposure, PostgREST config) |
| GEMINI_API_KEY | Primary AI (gemini-2.0-flash) |
| DEEPSEEK_API_KEY | Fallback AI |
| OPENROUTER_API_KEY | Fallback AI (Claude) |
| IMAGEKIT_PUBLIC_KEY | ImageKit uploads |
| IMAGEKIT_PRIVATE_KEY | ImageKit uploads (server-side) |
| IMAGEKIT_URL_ENDPOINT | ImageKit CDN base URL |
| GITHUB_TOKEN | GitHub API for cross-repo updates |
| CHOICE_LANDLORD_ID | Optional — auto-resolved from public.landlords if unset |

DO NOT ask the owner for credentials. They are all in Replit Secrets.

---

## GitHub Push Instructions

Git CLI push is blocked in the Replit main agent. Use the GitHub REST API:

```javascript
// Push a file via GitHub API (Node.js / code_execution tool):
const token = process.env.GITHUB_TOKEN;  // from Replit Secrets
const headers = { Authorization: `Bearer ${token}`, "Accept": "application/vnd.github+json", "Content-Type": "application/json" };

async function pushFile(repo, path, content, message) {
  const sha_resp = await fetch(`https://api.github.com/repos/choice121/${repo}/contents/${encodeURIComponent(path)}`, { headers });
  const sha = sha_resp.ok ? (await sha_resp.json()).sha : null;
  const body = { message, content: Buffer.from(content).toString('base64') };
  if (sha) body.sha = sha;
  const resp = await fetch(`https://api.github.com/repos/choice121/${repo}/contents/${encodeURIComponent(path)}`, {
    method: "PUT", headers, body: JSON.stringify(body)
  });
  return resp.ok;
}
```

Repos available: `property-pipeline`, `Choice`
