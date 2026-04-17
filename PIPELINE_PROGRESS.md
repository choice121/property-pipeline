# Choice Properties — Pipeline Progress Tracker

> Based on the Architecture Proposal: `attached_assets/choice-pipeline-proposal_1776140364085.pdf`
> Track all fixes, improvements, and their completion status here.

---

## Phase 1 · Foundation Fixes
*Goal: Make the existing pipeline safer and the quality score meaningful.*

- [x] **Expand FIELD_FALLBACKS** — Comprehensive fallback chains for monthly_rent, description, security_deposit, available_date, parking, and laundry across all source key variants.
- [x] **Weighted quality scoring** — Replace equal-weight 16-field scoring with a weighted system that reflects real publish-readiness (address 25pts, rent 20pts, beds+baths 15pts, photos 15pts, description 10pts, type 5pts, date 5pts, amenities 5pts).
- [x] **Pre-publish hard blocking rules** — Add `pre_publish_checks()` to publisher_service.py that runs before any ImageKit upload. Blocks on: missing address, missing rent, missing bedrooms, no local images, and quality score below 50.
- [x] **Validation rules (type, range, choices)** — New `services/validator.py` with typed range checks and allowed-value enforcement for rent, beds, baths, sqft, year_built, state, and property_type.
- [x] **Enhanced image filter (PIL dimension + blank detection)** — Add dimension checks (min 200×150) and solid-color/near-blank detection to the existing image download filter.

---

## Phase 2 · Enrichment Layer
*Goal: Auto-fill missing fields using rule-based logic, no external APIs.*

- [x] **Rule-based enrichers** — `services/enrichment_service.py` with title generation, available_date fallback (list_date or today), deposit inference (1× rent), and pet policy from description keywords. Runs inline before saving every new property.
- [x] **Nominatim geocoding fallback** — Free OSM geocoding for properties missing lat/lng. Runs as a background task after scrape, respects the 1 req/sec rate limit.
- [x] **`detail_fetcher.py`** — Background HTML fetch for sub-70 score properties to extract available_date, security_deposit, and lease_terms via regex from the listing source URL.
- [x] **Wire enrichment into scrape background task** — Rule-based enrichers run inline (before save); geocoding and detail_fetcher run as background tasks after save.
- [x] **Recalculate quality score after enrichment** — Score is recalculated after rule-based enrichment (inline) and again after background geocoding/detail-fetch completes, then persisted to the DB.

---

## Phase 3 · Enrichment Intelligence (Free, No APIs)
*Goal: Fill remaining gaps using template-based generation and expanded rule extraction — zero cost, zero dependencies.*

- [x] **`services/ai_enricher.py`** — Free enrichment engine: template-based description generator that assembles professional listing descriptions from all available property fields; expanded amenity/appliance extractor (30+ patterns); advanced pet policy text classifier; keyword-based property type classifier. Same interface as the proposal — swappable for a real LLM later with zero router changes.
- [x] **`ai_enrichment_log` table** — New `AiEnrichmentLog` SQLite model tracking every auto-filled field (field name, method used, ai_value). Logs which method filled each field (`template`, `rule_extraction`, `rule_classification`).
- [x] **Wire enricher into background task** — Runs automatically after geocoding and detail_fetcher in `enrichment_background_task`. Quality score recalculated one final time after all enrichment completes.
- [x] **Override tracking in editor** — `PUT /api/properties/{id}` now detects when a field that was auto-enriched is manually edited, marks `was_overridden=True` in the log, and stores the human value. Feedback loop is live from day one.

---

## Phase 4 · Monitoring & UI
*Goal: Surface data quality trends and catch scraper failures early.*

- [x] **`scrape_runs` table** — `pipeline_scrape_runs` table created in Supabase; `ScrapeRunRecord` + `add_scrape_run()` / `list_scrape_runs()` added to Repository; scraper router logs every run (source, location, count_total, count_new, avg_score).
- [x] **`GET /api/stats/quality` endpoint** — `backend/routers/stats.py` with `GET /api/stats/quality` (aggregates count, avg/min/max score, by-status breakdown grouped by source) and `GET /api/stats/scrape-runs`; "Stats" toggle button on Library page reveals live panel; "Run AI" button queues bulk enrichment via `POST /api/ai/bulk-enrich`.
- [ ] **Quality score badges in Library.jsx** — Show score and blocked/ready status in the property list.
- [ ] **"Enrich with AI" button in Editor.jsx** — Trigger AI enrichment for blocked/low-score properties.
- [ ] **Canary health check** — Detect when a source stops returning expected fields.

---

## Completed Bug Fixes (Pre-Proposal)

- [x] **PIPE-1** — Property type normalization (`SINGLE_FAMILY` → `house`) for Supabase schema.
- [x] **PIPE-2** — Duplicate prevention via address+city+state check against Supabase before inserting.
- [x] **PIPE-3** — Source stamping fix — each property correctly reflects its actual scrape source.
- [x] **PIPE-4** — `CHOICE_LANDLORD_ID` warning when env var is missing.
- [x] **PIPE-8** — Pet policy `None` preserved (not coerced to `False`) when no pet data found.
- [x] **PIPE-10** — `sync_fields()` — re-sync all editable fields to Supabase without re-uploading images.
- [x] **PIPE-11** — Removed broken JWT truncation from Supabase client init.
- [x] **PIPE-12** — Boilerplate cleaning (`_clean_description`) strips TurboTenant/platform text before publish.
- [x] **PIPE-13** — `application_fee` defaults to 0 explicitly.
- [x] **PIPE-14** — Image cap at 25 photos per listing.
