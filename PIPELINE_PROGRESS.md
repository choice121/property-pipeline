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

- [ ] **Rule-based enrichers** — `services/enrichment_service.py` with title generation, available_date fallback, deposit inference (1× rent), and pet policy from description keywords.
- [ ] **Nominatim geocoding fallback** — Free OSM geocoding for properties missing lat/lng.
- [ ] **`detail_fetcher.py`** — Background HTML fetch for sub-70 score properties to extract available_date, deposit, and lease_terms via regex.
- [ ] **Wire enrichment into scrape background task** — Run enrichers after normalization, before saving score.
- [ ] **Recalculate quality score after enrichment** — Score must reflect post-enrichment completeness.

---

## Phase 3 · AI Integration
*Goal: Fill remaining gaps using Claude API for properties with score 40–79.*

- [ ] **`services/ai_enricher.py`** — Claude Haiku API calls for description generation, amenity extraction, pet policy inference, and property type classification.
- [ ] **`ANTHROPIC_API_KEY` env var** — Add to `.env.example`.
- [ ] **Wire AI enricher** — Run for properties with quality score 40–79 as background task.
- [ ] **`ai_enrichment_log` table** — Track AI-inferred vs human-corrected values per field for feedback loop.

---

## Phase 4 · Monitoring & UI
*Goal: Surface data quality trends and catch scraper failures early.*

- [ ] **`scrape_runs` table** — Log every scrape invocation (source, location, count, avg_score, errors).
- [ ] **`GET /api/stats/quality` endpoint** — Aggregate quality stats by source for dashboard.
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
