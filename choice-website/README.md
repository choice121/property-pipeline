# Choice Properties

## STATIC SITE — No backend server required

This repository contains a **pure static frontend** deployed via Cloudflare Pages. There is no application server, no Node.js runtime server, no Python server, and no Docker configuration in this codebase.

All server-side logic runs on fully hosted third-party platforms:

- **Cloudflare Pages** — serves the static HTML / CSS / JS
- **Supabase Edge Functions** — handles all API logic (10 Deno functions deployed to Supabase's cloud)
- **Supabase PostgreSQL** — database with Row Level Security on all tables
- **Google Apps Script** — email relay (deployed separately to Google's platform)
- **ImageKit.io** — property photo CDN
- **Geoapify** — address autocomplete API

## Architecture

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for a full breakdown of every component, all Edge Functions, database tables, the security model, and an explicit list of what does **not** exist in this repository.

## Deployment

- **Cloudflare Pages root directory:** `/` (repository root)
- **Build command:** `node generate-config.js`
- **Build output directory:** `.`

No npm packages are installed at runtime. The build step uses only Node.js built-in modules.

---

## External Application Form Integration

This platform uses a **separate, standalone application form** hosted at:

**`https://apply-choice-properties.pages.dev`**

When a user clicks "Apply Now" on any property listing, they are redirected to this external form with all relevant property data passed as URL query parameters. The external form handles everything from that point — application submission, lease generation, e-signatures, and the applicant dashboard.

### How it works

The `buildApplyURL(property)` function in `js/cp-api.js` constructs the redirect URL with all available property context:

| Parameter | Source field | Purpose in the form |
|---|---|---|
| `id` | `property.id` | Stored for logging |
| `pn` | `property.title` | Property name display + pre-fill |
| `addr` | `property.address` | Pre-fills the address field |
| `city` | `property.city` | Property context banner |
| `state` | `property.state` | Context banner + lease jurisdiction |
| `rent` | `property.monthly_rent` | Income-to-rent ratio display |
| `beds` | `property.bedrooms` | Context display |
| `baths` | `property.bathrooms` | Context display |
| `pets` | Derived from pet fields | Pet policy display |
| `term` | `property.lease_terms` | Lease term display |

### What this platform does NOT do with applications

- Does **not** receive or store application submissions — all data goes to the external form's Google Sheets backend
- Does **not** generate leases — handled by the external form's GAS admin panel
- Does **not** track application status — applicants use the external form's dashboard at `https://apply-choice-properties.pages.dev/?path=dashboard`

### Configuration

`APPLY_FORM_URL` is set in `generate-config.js` and defaults to `https://apply-choice-properties.pages.dev`. It can be overridden via the `APPLY_FORM_URL` environment variable in Cloudflare Pages if the form URL ever changes.

### Platform separation contract

- This site passes data **one-way only** via URL parameters — no API calls to the external form
- The external form does **not** call back to this site
- The two systems share only the redirect link and display-only URL params

---

## Change History

| Date | Changes |
|---|---|
| April 2026 | **Security hardening.** Removed exposure of Geoapify API key from the Apply repo source code. Added build system to Apply site (`generate-config.js` + `package.json`). Synced Cloudflare Pages preview environment variables (was missing 14 vars). Documented correct deployment process for both platforms. |
  | April 2026 | **External application form integration.** All "Apply Now" buttons across `listings.html`, `property.html`, and `index.html` now redirect to `https://apply-choice-properties.pages.dev` with full property context via URL params. All "Track My Application" links in nav, footer, and `faq.html` updated to the external applicant dashboard. `js/cp-api.js` updated: `buildApplyURL()` fallback hardened, `sendRecoveryEmail()` dashboard URL updated. `generate-config.js` `APPLY_FORM_URL` default set. |
| April 2026 | **Frontend audit & mobile optimisation.** Responsive layouts, 44px touch targets, local Font Awesome hosting, CSS preload strategy, image lazy loading, critical CSS inlining, shared nav component, portal links, route highlighting, inline style cleanup, semantic HTML improvements. |

---

## Notes

- Supabase Edge Functions have their own uptime dashboard at [app.supabase.com](https://app.supabase.com) → your project → Edge Functions.
- GAS (Google Apps Script) email relay does **not** have a public health endpoint. Monitor email delivery by reviewing the Email Logs page in the admin panel regularly, or set up a daily cron alert via UptimeRobot pointed at your live site.
- The internal `/apply/` directory, `apply.html`, and all apply-specific JS files (`apply.js`, `apply-submit.js`, etc.) have been **removed**. Old email links and bookmarks pointing to `/apply/*` are handled by `_redirects`, which sends them to the external form automatically.
