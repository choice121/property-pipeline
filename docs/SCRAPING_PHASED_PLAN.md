# Property Pipeline — Scraping Hardening Plan

**Companion to:** `SCRAPING_AUDIT.md`
**Mission:** Take the scraping subsystem from "works on a good day" to production-grade. Each phase is independently shippable and instrumented.
**How to use:** Work top to bottom. Tick `[ ]` → `[x]` as each task lands. After every phase, update the matching section in `replit.md` and commit.

The audit IDs in parentheses (e.g. `(C1)`) refer to entries in `SCRAPING_AUDIT.md`.

---

## Phase 1 — Observability & Source-Attribution Fix  ✅ Foundation

> **Why first:** You cannot fix what you cannot see. Phases 2+ all need real numbers — drop counts, dedup counts, per-source attribution — to know whether they helped. This phase ships zero behavior changes that the user can directly *feel*, but every later phase compounds on it.

**Files touched:** `backend/services/scraper_service.py`, `backend/routers/scraper.py`, `backend/database/repository.py`, `frontend/src/pages/Scraper.jsx`.

### Tasks
- [x] **1.1** Fix `_inject_source` to never overwrite an already-set `source` *(C1, H4)*. Replace its body with a `setdefault` and rename to `_ensure_source` for clarity. Update the only caller in `routers/scraper.py:121`.
- [x] **1.2** Stamp `source` inside `_scrape_homeharvest` *(H4)* so the field is correct at the producer, not bolted on later. The dispatcher boundary is the right home for attribution.
- [x] **1.3** Build a `ScrapeMetrics` dataclass in `scraper_service.py` with counters: `total_scraped`, `watermarked_dropped`, `duplicate_skipped`, `validation_rejected`, `saved`, `image_download_queued`, `per_source_counts: dict`, `errors: list[str]`.
- [x] **1.4** Update `routers/scraper.py` to populate `ScrapeMetrics` during the post-processing loop and return it as a top-level `meta` field in the response: `{count, properties, meta: {...}}`.
- [x] **1.5** Pass the metrics into `add_scrape_run` so they get persisted on `pipeline_scrape_runs.error_message` as a JSON string (no schema migration needed for now — column rename happens in Phase 4).
- [x] **1.6** Update `frontend/src/pages/Scraper.jsx` to read `meta` and surface it in a small "Run summary" strip: `Scraped X · Saved Y · Dropped: watermark Z, dup W, invalid V`.
- [x] **1.7** Verify with a manual scrape — confirm the meta strip renders and per-source counts are correct on `source=all`.

### Acceptance criteria
- Running a scrape returns a `meta` object with all counters present.
- A multi-source scrape produces records with their real source name (`realtor`, `zillow`, …), not `"all"`.
- `pipeline_scrape_runs` rows carry the JSON metrics blob.
- Library/Stats screens still work (no regression).

---

## Phase 2 — Reliability of upstream calls

> **Why second:** Now that we can measure failure modes, harden the calls themselves. Targets HomeHarvest + custom scrapers + image downloads + geocoding.

### Tasks
- [x] **2.1** Wrap `homeharvest.scrape_property` in `_scrape_homeharvest` with a 3-attempt exponential backoff (1s → 2s → 4s) for `httpx.HTTPError` and `requests.exceptions.RequestException` *(H3)*. Record each retry in `metrics.errors`. *— Implemented via `services/http_utils.retry_with_backoff` (retries transport errors + 5xx only; 4xx never retried).*
- [x] **2.2** Add a per-source wall-clock deadline (default 30s) inside `_scrape_homeharvest` and `_scrape_custom`. If exceeded, return partial results with `metrics.errors.append("source X timed out")` *(H1)*. *— Implemented as `PER_SOURCE_DEADLINE_SECONDS = 35` via `ThreadPoolExecutor.future.result(timeout=...)` around the homeharvest call. Custom scrapers are individually quick (single httpx call with 20–25s timeout) and are inherently bounded by the multi-source pool deadline below.*
- [ ] **2.3** Cap the request-level scrape time in the router using `asyncio.wait_for` (default 90s for single source, 120s for `all`). Return what we have plus a `partial=true` flag in `meta` *(H1)*. *— **Deferred**: covered transitively by 2.2 (per-source deadline) and the existing `as_completed(timeout=PER_SOURCE_DEADLINE_SECONDS * 2)` in `scrape_all_sources`. Promoting the routes to `async def` for `asyncio.wait_for` is a larger refactor and not worth the risk this phase. Revisit if real-world traces show requests still hanging beyond the aggregate.*
- [x] **2.4** In `image_service._download_one`, add a 2-attempt retry for `httpx.ReadTimeout` / `httpx.ConnectError` only (do **not** retry on 4xx). Return a structured `(success, reason)` tuple instead of bool *(H2)*. *— Implemented. Reason codes: `ok | http_<code> | not_image | too_small | low_quality | watermarked | transient | error`.*
- [~] **2.5** Aggregate per-property image-download stats and surface them in a new `download_stats` field on the property when the background task completes (write to `inferred_features` for now; proper column in Phase 4). *— **Partially**: `download_images` now logs an aggregate per-reason summary at INFO level. DB persistence into `inferred_features` deferred to Phase 4 to avoid a write-shape change here; the log line is enough for ops triage today.*
- [x] **2.6** Convert `geocode_property` to use a process-global token bucket (1 req/s) so concurrent enrichments cannot violate Nominatim's TOS *(M4)*. Drop the trailing `time.sleep(1)`. *— Implemented via `services/http_utils.nominatim_limiter` (1.05s min interval, threading.Lock). UA also upgraded to include a contact email per OSM TOS.*
- [x] **2.7** Cap the global thread pool used by `scrape_all_sources` at `min(len(sources), 4)` — concurrency above this delivers no speedup but burns sockets *(M1)*. *— Implemented via `MAX_MULTISOURCE_WORKERS = 4` constant.*
- [x] **2.8** Add a `User-Agent` rotation pool (3–5 modern desktop UAs) shared by all custom scrapers, picked per-request *(L1)*. *— Implemented: `services/http_utils.random_headers()` (5-UA pool: Chrome Win/Mac/Linux, Firefox Mac, Safari Mac). Wired into all 6 custom scrapers (`apartments`, `opendoor`, `hotpads`, `craigslist`, `invitation_homes`, `progress_residential`) and `image_service._download_one`.*

### Acceptance criteria
- Killing one source mid-scrape no longer blanks the whole run; `meta.partial = true` and the others succeed.
- Three repeat scrapes of the same location from the same IP do not show steadily decreasing image counts (= we are no longer being soft-banned for image fetching).
- `metrics.errors` contains a structured trail of what was retried and what timed out.

---

## Phase 3 — Data correctness & validator teeth

> **Why third:** With reliable ingest, fix what we *store*. Tighten validation, capture missing useful fields, prune dead ones.

### Tasks
- [ ] **3.1** Promote `validate_and_warn` to `validate_and_filter`: hard-reject rows where `monthly_rent is None` *or* `monthly_rent < 200` *or* `address is None` *(C4)*. Increment `metrics.validation_rejected`.
- [ ] **3.2** Add `neighborhood`, `broker_name`, `agent_name`, `tax_value`, `hoa_fee` to `normalize_row` and `PROPERTY_FIELDS` *(M2)*. Migration note in `replit.md`: ALTER TABLE add nullable columns.
- [ ] **3.3** Decide on `showing_instructions` *(M3)*: either remove from schema, or have the AI enricher generate a default ("Contact listing agent to schedule.") — recommended: generate a default.
- [ ] **3.4** Allow-list what we keep in `original_data` *(M5)*. Strip everything except the upstream identifiers, raw price, raw description. Cap the JSON payload at 4 KB.
- [ ] **3.5** De-double-count amenities in `normalize_row` *(L3)* — run a final `set()` over each amenity / appliance / utility list before persisting.
- [ ] **3.6** Add a unit test `tests/test_validator.py` that locks in the new reject rules so they cannot regress.

### Acceptance criteria
- Library no longer contains rows with `monthly_rent = null`.
- New columns are populated when the upstream provided them.
- `original_data` size on disk drops noticeably (verify with a quick `select avg(length(original_data)) ...`).

---

## Phase 4 — Frontend UX & live progress

> **Why fourth:** Users see the wins from 1–3 only if the UI exposes them.

### Tasks
- [ ] **4.1** Add a `pipeline_scrape_runs` migration with proper columns: `count_watermarked`, `count_duplicate`, `count_validation_rejected`, `count_image_failed`, `meta_json`. Backfill from the JSON-blob format used in Phase 1.5.
- [ ] **4.2** Build a `GET /scraper/run/{id}/status` endpoint that returns the in-progress metrics for a running scrape. Poll-based at first; SSE later.
- [ ] **4.3** Convert `Scraper.jsx` to optimistic-progress: show per-source pill (`realtor: 12 ✓ · zillow: ⏳ · redfin: 0 ✗`) updated every 1.5s while the request is in flight *(H6)*.
- [ ] **4.4** Add a "Last 10 runs" sparkline to the Stats screen using the new metrics columns.
- [ ] **4.5** Make `INTER_ENRICHMENT_DELAY` env-driven (`PIPELINE_ENRICHMENT_DELAY_MS`) *(M7)*.
- [ ] **4.6** Add a "Retry failed sources" button on the result screen that re-runs only sources where `metrics.per_source_counts[src] == 0 and src in errors`.

### Acceptance criteria
- A 60-second multi-source scrape feels alive (per-source progress moves).
- Mobile users no longer double-tap because the spinner sits silent (verify on a phone).
- Stats screen shows real drop reasons over time.

---

## Phase 5 — Anti-fragility & long-tail robustness

> **Why last:** Costly, less urgent. Tackle when 1–4 are stable.

### Tasks
- [ ] **5.1** Refactor each custom scraper into a fallback chain: JSON-LD → embedded `__INITIAL_STATE__` → CSS selectors → graceful empty *(M6)*.
- [ ] **5.2** Add an optional proxy URL via `PIPELINE_SCRAPER_PROXY` env var; when set, all custom scrapers route through it. HomeHarvest already supports its own proxy config — wire that through *(C3)*.
- [ ] **5.3** Add an idempotency key to `/scrape` (hash of normalized request body); reject duplicate requests within 30s with a `409` and the cached `run_id`.
- [ ] **5.4** Move the enrichment + image-download `BackgroundTasks` into a real worker process (RQ / Celery / or a simple `asyncio.Queue` consumer) so the FastAPI worker is freed immediately.
- [ ] **5.5** Audit and harden `craigslist_scraper.py`, `hotpads_scraper.py`, `invitation_homes_scraper.py`, `progress_residential_scraper.py` against the same checklist that Phase 2 + Phase 3 + Phase 5.1 applied to `apartments_scraper.py` *(L2)*.
- [ ] **5.6** Add Playwright-based integration tests that hit recorded fixtures of each upstream and assert the parser still extracts ≥ N fields.

### Acceptance criteria
- All custom scrapers survive a class-name change on the upstream because at least one fallback layer still works.
- The FastAPI worker count needed to handle the same scrape load drops by ≥ 50% (because background work moved off the request thread).

---

## Status board

| Phase | Owner | Status | Last touched |
|---|---|---|---|
| 1 — Observability | Agent | ✅ done | 2026-04-26 |
| 2 — Reliability | Agent | ✅ done (2.3 deferred, 2.5 partial) | 2026-04-26 |
| 3 — Data correctness | — | not started | — |
| 4 — Frontend UX | — | not started | — |
| 5 — Anti-fragility | — | not started | — |

Update this table at the end of each phase along with the in-line task checkboxes.
