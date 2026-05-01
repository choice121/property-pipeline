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

**One-time setup needed**: The `pipeline` schema must be exposed in Supabase dashboard settings. See `SETUP_SUPABASE.md`.

---

## Implementation Checklist

### Phase 1 — Reliability Fixes ✅ COMPLETE
- [x] 1A. `backend/services/ai_client.py` — shared PLATFORM_CONTEXT, call_deepseek(), retry logic with exponential backoff, JSON mode support, PROMPT_VERSION constant
- [x] 1B. `backend/routers/ai.py` — all structured endpoints use json_mode=True
- [x] 1C. `backend/services/ai_enricher.py` — LLM feature extraction replaces keyword regex

### Phase 2 — Bulk Operation Rate Control ✅ COMPLETE
- [x] 2A–2E: 750ms delay, 429 retry, token-aware batching, skip-recently-scanned, checkpoint/resume

### Phase 3 — Smarter Auto-Enrichment ✅ COMPLETE
- [x] 3A–3C: LLM feature extraction, enrichment queue, fingerprint-based re-enrichment triggers

### Phase 4 — New Intelligence Features ✅ COMPLETE
- [x] 4A: Streaming for rewrite-description and chat (SSE)
- [x] 4B: Neighborhood context paragraph generation
- [x] 4C: Duplicate detection via difflib fuzzy matching before publish

### Phase 5 — UX and Tracking Improvements ✅ COMPLETE
- [x] 5A: Publish readiness progress bar (completeness.js)
- [x] 5B: Accept/reject feedback buttons on AI suggestions
- [x] 5C: Prompt versioning (PROMPT_VERSION)
- [x] 5D: Description edit history with restore

### Phase 6 — Cross-Project Integration & Schema Fix ✅ COMPLETE
- [x] 6A: `supabase_client.py` — added `get_pipeline_schema()` using `client.schema("pipeline")`
- [x] 6B: `repository.py` — all pipeline_ table calls use `self._pipeline` (pipeline schema)
- [x] 6C: `setup_service.py` — checks pipeline schema; gives clear error with fix instructions
- [x] 6D: `ECOSYSTEM.md` — canonical cross-project architecture document
- [x] 6E: `SETUP_SUPABASE.md` — one-step setup guide for the pipeline schema exposure
- [x] `replit.md` — full ecosystem context for Replit AI
- [x] `choice121/Choice/.github/copilot-instructions.md` — updated with pipeline context
- [x] `choice121/Choice/.github/CODEOWNERS` — pipeline schema migrations protected
- [x] `choice121/Choice/ECOSYSTEM.md` — cross-project overview in Choice repo

---

## Next Action for Incoming AI

1. Read this file completely
2. Read `ECOSYSTEM.md` for cross-project context
3. Check the checklist above — find the first unchecked item
4. Read the relevant source files before editing
5. Update this file when done (mark [x], update Next Action)
6. Push to GitHub (see push instructions at bottom)

**All phases 1–6 are complete. The pipeline is fully operational with streaming AI, schema-correct Supabase access, and bidirectional cross-project documentation.**

The one remaining step is: expose the `pipeline` schema in Supabase dashboard settings (see `SETUP_SUPABASE.md`). This cannot be done via code — it's a one-time dashboard action.

---

## Key Architecture Decisions

### get_pipeline_schema() vs get_supabase()
- `get_supabase()` → public schema → use for: publisher (properties, property_photos), live_sync, landlords
- `get_pipeline_schema()` → pipeline schema → use for: ALL pipeline_ tables in repository.py
- Never mix these up. Using `get_supabase().table("pipeline_properties")` fails silently or with schema-cache error.

### Shared AI Client (`backend/services/ai_client.py`)
Single source of truth for all AI config: PLATFORM_CONTEXT, PROMPT_VERSION, call_deepseek(), get_client(), handle_deepseek_error(). Both routers/ai.py and services/ai_enricher.py import from here. Never duplicate.

### JSON Mode
Structured endpoints use `json_mode=True`. Plain-text endpoints (rewrite-description, chat, generate-title) do not.

### Publisher Flow
`publisher_service.py` → `public.properties` (upsert) + ImageKit upload → `public.property_photos` (insert). Never writes to pipeline_ tables.

---

## What This Project Is

A private property management tool for the owner of Choice Properties.

1. Scrape listings from Zillow, Realtor.com, Redfin
2. View and edit in a private dashboard
3. AI-enrich (titles, descriptions, features, quality scores)
4. Publish approved listings to the live Choice Properties website

Nothing touches the live website until the owner explicitly publishes a listing.

---

## Non-Negotiable Rules

### Schema boundaries
- pipeline_ tables → always `self._pipeline` in repository.py
- public tables → always `self._client` or `get_supabase()`
- Never write to public schema tables OTHER than properties + property_photos

### No hardcoded credentials
All credentials are in Replit Secrets. Never commit backend/.env.

### Preserve original data
`original_data` written once on scrape, never changed. `edited_fields` tracks changes.

### No ad-hoc SQL
New tables/columns → add a migration to `choice121/Choice/supabase/migrations/`

### Update this file
After completing any work, mark phases [x] and update the Next Action section.

### Cross-repo changes
When making changes that affect the Choice website's database structure, also update `choice121/Choice`. Use the GitHub token available in the environment.

---

## Project Structure (Key Files)

```
ECOSYSTEM.md                      ← Cross-project bible — read first for any cross-repo work
SETUP_SUPABASE.md                 ← One-time Supabase schema exposure guide
backend/
  database/
    supabase_client.py            ← get_supabase() [public] + get_pipeline_schema() [pipeline]
    repository.py                 ← All CRUD; uses _pipeline for pipeline_ tables
  services/
    ai_client.py                  ← SHARED AI config + client (Phase 1)
    ai_enricher.py                ← Auto-enrichment on scrape
    enrichment_queue.py           ← Rate-controlled enrichment serializer (Phase 3B)
    publisher_service.py          ← Publish to public.properties + ImageKit
    setup_service.py              ← Credential + schema validation
  routers/
    ai.py                         ← All AI endpoints
    properties.py                 ← CRUD endpoints for pipeline properties
    publisher.py                  ← Publish endpoint
    scraper.py                    ← Scraping endpoints
frontend/
  src/
    components/
      AiAssistant.jsx             ← 9-tab AI panel
      PropertyCard.jsx            ← Library cards with AI health badges
      PublishButton.jsx           ← Publish gate with pre-publish checks
    pages/
      Library.jsx                 ← Property grid
      Editor.jsx                  ← Full property editor
      Audit.jsx                   ← Quality dashboard
```

---

## Choice Website — What AI Working Here Needs to Know

The Choice website (`choice121/Choice`) is a **static HTML/CSS/JS site** deployed on **Cloudflare Pages**.

- **No Node.js server, no Python, no Express** — everything runs in the browser + Supabase
- **Backend logic**: Supabase Edge Functions (Deno/TypeScript) in `supabase/functions/`
- **Database migrations**: `supabase/migrations/` — all changes go here
- **Deployment**: Push to `main` → GitHub CI validates → Cloudflare Pages auto-deploys
- **Replit role in Choice**: editing only — Replit is NOT the host
- **Live URL**: https://choice-properties-site.pages.dev

### Choice website tables this pipeline touches (public schema):
- `public.properties` — publisher writes here when a listing is approved
- `public.property_photos` — publisher writes ImageKit URLs here

### Choice website tables this pipeline NEVER touches:
- `public.applications`, `public.leases`, `public.landlords`, `public.sign_events` — all belong to the Choice website's lease/application workflow

---

## Credentials & Environment

| Variable | Purpose |
|---|---|
| SUPABASE_URL | `https://tlfmwetmhthpyrytrcfo.supabase.co` |
| SUPABASE_SERVICE_ROLE_KEY | Full DB access (pipeline + public schema) |
| DEEPSEEK_API_KEY | All AI features |
| IMAGEKIT_PUBLIC_KEY | ImageKit uploads |
| IMAGEKIT_PRIVATE_KEY | ImageKit uploads (server-side) |
| IMAGEKIT_URL_ENDPOINT | ImageKit CDN base URL |
| CHOICE_LANDLORD_ID | Optional — auto-resolved from public.landlords if unset |

DO NOT ask the owner for credentials. They are all in Replit Secrets.

---

## GitHub Push Instructions

```bash
git config user.email "agent@replit.com"
git config user.name "Replit Agent"
git remote set-url origin https://x-access-token:$GITHUB_TOKEN@github.com/choice121/property-pipeline.git
git add -A
git commit -m "Phase X complete: [description]"
git push origin main
```

To also update the Choice repo (when making cross-project changes):
Use the GitHub REST API with the token in `GITHUB_TOKEN` env var. See `ECOSYSTEM.md` for cross-repo rules.
