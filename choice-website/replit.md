# Choice Properties — Replit Setup

## Overview

Choice Properties is a nationwide rental marketplace — a static HTML/CSS/JS site with a Supabase cloud backend.

## Architecture

- **Frontend**: Static HTML/CSS/JS site (no frontend framework/bundler)
- **Backend**: Supabase cloud (PostgreSQL + Auth + Storage + Edge Functions)
- **Image CDN**: ImageKit
- **Address autocomplete**: Geoapify
- **Email relay**: GAS (Google Apps Script) + Resend

## How It Runs on Replit

A lightweight Node.js server (`server.js`) serves the static files with several performance optimisations applied at serve time. No npm packages are required — only built-in Node.js modules are used.

```
node server.js   → listens on port 5000
```

The server:
1. Generates `/config.js` on every request from environment variables (no-cache)
2. **Injects nav + footer server-side** — reads `components/nav.html` and `components/footer.html` at startup and inserts them directly into every HTML response, eliminating 2 fetch() calls per page load
3. **Pre-fetches and caches property listings** — fetches the first 24 active properties from Supabase REST API at startup (refreshes every 3 minutes), embeds as `window.__INITIAL_LISTINGS__` in `listings.html` so properties render instantly on first paint with no loading spinner
4. Serves all static files (HTML, CSS, JS, images, fonts) from the project root
5. Applies **Cache-Control headers** — static assets (CSS/JS/fonts/images) get `max-age=31536000 immutable`; HTML gets `no-cache` for freshness
6. Handles directory index resolution and `.html` extension inference
7. Redirects browser-auto-requested icons to `/assets/favicon.svg`

The **Supabase JS library** (`js/supabase.min.js`) is self-hosted locally — all 23 HTML files reference the local copy instead of the jsdelivr CDN, removing a cross-origin dependency.

### Client-side optimisation (listings.html)
`fetchAndRender()` checks for `window.__INITIAL_LISTINGS__` on the first unfiltered page-1 load. If the server has injected data, it renders immediately and skips the Supabase API round-trip entirely. Filter changes and pagination always fetch fresh data from the live API.

## Environment Variables

All non-sensitive configuration is stored as Replit environment variables (shared). The Supabase anon key is stored as a Replit secret.

| Variable | Purpose | Storage |
|---|---|---|
| `SUPABASE_URL` | Supabase project URL | Env var |
| `SUPABASE_ANON_KEY` | Supabase anonymous key (public JWT) | Replit Secret |
| `IMAGEKIT_URL` | ImageKit CDN base URL | Env var |
| `IMAGEKIT_PUBLIC_KEY` | ImageKit public upload key | Env var |
| `GEOAPIFY_API_KEY` | Address autocomplete API key | Env var |
| `COMPANY_NAME` | Displayed company name | Env var |
| `COMPANY_EMAIL` | Company contact email | Env var |
| `COMPANY_PHONE` | Company phone number | Env var |
| `COMPANY_ADDRESS` | Company address | Env var |
| `COMPANY_TAGLINE` | Company tagline | Env var |
| `SITE_URL` | Canonical site URL | Env var |
| `APPLY_FORM_URL` | External apply form base URL | Env var |
| `ADMIN_EMAILS` | Admin notification email(s) | Env var |
| `PORT` | Server port (default: 5000) | Env var |

## Key Files

| File | Purpose |
|---|---|
| `server.js` | Node.js static file server (Replit entry point) |
| `generate-config.js` | Cloudflare Pages build script (not used on Replit) |
| `js/cp-api.js` | Shared API client — wraps Supabase calls |
| `supabase/functions/` | Supabase Edge Functions (deployed via Supabase CLI, not run on Replit) |
| `SETUP.sql` | Database schema (applied in Supabase dashboard) |
| `webfonts/` | Font Awesome webfont files |

## Site Pages

  **Public pages:**
  - `/` — Homepage with property search
  - `/listings.html` — Browse available properties
  - `/property.html?id=...` — Individual property detail page
  - `/about.html` — About Choice Properties
  - `/faq.html` — Frequently asked questions
  - `/how-it-works.html` — How the platform works
  - `/how-to-apply.html` — Application guide for tenants

  **Policy pages (added April 2026):**
  - `/fair-housing.html` — Fair Housing Policy
  - `/holding-deposit-policy.html` — Holding Deposit Policy
  - `/rental-application-policy.html` — Rental Application Policy
  - `/application-credit-policy.html` — Application Credit Policy
  - `/landlord-platform-agreement.html` — Landlord Platform Agreement
  - `/privacy.html` — Privacy Policy
  - `/terms.html` — Terms of Service

  **Admin portal (login-protected):**
  - `/admin/login.html` — Admin login
  - `/admin/dashboard.html` — Admin dashboard

  **Landlord portal (login-protected):**
  - `/landlord/login.html` — Landlord login
  - `/landlord/dashboard.html` — Landlord dashboard

## Supabase Edge Functions

  The backend logic lives in `supabase/functions/`. These are deployed to Supabase directly (not run on Replit).

  **4 active functions:**
  - `send-inquiry` — sends property inquiry to landlord (public, rate-limited)
  - `send-message` — sends message in an application thread (admin only)
  - `imagekit-upload` — authenticates and proxies photo uploads to ImageKit CDN
  - `imagekit-delete` — deletes a photo from ImageKit CDN

  **7 decommissioned functions** (moved to external GAS system — pending deletion from Supabase dashboard):
  `generate-lease`, `sign-lease`, `update-status`, `mark-paid`, `mark-movein`, `get-application-status`, `process-application`

  See `ARCHITECTURE.md` for full details on the decommission list and what replaced each function.

## Application System

All rental applications are handled by the **external application system** at `https://apply-choice-properties.pages.dev`. "Apply Now" buttons redirect there with property details pre-filled as URL params.
