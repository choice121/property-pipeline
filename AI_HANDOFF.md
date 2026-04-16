# AI Handoff Guide

Read this file completely before touching any code. It is mandatory.

---

## START HERE — Implementation Status

This project has an active multi-phase AI improvement plan. Check the checklist below to find exactly where to continue. Each phase is pushed to GitHub when complete. Do not re-do completed phases.

### Implementation Checklist

#### Phase 1 — Reliability Fixes ✅ COMPLETE
- [x] 1A. Created `backend/services/ai_client.py` — shared PLATFORM_CONTEXT, call_deepseek(), get_client(), handle_deepseek_error(), retry logic with exponential backoff (1s→2s→4s), JSON mode support, PROMPT_VERSION constant
- [x] 1B. Updated `backend/routers/ai.py` — imports from ai_client, all structured endpoints use json_mode=True, markdown stripping removed, PROMPT_VERSION tags on all enrichment log entries
- [x] 1C. Updated `backend/services/ai_enricher.py` — imports from ai_client, uses same PLATFORM_CONTEXT and call_deepseek() as the router, LLM feature extraction (_llm_extract_features) replaces keyword regex list, description generation uses full platform context

#### Phase 2 — Bulk Operation Rate Control ✅ COMPLETE
- [x] 2A. 750ms delay between properties in bulk-clean loop — already present in Phase 1
- [x] 2B. Per-property 429 retry in bulk_clean — `_bulk_clean_with_retry()` helper with 3 attempts, 5s/10s wait
- [x] 2C. Token-aware batching for bulk-scan — already done in Phase 1 (~3000 token budget)
- [x] 2D. Skip recently-scanned properties — last_scanned timestamp stored in `inferred_features` field as `"last_scanned:<ISO>"` tag; bulk_scan skips properties scanned < 24h ago that haven't been edited since (`skip_recent=True` by default)
- [x] 2E. Checkpoint/resume for bulk-clean — `resume=True` param skips properties with `last_cleaned:<ISO>` tag < 1h old; timestamp stored via `_set_inferred_tag()` after each successful clean; no schema changes needed — all stored in existing `inferred_features` column

**Architecture note on 2D/2E:** No Supabase schema changes were made. Timestamps are embedded in the existing `inferred_features` JSON array as tagged strings (`"last_scanned:..."`, `"last_cleaned:..."`). The `update_inferred_features()` method in Repository does a targeted Supabase update that does NOT change `updated_at`, preserving the "edited since last scan" comparison logic.

#### Phase 3 — Smarter Auto-Enrichment ✅ COMPLETE
- [x] 3A. LLM feature extraction — done in Phase 1C
- [x] 3B. Rate-controlled enrichment queue — new `backend/services/enrichment_queue.py` module with `enqueue_enrichment()`. Uses a global `threading.Lock` + 1s post-release sleep so at most one property enrichment runs at a time, preventing DeepSeek being hammered with 50 concurrent calls after a large scrape. `scraper.py` updated to call `enqueue_enrichment` instead of the old `enrichment_background_task` (which is now removed).
- [x] 3C. Smarter enrichment triggers — `enrich_property()` in `ai_enricher.py` now fingerprints `CORE_SCRAPED_FIELDS` + `PROMPT_VERSION` into a 12-char MD5 sig at the start. If the stored sig matches (tag `"enriched_sig:<sig>"` in `inferred_features`), enrichment is skipped entirely. If inputs changed or PROMPT_VERSION bumped, enrichment runs and the new sig is stored. Intentionally excludes AI-generated fields (description, title, amenities, appliances) from the sig to avoid circular triggers.

#### Phase 4 — New Intelligence Features 🔲 NOT STARTED
- [ ] 4A. Streaming for rewrite-description and chat endpoints (FastAPI StreamingResponse + frontend Fetch API)
- [ ] 4B. Neighborhood context paragraph generation (new enrichment task for known cities)
- [ ] 4C. Duplicate detection using DeepSeek embeddings before publish

#### Phase 5 — UX and Tracking Improvements 🔲 NOT STARTED
- [ ] 5A. Publish readiness progress bar (rule-based, no API call, always visible in library + editor)
- [ ] 5B. Accept/reject feedback buttons on AI suggestions → saved to Supabase
- [ ] 5C. Prompt versioning on all enrichment log entries (already partially done via PROMPT_VERSION in ai_client.py)
- [ ] 5D. Description edit history — save previous description before overwriting on PUT

---

## Next Action for Incoming AI

1. Read this file completely
2. Check the checklist above — find the first unchecked item
3. Read the relevant source files before editing
4. Implement the next unchecked phase items
5. Mark items as complete [x] in this file
6. Push to GitHub with a descriptive commit message
7. Continue to the next phase

**Current next step: Begin Phase 4 — start with 4A (streaming for rewrite-description and chat), then 4B (neighborhood context), then 4C (duplicate detection).**

---

## Key Architecture Decisions Made During Implementation

### Shared AI Client Module
`backend/services/ai_client.py` is the single source of truth for all AI configuration:
- `PLATFORM_CONTEXT` — the full system prompt injected into every DeepSeek call
- `PROMPT_VERSION` — bump this string (e.g. "v2" → "v3") when prompts change significantly
- `call_deepseek()` — unified caller with retry logic and json_mode parameter
- `get_client()` — creates the OpenAI-compatible DeepSeek client
- `handle_deepseek_error()` — classifies and raises appropriate HTTP exceptions

Both `backend/routers/ai.py` and `backend/services/ai_enricher.py` import from here. Never duplicate AI client setup elsewhere.

### JSON Mode
All structured endpoints (detect-issues, autofill, bulk-scan, score, pricing-intel, seo-optimize, clean, extract-features) use `json_mode=True` in their `call_deepseek()` call. This passes `response_format={"type": "json_object"}` to the API and eliminates markdown stripping. Plain text endpoints (rewrite-description, suggest-field, chat, generate-title) do not use json_mode.

### Prompt Versioning
Every `repo.add_log()` call uses `method=f"some_method_{PROMPT_VERSION}"`. When prompts are updated, bump `PROMPT_VERSION` in `ai_client.py`. You can then query Supabase for properties enriched with old prompt versions and re-run them.

### LLM Feature Extraction
The auto-enricher now uses `_llm_extract_features()` instead of the old keyword list. This understands nuanced language ("stainless suite" → appliances, "EV rough-in" → EV Charging). If the LLM call fails, it returns empty lists gracefully — no crash.

---

## What This Project Is

A private property management tool for the owner of Choice Properties.

It allows the owner to:
1. Scrape property listings from Zillow, Realtor.com, and Redfin
2. View and edit scraped properties in a private dashboard
3. Publish approved listings to their live website

Nothing touches the live website until Stage 7, and only with explicit owner approval.

---

## Non-Negotiable Rules

### Do not touch the live website before Stage 7
Stage 7 is the only stage that connects to Supabase or ImageKit for publishing.
publisher_service.py handles this — do not modify its publish logic without explicit instruction.

### No hardcoded credentials
All credentials are in Replit Secrets / environment variables.
Never create or commit a backend/.env file.

### Preserve original scraped data
The original_data column is written once (on scrape) and never changed.
The edited_fields column tracks what the owner changed.

### Update this file when done
After completing each phase or sub-task, mark it [x] in the checklist above and update the "Next Action" section. If you do not, the next AI starts blind.

---

## Project Structure (Key Files)

```
backend/
  services/
    ai_client.py        ← SHARED AI config, client, retry logic (NEW — Phase 1)
    ai_enricher.py      ← Auto-enrichment on scrape (updated Phases 1 + 3)
    enrichment_queue.py ← Rate-controlled enrichment serializer (NEW — Phase 3B)
    pricing_service.py  ← Pricing rules applied during enrichment
  routers/
    ai.py               ← All AI API endpoints (updated Phase 1)
    properties.py       ← CRUD endpoints for pipeline properties
    publisher.py        ← Publish to live Supabase + ImageKit
    scraper.py          ← Triggers HomeHarvest scraping
  database/
    repository.py       ← Supabase read/write layer
    supabase_client.py  ← Lazy Supabase connection singleton
frontend/
  src/
    components/
      AiAssistant.jsx   ← 9-tab AI panel in the editor
      PropertyCard.jsx  ← Library cards with AI health badges
      PublishButton.jsx ← Publish gate with pre-publish AI check
    pages/
      Library.jsx       ← Property grid with bulk scan/clean
      Editor.jsx        ← Full property editor
      Audit.jsx         ← Library-wide quality dashboard
```

---

## Credentials & Environment

All credentials are in Replit environment variables. DO NOT ask the owner for them.

| Variable | Purpose |
|---|---|
| SUPABASE_URL | Supabase project REST URL |
| SUPABASE_SERVICE_ROLE_KEY | Supabase service-role JWT |
| DEEPSEEK_API_KEY | All AI features |
| IMAGEKIT_PUBLIC_KEY | ImageKit uploads |
| IMAGEKIT_PRIVATE_KEY | ImageKit uploads |
| IMAGEKIT_URL_ENDPOINT | ImageKit CDN base URL |

Supabase project ID: `tlfmwetmhthpyrytrcfo`
ImageKit account: `21rg7lvzo`

---

## GitHub Push Instructions

The repo remote is: `https://github.com/choice121/property-pipeline`
Current branch: `main`

To push after completing a phase:
```bash
git add -A
git commit -m "Phase X complete: [short description of what was done]"
git push origin main
```

The GITHUB_TOKEN is available as an environment variable. Configure git credentials before pushing:
```bash
git config user.email "agent@replit.com"
git config user.name "Replit Agent"
git remote set-url origin https://x-access-token:$GITHUB_TOKEN@github.com/choice121/property-pipeline.git
git push origin main
```
