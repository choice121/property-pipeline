# Choice Properties — Deployment Guide

> **Based on actual codebase scan — April 2026**
> This guide reflects what the code actually does, not what earlier docs assumed.

---

## How the Production Stack Works

| Layer | Technology | Where it runs |
|---|---|---|
| Frontend (listings, landlord portal, admin) | Static HTML / CSS / JS | Cloudflare Pages |
| Config injection | `generate-config.js` | Cloudflare Pages **build step** |
| Database | Supabase (cloud) | Supabase cloud — always on |
| Image delivery | ImageKit CDN | ImageKit cloud |
| Email relay | Google Apps Script | Google's GAS runtime |
| Edge functions | Supabase Edge Functions | Supabase cloud |

> **Replit is a code editor only.** `server.js` in the repo root is a local preview server for
> the Replit environment — it is **not used in production**. Cloudflare Pages serves the static
> files directly. Do not run `npm start` and expect to be running the production stack.

> **`deploy.sh` and `push.sh` are stale and broken.** They reference a deleted Codespaces
> workspace path (`/workspaces/choicepropertiesofficial`) and a deleted GitHub org
> (`choicepropertyofficial1-collab`). Never run these scripts. Use git directly (see below).

---

## Day-to-Day Deployment

All frontend changes deploy automatically on every push to `main`:

```
Edit files in your editor
       ↓
git add .
git commit -m "your message"
git push origin main
       ↓
Cloudflare Pages detects the push
       ↓
Build step runs: node generate-config.js
  - Reads all env vars from Cloudflare Pages dashboard
  - Writes config.js (injecting all public API keys)
  - Rewrites sitemap.xml + robots.txt with SITE_URL
  - Replaces ?v=__BUILD_VERSION__ cache-bust tokens in all HTML files
       ↓
Site is live globally in ~1–2 minutes
```

**config.js is gitignored.** It is generated fresh on every deploy and never committed.

---

## What the Build Step Actually Does

`node generate-config.js` runs at Cloudflare Pages build time and does exactly these things:

1. Reads env vars from the Cloudflare Pages dashboard
2. Validates required vars — fails the build early if any are missing
3. Makes a live HTTP probe to Supabase (`GET /rest/v1/`) to confirm credentials work
4. Writes `config.js` with all public config values baked in
5. Rewrites `sitemap.xml` and `robots.txt`: replaces `YOUR-DOMAIN.com` with `SITE_URL`
6. Replaces `?v=__BUILD_VERSION__` in all `.html` files with a timestamp for cache busting

> **What it does NOT do (despite an earlier stale doc entry):** It does NOT inject CSP nonces.
> Nonce-based CSP was planned and then removed. The `_headers` file uses `'unsafe-inline'`
> for `script-src` intentionally, because the CSS preload pattern requires it and nonces were
> causing CSP mismatches on every Cloudflare deploy.

---

## Environment Variables (Cloudflare Pages)

Set these in **Cloudflare Pages → your project → Settings → Environment variables**.

### Required

| Variable | Value | Notes |
|---|---|---|
| `SUPABASE_URL` | `https://xxxx.supabase.co` | From Supabase → Settings → API |
| `SUPABASE_ANON_KEY` | `eyJ...` anon key | From Supabase → Settings → API |
| `SITE_URL` | `https://yourdomain.com` | **No trailing slash.** Rewrites sitemap.xml and robots.txt |
| `IMAGEKIT_URL` | `https://ik.imagekit.io/your-id` | From ImageKit → Developer Options |
| `IMAGEKIT_PUBLIC_KEY` | Your ImageKit public key | From ImageKit → Developer Options |
| `COMPANY_NAME` | Your business name | Shown in UI and emails |
| `COMPANY_EMAIL` | Your business email | Shown in UI and emails |
| `COMPANY_PHONE` | Your phone number | Shown in UI |
| `COMPANY_ADDRESS` | Your business address | Shown in UI |

### Optional

| Variable | Default | Notes |
|---|---|---|
| `GEOAPIFY_API_KEY` | — | Address autocomplete. Disabled if not set |
| `APPLY_FORM_URL` | `https://apply-choice-properties.pages.dev` | Only change if the Apply form URL ever changes |
| `COMPANY_TAGLINE` | `Your trust is our standard.` | Footer tagline |
| `LEASE_DEFAULT_LATE_FEE_FLAT` | `50` | Flat late fee in dollars |
| `LEASE_DEFAULT_LATE_FEE_DAILY` | `10` | Daily late fee accrual in dollars |
| `LEASE_DEFAULT_EXPIRY_DAYS` | `7` | Days until an unsigned lease expires |
| `FEATURE_CO_APPLICANT` | `true` | Set to `false` to disable co-applicant section |
| `FEATURE_VEHICLE_INFO` | `true` | Set to `false` to disable vehicle info fields |
| `FEATURE_DOCUMENT_UPLOAD` | `true` | Set to `false` to disable document upload |
| `FEATURE_MESSAGING` | `true` | Set to `false` to disable in-app messaging |
| `FEATURE_REALTIME_UPDATES` | `true` | Set to `false` to disable realtime status updates |

> **ADMIN_EMAILS is removed** — it no longer exists in `generate-config.js` or `server.js`.
> For server-side admin notifications, use `ADMIN_EMAIL` (singular) in Supabase Edge Function secrets.

After adding or changing any variable, trigger a redeploy:
**Cloudflare Pages → Deployments → Retry deployment** (or push any commit).

---

## Cloudflare Pages — First-Time Setup

1. Go to **dash.cloudflare.com → Workers & Pages → Create application → Pages → Connect to Git**
2. Connect GitHub and select the **`choice121/Choice`** repository
3. Under **Set up builds and deployments**:
   - **Framework preset**: None
   - **Root directory**: `/` *(repository root)*
   - **Build command**: `node generate-config.js`
   - **Build output directory**: `.` *(a single dot — the repo root)*
4. Add all **Required** environment variables from the table above
5. Click **Save and Deploy**

From this point on, every push to `main` auto-redeploys the frontend.

---

## Deploying Supabase Edge Functions

Edge Functions live in `supabase/functions/` and are deployed **separately** via the Supabase CLI.
Only do this step when you change files inside that directory.

```bash
# One-time login
npx supabase login

# Deploy all functions to YOUR project (replace with your own project ref)
npx supabase functions deploy --project-ref YOUR_PROJECT_REF

# Deploy a single function
npx supabase functions deploy imagekit-upload --project-ref YOUR_PROJECT_REF
```

> **Where to find YOUR_PROJECT_REF:** Supabase → Settings → General → Reference ID.
> Do **not** use the ref in `supabase/config.toml` (`cfsdhylbwzyuvcvbnrel`) —
> that is the original developer's project. You need to supply your own.

Available functions: `imagekit-upload`, `imagekit-delete`, `send-inquiry`, `send-message`

> Alternative: **Supabase Dashboard → Edge Functions → Deploy via UI** (no CLI needed).

### Edge Function secrets

Set these in **Supabase → Settings → Edge Functions → Environment Variables**:

| Secret | Value |
|---|---|
| `GAS_EMAIL_URL` | Your Google Apps Script Web App URL |
| `GAS_RELAY_SECRET` | Your relay secret (must match GAS Script Property `RELAY_SECRET` exactly) |
| `IMAGEKIT_PRIVATE_KEY` | From ImageKit → Developer Options |
| `IMAGEKIT_URL_ENDPOINT` | From ImageKit → Developer Options |
| `ADMIN_EMAIL` | Your admin email — used for server-side notifications |
| `DASHBOARD_URL` | Your live site URL e.g. `https://choiceproperties.com` (no trailing slash) |
| `FRONTEND_ORIGIN` | Same value as `DASHBOARD_URL` — used for CORS validation |

---

## Updating the Google Apps Script Email Relay

The relay script is **`GAS-EMAIL-RELAY.gs`** in the **Choice repo root** (not the Apply repo).

To update it after making code changes:

1. Open **script.google.com** → open your deployed project
2. Replace the script content with the updated `GAS-EMAIL-RELAY.gs`
3. Click **Deploy → Manage deployments → Edit** (pencil icon — NOT 'New deployment')
4. Increment the version and click **Deploy**

> **Critical:** Always use **Manage deployments → Edit**. Never click **New deployment**.
> A new deployment generates a new URL. You would need to update `GAS_EMAIL_URL` in
> Supabase Edge Function secrets or emails will stop sending.

---

## When You Change Domains

Update **all** of these — missing even one breaks something:

1. Cloudflare Pages → your project → **Custom domains** — add new domain
2. Cloudflare Pages → **Environment variables** → update `SITE_URL`
3. Supabase → **Settings → Edge Functions** → update `DASHBOARD_URL` and `FRONTEND_ORIGIN`
4. Supabase → **Authentication → URL Configuration** → update Site URL + both Redirect URLs
5. Google Apps Script → **Script Properties** → update `DASHBOARD_URL`

---

## Security Notes

  - `SUPABASE_SERVICE_ROLE_KEY`, `IMAGEKIT_PRIVATE_KEY`, `GAS_RELAY_SECRET` are stored in Cloudflare Pages env vars but are **not used** by the Cloudflare build process. They are only needed in Supabase Edge Function secrets and the Replit dev server (`server.js`). Consider keeping them in Supabase secrets only and removing them from Cloudflare to reduce secret sprawl.
  - `config.js` is gitignored and contains only public-safe keys (Supabase anon key, ImageKit public key, Geoapify key). Never add private keys to `generate-config.js` output.
  - The Supabase service role key must never reach the browser or be written to `config.js`.
  - Geoapify API keys can be rotated at **app.geoapify.com → API Keys** without any code changes — just update the `GEOAPIFY_API_KEY` env var in Cloudflare and redeploy.

  ---

  ## Verifying a Deployment

After any deploy, verify with these:

- Open `/health.html` on your live site — runs live checks against Supabase + config
- **Cloudflare Pages → Deployments** — build log shows errors from `generate-config.js`
- **Supabase → Edge Functions** — each function shows its last deployment timestamp

---

## Troubleshooting

**"CONFIG is not defined" or page shows no data**
→ Environment variables not set in Cloudflare Pages, or a redeploy hasn't run yet
→ Cloudflare Pages → Deployments → Retry deployment

**Build fails with "Validating Supabase credentials"**
→ `SUPABASE_URL` or `SUPABASE_ANON_KEY` is wrong, or the Supabase project is paused
→ Verify both values in Supabase → Settings → API

**"Apply Now" button goes to wrong URL**
→ Check `APPLY_FORM_URL` env var (default: `https://apply-choice-properties.pages.dev`)
→ If not set, the default in `generate-config.js` is already correct

**Emails not sending**
→ Supabase → Edge Functions → click the function → Logs tab for the exact error
→ Most common cause: `GAS_EMAIL_URL` secret is wrong, or `GAS_RELAY_SECRET` does not
   match the `RELAY_SECRET` in GAS Script Properties

**Images not loading**
→ `IMAGEKIT_URL` is wrong or not set in Cloudflare Pages environment variables

**Address autocomplete not working**
→ `GEOAPIFY_API_KEY` not set, or the key has an HTTP referrer restriction in Geoapify dashboard
→ Geoapify → API Keys → remove the referrer restriction or add your domain

**Admin or landlord login redirects incorrectly after domain change**
→ Update Redirect URLs in Supabase → Authentication → URL Configuration

**Lease signing link broken after domain change**
→ Update `DASHBOARD_URL` in Supabase Edge Function secrets

---

*Choice Properties · Your trust is our standard.*