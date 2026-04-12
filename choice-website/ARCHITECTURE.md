# Choice Properties — System Architecture

---

## ══════════════════════════════════════════════════════════
## STOP — AI AGENTS READ THIS FIRST — NON-NEGOTIABLE
## ══════════════════════════════════════════════════════════
##
## THIS PROJECT IS A STATIC WEBSITE. IT IS NOT BEING MIGRATED.
## IT IS FULLY SET UP. DO NOT TOUCH THE DATABASE. DO NOT MIGRATE.
##
## MANDATORY: Read `.agents/instructions.md` before any action.
## It contains the complete rule set that governs this project.
##
## SHORT VERSION — NEVER, UNDER ANY CIRCUMSTANCES:
## - Provision or connect to Replit/Neon PostgreSQL
## - Use DATABASE_URL, PGHOST, PGPASSWORD, or any PG variable
## - Install Drizzle, Prisma, Sequelize, or any ORM
## - Run db:push, db:migrate, or any database command
## - Create backend server files or api/ directories
## - Run wrangler or any Cloudflare CLI command
## - Run git push, git commit, or any git write command
##
## `integrations = ["javascript_database:1.0.0"]` IN .replit IS
## A LOCKED SYSTEM ARTIFACT. IT DOES NOT MEAN USE A LOCAL DB.
## IGNORE IT COMPLETELY. EVERY TIME. FOREVER. NO EXCEPTIONS.
##
## YOUR ONLY JOB: Edit static HTML, CSS, and frontend JS files.
## ══════════════════════════════════════════════════════════

---

## Overview

Choice Properties is a **pure static frontend** connected to fully hosted backend services. There is no application server in this repository. Every component runs either in the browser or on a third-party hosted platform.

```
Browser
  │
  ├── Cloudflare Pages CDN  ← serves static HTML / CSS / JS
  │
  ├── Supabase              ← database, auth, realtime, storage
  │     ├── PostgreSQL (RLS enforced on all tables)
  │     ├── Supabase Auth (landlord + admin login)
  │     ├── Realtime (application status updates)
  │     ├── Storage (lease PDFs, application docs — private)
  │     └── Edge Functions (4 active Deno functions — 7 decommissioned, pending Supabase dashboard deletion)
  │
  ├── Google Apps Script    ← email relay (deployed separately)
  │
  ├── ImageKit.io           ← property photo CDN + transforms
  │
  ├── Geoapify              ← address autocomplete API
  │
  └── apply-choice-properties.pages.dev  ← external application form
        (separate system — receives one-way redirect with URL params)
```

---

## Component Breakdown

### Frontend — Cloudflare Pages

| Type | Details |
|---|---|
| Language | Vanilla JavaScript (ES6+), HTML5, CSS3 |
| Framework | None |
| Build step | `node generate-config.js` — injects env vars into `config.js`, rewrites `sitemap.xml` + `robots.txt` with `SITE_URL`, and cache-busts `?v=__BUILD_VERSION__` tokens in HTML files |
| Structured data | JSON-LD on `index.html` (WebSite+SearchAction), `listings.html` (CollectionPage), `property.html` (RealEstateListing+BreadcrumbList) |
| Deployment | Cloudflare Pages (auto-deploy on push to `main`) |
| CDN | Cloudflare global CDN (automatic, no configuration needed) |
| Security headers | `_headers` file (X-Frame-Options, CSP, HSTS, etc.) — CSP `script-src` uses `'unsafe-inline'` intentionally (CSS preload pattern requires it; nonce-based CSP was planned in I-052 but removed due to CSP mismatches on Cloudflare deploys) |
| 404 handling | `_redirects` file (catch-all → `404.html`) |

The build step uses only Node.js built-in modules (`fs`, `process.env`). No npm packages are installed during the build.

---

### Backend API — Supabase Edge Functions

  4 Deno-based Edge Functions are active. 7 application-related functions were removed from this repository and must be deleted from the Supabase dashboard (they are still deployed).

  #### Active Functions

  | Function | Purpose | Auth required |
  |---|---|---|
  | `send-inquiry` | Send property inquiry to landlord | Public (rate-limited) |
  | `send-message` | Send message in thread | Admin only |
  | `imagekit-upload` | Authenticated photo upload to ImageKit | Authenticated user |
  | `imagekit-delete` | Delete photo from ImageKit CDN | Authenticated user |

  #### Decommissioned Functions — Action Required

  All application and lease processing moved to the external GAS system. The 7 functions below have been removed from this repository but are **still running on Supabase** and should be deleted to eliminate unnecessary live endpoints.

  **Go to:** [Supabase Dashboard → Edge Functions](https://supabase.com/dashboard/project/tlfmwetmhthpyrytrcfo/functions) → delete each:

  | Function | Was responsible for |
  |---|---|
  | `process-application` | Application intake (now handled by GAS `doPost()`) |
  | `generate-lease` | Lease generation (now: GAS admin panel) |
  | `sign-lease` | E-signature processing (now: GAS lease portal) |
  | `update-status` | Status updates (now: GAS admin panel) |
  | `mark-paid` | Payment marking (now: GAS admin panel) |
  | `mark-movein` | Move-in confirmation (now: GAS admin panel) |
  | `get-application-status` | Tenant status check (now: GAS `?path=dashboard`) |

  **Deployment (active functions only):** `npx supabase functions deploy --project-ref tlfmwetmhthpyrytrcfo` (see SETUP.md → Step 7)

  These functions are NOT part of this repository's local runtime. They run on Deno in Supabase's cloud.
---

### Database — Supabase PostgreSQL

| Table | Description |
|---|---|
| `properties` | Rental listings |
| `landlords` | Landlord profiles |
| `applications` | Tenant applications (SSN masked to last-4) |
| `co_applicants` | Co-applicant data linked to applications |
| `messages` | Application thread messages |
| `inquiries` | Property inquiry submissions |
| `email_logs` | All email send attempts with status |
| `admin_roles` | Admin user registry |
| `admin_actions` | Admin audit trail — records every admin action with actor and timestamp |
| `saved_properties` | Tenant saved listings |
| `rate_limit_log` | DB-backed rate limiting — stores IP, endpoint, and timestamp |

Row Level Security (RLS) is enabled on all tables. The complete schema, RLS policies, triggers, indexes, and **table-level grants** are all in `SETUP.sql` — one file, one run.

**Key helper database functions:**
- `is_admin()` — returns `true` if the current session's user exists in `admin_roles`. Used in RLS policies across all tables.
- `immutable_array_to_text(arr text[], sep text)` — `IMMUTABLE` wrapper around `array_to_string`. Required for use in generated column expressions (PostgreSQL requires all functions in generated columns to be immutable).

> **Important:** RLS policies alone are not enough. PostgreSQL requires both a table-level `GRANT` (giving the role permission to touch the table at all) AND an RLS policy (determining which rows that role can see). Without the grants, all queries return `permission denied` even when valid RLS policies exist. `SETUP.sql` includes both. If you ever see `permission denied for table X`, run the grant block in `SETUP.sql` section 14 manually in the SQL Editor.

---

### Email — Google Apps Script Relay

A Google Apps Script Web App receives email requests from Supabase Edge Functions and sends them via Gmail. The script source is in `GAS-EMAIL-RELAY.gs` and must be manually deployed to Google's platform.

Secret verification (`RELAY_SECRET`) is enforced on every request. The GAS URL and secret live only in Supabase Edge Function secrets — never in the frontend.

---

### Image Storage — ImageKit.io

Property photos and landlord avatars are served through ImageKit's global CDN. Upload is handled by the `imagekit-upload` Edge Function (private key stays in Supabase secrets). The frontend receives CDN URLs and applies transform presets for different display sizes.

**Upload flow:**
```
Browser (imagekit.js)
  → fileToBase64(file)
  → POST /functions/v1/imagekit-upload
      { fileData, fileName, folder }   ← field name must be 'fileData'
  → Edge Function authenticates caller, forwards to ImageKit Upload API
  → Returns { success, url, fileId }
  → Browser stores url in properties.photo_urls[]
```

**Previously known gaps (all resolved as of Session 019):**
| Gap | Issue | Status |
|---|---|---|
| `fileId` is discarded — cannot delete from ImageKit | I-028 | ✅ RESOLVED |
| Photos removed from a listing are never deleted from CDN | I-015 | ✅ RESOLVED |
| Uploads are sequential (one at a time) — slow on mobile | I-016 | ✅ RESOLVED |

**Post-launch improvement (Phase 3 backlog):**
Replace `photo_urls TEXT[]` on the `properties` table with a dedicated `property_photos` table for per-photo metadata, sort order, and clean CDN deletion. See `.agents/instructions.md` Phase 3 backlog for details.

---

### Application & Lease Storage — External GAS System

All application intake, lease generation, e-signatures, and document storage are handled by the **external application system** at `apply-choice-properties.pages.dev` — not by this platform's Supabase instance.

| Data | Where stored | How accessed |
|---|---|---|
| Rental applications | Google Sheets (GAS backend) | GAS admin panel at `?path=admin` |
| Lease documents | Google Sheets + Google Drive | GAS admin panel |
| Applicant-uploaded docs | Google Drive (GAS backend) | GAS admin panel |
| Application status | Google Sheets (GAS backend) | Applicant dashboard at `?path=dashboard` |

**This platform does not store, read, or process applications.** All admin pages that previously showed Supabase application data now redirect to the GAS admin panel. The Supabase `lease-pdfs` and `application-docs` storage buckets referenced in older documentation are no longer in use.

---

## Security Model

| Concern | Mechanism |
|---|---|
| Database access | Table-level grants (`GRANT`) + RLS policies on every table; service role key server-side only |
| Admin auth | JWT verified server-side against `admin_roles` table |
| SSN data | Masked to last-4 on receipt; never stored full |
| Lease signing | 192-bit random tokens per lease; verified server-side |
| Email relay | HMAC secret verified on every request |
| Rate limiting | In-memory per-IP limits on all public Edge Functions |
| File access | All sensitive buckets private; signed URLs only |
| CORS | Edge Functions use `Access-Control-Allow-Origin: *` (public API) |
| Frontend config | `config.js` generated at build time; gitignored; no-cache headers |

---

## What Does NOT Exist In This Repository

| What you might expect | Reality |
|---|---|
| Express / Fastify / Koa server | None — no server at all |
| Node.js API routes | None — Supabase Edge Functions handle all server logic |
| Python Flask / Django | None |
| Local database | None — Supabase is the database |
| Redis / queue / workers | None |
| Docker / docker-compose | None |
| `.env` file with secrets | None — secrets live in Supabase and GAS dashboards |
| npm packages for runtime | None — `generate-config.js` uses only Node.js built-ins |

---

## Local Development

Any static file server works. No build pipeline is needed for local development.

```bash
# From the repository root:
python3 -m http.server 8080
# OR
npx serve .
```

Create a local `config.js` from `config.example.js` with your Supabase credentials. This file is gitignored.

---

## Data Flow — Tenant Applies for a Property

Applications are handled entirely by the **external application form** at `https://apply-choice-properties.pages.dev`. This platform's role is only to redirect the tenant with property context.

```
Tenant clicks "Apply Now" on listings.html or property.html
  │
  └── buildApplyURL(property) in js/cp-api.js
        │
        ├── Writes property context to sessionStorage (same-origin fallback)
        └── Builds redirect URL with query params:
              ?id=<id>&pn=<title>&addr=<address>&city=<city>
              &state=<state>&rent=<rent>&beds=<beds>&baths=<baths>
              &pets=<pet_policy>&term=<lease_term>
              │
              └── window.location → https://apply-choice-properties.pages.dev
                    │
                    ├── Form pre-fills from URL params
                    ├── Tenant completes 6-step application
                    ├── GAS backend stores data in Google Sheets
                    ├── Confirmation email sent to tenant
                    └── Admin notified — manages lease via GAS admin panel
```

This platform does **not** receive, store, or process application data. All application state lives in the external form's Google Sheets backend.

---

## Data Flow — Property Inquiry (Contact Landlord)

```
Browser → POST /functions/v1/send-inquiry
            │
            ├── Rate limit check (in-memory, per IP)
            ├── Fetch landlord email from properties table
            └── POST to GAS relay → Gmail sends inquiry to landlord
```

---

## External Application Form

Tenant applications are handled by a completely separate system:

| Property | Value |
|---|---|
| URL | `https://apply-choice-properties.pages.dev` |
| Frontend | Vanilla HTML/CSS/JS — single `index.html` |
| Backend | Google Apps Script (`code.gs`) |
| Storage | Google Sheets (auto-managed by GAS) |
| Admin panel | `?path=admin` — served by GAS |
| Applicant dashboard | `?path=dashboard&id=<appId>` |

### Integration contract (one-way, read-only)

This platform sends the following URL params when redirecting to the form. The external form treats them as **display-only** — they pre-fill fields and show context banners but are never used for backend validation.

| Param | Value |
|---|---|
| `id` | `property.id` |
| `pn` | `property.title` |
| `addr` | `property.address` |
| `city` | `property.city` |
| `state` | `property.state` |
| `rent` | `property.monthly_rent` |
| `beds` | `property.bedrooms` |
| `baths` | `property.bathrooms` |
| `pets` | Derived pet policy string |
| `term` | Lease term string |

**This platform never calls the external form's API and the external form never calls this platform.**

### Configuration

`APPLY_FORM_URL` in `generate-config.js` defaults to `https://apply-choice-properties.pages.dev`. Override with the `APPLY_FORM_URL` Cloudflare Pages environment variable if the URL changes.

---

## Deployment Checklist

- [ ] Supabase project created, `SETUP.sql` run in SQL Editor (one file, one run — includes schema, RLS, functions, grants, and storage buckets)
- [ ] Supabase Edge Function secrets set (see SETUP.md Step 4 for full list)
- [ ] Google Apps Script deployed, URL added as `GAS_EMAIL_URL` secret
- [ ] Supabase Auth redirect URLs configured (Site URL + landlord + admin redirect URLs)
- [ ] Cloudflare Pages project created, all environment variables set (see SETUP.md Step 6) — including `APPLY_FORM_URL`
- [ ] Edge Functions deployed — see SETUP.md Step 7. If deploying from mobile/no CLI, use the Supabase Dashboard → Edge Functions → Deploy via UI
- [ ] Admin account created via SQL insert into `admin_roles` (see SETUP.md Step 8)
- [ ] `health.html` checks passing on the live site
- [ ] At least 3–5 listings seeded via landlord dashboard so homepage shows live content
- [ ] Verify "Apply Now" buttons redirect to `https://apply-choice-properties.pages.dev` with correct property params
- [ ] Verify "Track My Application" links in nav, footer, and FAQ point to the external applicant dashboard

  ---

  ## Changelog

  ### 2026-04-07 — Property Data Completeness Improvements

  Addressed systematic gap where DB columns existed but were never collected in landlord forms.

  **Financial Fields (new inputs in Step 2 of new-listing / edit-listing):**
  - last_months_rent — Last month rent amount (was always NULL before)
  - admin_fee — One-time move-in/admin fee (was always NULL before)
  - move_in_special — Free-text move-in promotion/special (was always NULL before)

  **Structured Pet Policy (replaces single text-box in Step 3):**
  - pet_types_allowed — Array of allowed pet types: Dogs, Cats, Birds, Small Animals, Reptiles
  - pet_weight_limit — Dog weight limit in lbs (dropdown: none / 15 / 25 / 50 / 75 / 100)
  - pet_deposit — Separate pet deposit amount (was always NULL before)
  - pet_details — Free-text notes now a secondary field, not the primary input

  **Structured Parking (replaces single select in Step 3):**
  - parking — Now includes Covered, Garage (Attached/Detached), Gated options
  - garage_spaces — Number of spaces included (was always NULL before)
  - parking_fee — Monthly parking fee separate from rent (was always NULL before)
  - ev_charging — EV charging availability: none / available / included

  **Systems and Appliances (new selects added to Step 3):**
  - laundry_type — In-unit / hookups / shared / laundromat / none
  - heating_type — Gas forced air / electric / baseboard / radiant / heat pump / boiler / other
  - cooling_type — Central A/C / mini-split / window units / evaporative / none

  All fields write to columns that already existed in the DB schema (zero schema changes required).
  Draft autosave and draft restore updated to persist all new fields.


---

## Application System Architecture Decision (2026-04-09)

All rental application processing is handled exclusively by the external GAS system at **apply-choice-properties.pages.dev**. The Supabase applications table and related database objects are legacy and should be removed by running MIGRATION_drop_applications_tables.sql in the Supabase SQL Editor.

### What moved to GAS

| Capability | Was (Supabase) | Now (GAS) |
|---|---|---|
| Application submission | Edge Functions + PostgreSQL | GAS doPost + Google Sheets |
| Lease generation | sign_lease stored procedure | GAS generateAndSendLease |
| Lease e-signing | Supabase stored procedure | GAS lease signing page |
| Application status | applications table | Google Sheets row |
| Email notifications | GAS relay via Edge Function | GAS MailApp directly |
| Admin dashboard | admin_application_view | GAS web app admin panel |

### What stays in Supabase

landlords, properties, inquiries, email_logs, saved_properties, rate_limit_log, admin_roles, admin_actions, and the 4 active Edge Functions: send-inquiry, send-message, imagekit-upload, imagekit-delete.

### Cleanup actions required

1. Run MIGRATION_drop_applications_tables.sql in Supabase SQL Editor (includes pre-flight row-count check).
2. Delete the 7 decommissioned application Edge Functions from Supabase Dashboard -> Edge Functions.
3. Update or remove admin/applications.html and admin/leases.html — they reference the removed Supabase applications table and should redirect to the GAS admin dashboard.
