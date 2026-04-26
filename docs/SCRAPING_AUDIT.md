# Property Pipeline — Scraping Architecture Audit

**Audit date:** 2026-04-26
**Scope:** End-to-end ingestion path — HTTP request → scraper dispatch → normalization → validation → enrichment → persistence → frontend rendering.
**Audience:** Any future engineer or AI agent picking up this codebase. This document is the source of truth for *what is wrong*, *why it matters*, and *where to look*. The companion file `SCRAPING_PHASED_PLAN.md` describes *what to do about it* in ordered, checkable phases.

---

## 1. Architecture at a glance

```
                    POST /scrape  (backend/routers/scraper.py)
                              │
                              ▼
            ┌───── scraper_service.scrape() ─────┐
            │                                    │
            ▼                                    ▼
 _scrape_homeharvest                       _scrape_custom
 (realtor / zillow / redfin                (opendoor / apartments /
  via the homeharvest lib)                  craigslist / hotpads /
            │                                invitation_homes /
            ▼                                progress_residential)
   normalize_row(...)                              │
            │                                    │
            └──────────── results list ──────────┘
                              │
                              ▼
              router post-processing loop
                              │
   ┌──────────┬───────────────┼───────────────┬──────────────┐
   ▼          ▼               ▼               ▼              ▼
watermark  duplicate    rule-based       weighted      Supabase
 filter    by source_   enrichment       quality        upsert
 (silent   listing_id   (template)       score         + scrape_runs
  drop)    (skip)                                       row
                              │
                              ▼
        BackgroundTasks: image download (10-thread pool)
        BackgroundTasks: enqueue_enrichment (1 lock,
         then geocode → detail_fetcher → DeepSeek →
         re-score → save)
                              │
                              ▼
              Supabase `pipeline_properties`
                              │
                              ▼
         frontend (TanStack Query, offline-first)
            Library / Editor / Audit screens
```

Key files:

| Concern | File |
|---|---|
| Public route | `backend/routers/scraper.py` |
| Dispatcher + HomeHarvest + multi-source | `backend/services/scraper_service.py` |
| Custom site scrapers | `backend/services/scrapers/*.py` |
| Field validation | `backend/services/validator.py` |
| Watermark detection | `backend/services/watermark_filter.py` + `backend/services/image_service.py` |
| Image download/store | `backend/services/image_service.py` |
| Rule-based enrichment | `backend/services/enrichment_service.py` |
| HTML detail backfill | `backend/services/detail_fetcher.py` |
| Enrichment queue (lock + async) | `backend/services/enrichment_queue.py` |
| AI enricher (DeepSeek) | `backend/services/ai_enricher.py` |
| Storage | `backend/database/repository.py` (Supabase) |
| Front-end ingest UI | `frontend/src/pages/Scraper.jsx` |

---

## 2. Findings, ranked by severity

Each finding lists: **Symptom** → **Root cause** → **File:line** → **Why it matters**.
Phase numbers refer to `SCRAPING_PHASED_PLAN.md`.

### 🔴 Critical

#### C1. `_inject_source` corrupts per-source attribution on multi-source scrapes
- **Symptom:** When the user picks "All sources", every saved record ends up with `source = "all"` instead of `realtor` / `zillow` / etc.
- **Root cause:** `routers/scraper.py:121` unconditionally calls `_inject_source(results, req.source or "realtor")`, which overwrites the per-source name that `scrape_all_sources` correctly attached at `scraper_service.py:754` (`r.setdefault("source", src_name)`).
- **Why it matters:** Quality stats (`Repository.quality_stats_by_source`) are bucketed by `source`, so the analytics tab silently lies. De-dup across sources is also defeated.
- **Fix in:** Phase 1.

#### C2. Silent drop of watermarked properties with no telemetry returned to caller
- **Symptom:** User scrapes 30 results in a watermark-heavy market and the UI shows 4. They have no idea what happened.
- **Root cause:** `routers/scraper.py:127` skips watermarked records with only a `logger.info`. The `/scrape` response shape is `{count, properties}` — no breakdown.
- **Why it matters:** Internal users keep re-running scrapes thinking they got no hits. The team also can't measure how aggressive the watermark filter is.
- **Fix in:** Phase 1.

#### C3. Custom scrapers have **zero retry, backoff, UA rotation, or proxy support**
- **Symptom:** Apartments.com / HotPads / Craigslist start returning empty lists or 403s after a few runs from a single IP.
- **Root cause:** `services/scrapers/*.py` each open a single `httpx.Client` with one fixed UA, no proxy, no retry. On any non-200 the loop just `break`s.
- **Why it matters:** This is the single biggest source of "the scraper stopped working" reports. There is no way to tell *why* it stopped — was it blocked, rate-limited, or did the markup change?
- **Fix in:** Phase 2.

#### C4. `validate_and_warn` is non-blocking — bad records are persisted
- **Symptom:** Properties with no `monthly_rent` or absurd values are saved with `monthly_rent = None`, which then degrades quality scores and pollutes the Library.
- **Root cause:** `services/validator.py:97-109` only logs warnings. The router does not look at the warning list at all (`scraper.py:145`).
- **Why it matters:** The contract suggests validation, but in practice nothing is blocked. `monthly_rent` is declared `required=True` and is ignored.
- **Fix in:** Phase 3.

---

### 🟠 High

#### H1. `/scrape` route has no request timeout
- **Symptom:** A bad location string or an unresponsive upstream can hold a worker open for minutes; FastAPI returns a 502 to the proxy and the user sees "fetch failed".
- **Root cause:** `routers/scraper.py:75-189` runs the whole scrape inline. `scrape_all_sources` has a 60s `as_completed` timeout but per-source `_scrape_homeharvest` has no time guard. Custom scrapers each set per-request `timeout=25` but loop indefinitely until `len(results) >= limit`.
- **Why it matters:** One stuck request takes a worker out of the pool, increasing tail latency for everyone else.
- **Fix in:** Phase 2.

#### H2. Image download silently swallows all errors
- **Symptom:** Properties show up in the Library with broken thumbnails. No way to know whether the upstream returned 403, the file failed PIL decode, or it was watermarked.
- **Root cause:** `services/image_service.py:93-115` returns `False` for everything from `httpx` errors to wrong content-type to "watermark detected", with no metric or per-image reason recorded.
- **Why it matters:** The user can't distinguish "no images existed" from "we couldn't fetch them" from "we filtered them all".
- **Fix in:** Phase 2.

#### H3. No retry on `homeharvest.scrape_property`
- **Symptom:** Transient 5xx from Realtor/Zillow/Redfin = empty results for that source for the whole run.
- **Root cause:** `services/scraper_service.py:653` calls `scrape_property(**kwargs)` once, no try/except for transient HTTP, no backoff. Only the dispatcher in `scrape_all_sources` catches it (`:739`) and returns `[]`.
- **Why it matters:** First-time users on a fresh IP often see 1–2 sources empty out of three, then they retry and it works — eroding trust.
- **Fix in:** Phase 2.

#### H4. `_inject_source` is the *only* place `source` is set after normalize, so single-source scrapes work by accident
- **Symptom:** Code reads as if `source` is set inside `normalize_row`, but it isn't. Removing or reordering `_inject_source` would silently produce records with `source = None`.
- **Root cause:** `services/scraper_service.py:835-839` is named like a hotfix and acts like one. `normalize_row` (line 415-ish) does not assign `source`.
- **Why it matters:** Brittle. Any refactor of the normalize pipeline can drop the `source` field with no test to catch it. Compounded with C1.
- **Fix in:** Phase 1 (replace with attribution inside `normalize_row` or at the dispatcher boundary).

#### H5. `pipeline_scrape_runs` does not record what was *dropped*
- **Symptom:** The Stats screen says "scraped 30, kept 4" with no explanation.
- **Root cause:** `database/repository.py:267-280` writes only `count_total`, `count_new`, `avg_score`, `error_message`. There is no field for watermark drops, validation rejects, dup skips, image-fetch failures.
- **Why it matters:** Operational blind spot. Without this you cannot tune watermark thresholds or know when a custom scraper is silently degrading.
- **Fix in:** Phase 1 (return in API response and log; persist as additional columns in Phase 4 once the schema is touched).

#### H6. Frontend `/scrape` is request-response only — no progress
- **Symptom:** User clicks "Scrape", sees a spinner for up to 60s with no signal.
- **Root cause:** `frontend/src/pages/Scraper.jsx` posts and `await`s. There is no SSE, no WebSocket, no chunked update.
- **Why it matters:** Mobile users in particular think the app is broken and tap again, multiplying load.
- **Fix in:** Phase 4.

---

### 🟡 Medium

#### M1. `scrape_all_sources` thread fan-out + image-download fan-out can produce ~100 live threads
- **Cause:** Up to 9 source threads × 10 image threads each, plus the enrichment queue. No upper bound at the process level.
- **File:** `services/scraper_service.py:746` and `services/image_service.py:131`.
- **Risk:** Memory pressure on the Replit container; intermittent socket exhaustion.
- **Fix in:** Phase 2.

#### M2. Useful HomeHarvest fields are dropped on the floor
- **Cause:** `normalize_row` ignores `neighborhood`, `broker_name`, `agent_name`, `tax_value`, `hoa_fee`, even though Realtor/Zillow regularly return them.
- **Risk:** Editors lose context they would have used.
- **Fix in:** Phase 3.

#### M3. `showing_instructions` is a dead column
- **Cause:** Declared in `PROPERTY_FIELDS` (`repository.py:12`) but never written. Detail fetcher does not extract it. AI enricher does not populate it.
- **Risk:** Dead UX. Either populate it or remove it.
- **Fix in:** Phase 3.

#### M4. `geocode_property` calls Nominatim with a `time.sleep(1)` *after* the request, not before
- **Cause:** `services/enrichment_service.py:117`. Concurrent requests can still violate Nominatim's 1 req/s policy, and a global sleep blocks unrelated work.
- **Risk:** Soft-banning from Nominatim; slow enrichment.
- **Fix in:** Phase 2 (move to a token bucket).

#### M5. `original_data` blob is persisted as-is, including raw upstream JSON
- **Cause:** `routers/scraper.py:161` passes through `original_data`, which the custom scrapers fill with the entire schema.org item.
- **Risk:** Storage bloat (10–50 KB/row), and any PII or auth fragments in the upstream payload get logged on save errors.
- **Fix in:** Phase 3 (allow-list the fields we keep).

#### M6. `apartments_scraper` parses HTML by class regex
- **Cause:** `services/scrapers/apartments_scraper.py:163, 169, 172, 191, 201, 212` use regex on class names like `r"property-link|listing-link|js-url"`.
- **Risk:** A class rename on the upstream silently kills the scraper.
- **Fix in:** Phase 5 (introduce a fallback chain: JSON-LD → embedded `__SEARCH_STATE__` → cards).

#### M7. Inter-enrichment delay is hardcoded
- **Cause:** `services/enrichment_queue.py:26` `INTER_ENRICHMENT_DELAY = 1.0`, no env var override.
- **Risk:** Cannot tune for DeepSeek throughput.
- **Fix in:** Phase 4.

---

### 🟢 Low

#### L1. No User-Agent rotation
- All scrapers use a single fixed UA. Trivial to fingerprint.

#### L2. `craigslist_scraper`, `hotpads_scraper`, `invitation_homes_scraper`, `progress_residential_scraper` were not deeply audited but are suspected to share C3/H2/M6 patterns.

#### L3. `normalize_row` regexes for amenities/appliances/utilities are case-sensitive in places and may double-count (`"central air"` and `"central a/c"` count as two amenities).

#### L4. `_inject_source` unconditionally mutates rows even when `source` is already set correctly.

---

## 3. Cross-cutting issues

- **No structured per-run report.** There is a `pipeline_scrape_runs` row but it does not capture what was filtered or why. Without this, every other improvement is a guess.
- **No idempotency key on `/scrape`.** A user double-tapping the button issues two real scrapes back-to-back.
- **No queue for scrapes themselves.** If two users scrape the same location concurrently, both pay the upstream cost and both write the same rows (deduped only by `source_listing_id`).
- **Background tasks share the FastAPI worker.** Image downloads and enrichment run in the request worker's process via `BackgroundTasks` — fine for low volume, fragile under load.

---

## 4. What is *good* and worth preserving

- The `WEIGHTED_QUALITY_FIELDS` scoring + `FIELD_FALLBACKS` chain in `scraper_service.py` is genuinely useful and should not be touched.
- The watermark detector in `image_service._has_branded_overlay` is a clever, dependency-light heuristic.
- `enqueue_enrichment` correctly serializes DeepSeek calls with a `threading.Lock`.
- `normalize_row` is defensive (`safe_val` + per-field try/except) and survives partial upstream changes.
- Repository upsert by `id` plus the `source_listing_id` lookup in the router is an effective two-tier dedup.
- The custom-scraper dispatcher in `_scrape_custom` is cleanly extensible — adding a new site is a one-liner.

---

## 5. How to use this document

1. Read `SCRAPING_PHASED_PLAN.md` next.
2. Pick the lowest-numbered unchecked phase.
3. For each task in that phase, the plan links back to the finding ID (C1, H3, etc.) above so you can re-read the rationale.
4. Tick the box, commit, update `replit.md` under the "Scraping" section, then move on.
5. Do not skip phases. Phase 1 (observability) is a prerequisite for measuring whether Phase 2 (reliability) is actually working.
