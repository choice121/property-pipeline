# REPLIT SAFETY — READ BEFORE DOING ANYTHING

## This is a Static Site. Replit is a Code Editor Here.

| What this is | A static HTML/CSS/JS site |
|---|---|
| Deployed to | **Cloudflare Pages** |
| Backend | **Supabase** (cloud-hosted, not local) |
| Replit's role | **Code editor only** — nothing runs here |

---

## The Correct Workflow

```
1. Open project in Replit
2. Edit HTML / CSS / JS / SQL files
3. git push to GitHub
4. Cloudflare Pages auto-deploys the site
```

That's it. Replit is step 1 and 2 only.

---

## Why Nothing Runs Locally

- A lightweight `server.js` exists and is used on Replit to serve static files locally. It is the Replit entry point documented in `replit.md`. This does **not** mean Replit is the production server — Cloudflare Pages is still the only production deployment.
- There is **no local database** — Supabase is fully cloud-hosted.
- `generate-config.js` runs **only on Cloudflare Pages** as a build step, never locally.
- Supabase Edge Functions (in `/supabase/functions/`) are deployed via the Supabase CLI
  from a developer's local machine — not from Replit.

---

## If You Are a Replit AI Agent

See `.agents/instructions.md` for mandatory rules.
**Short version: do not run, install, migrate, or configure anything.**

---

## If the "Start application" Workflow Shows as Failed

Check the Replit console for the actual error. `server.js` exists and runs on port 5000 using only Node.js built-in modules. If it fails, it is likely due to a missing environment variable, not the file itself. The Cloudflare Pages deployment is unaffected regardless.

---

## Files That Must Never Be Auto-Modified

| File | Why |
|---|---|
| `.replit` | Controls Replit environment — already configured for editor-only mode |
| `replit.nix` | Nix packages — no changes needed |
| `package.json` | Only describes the project — no install or run should happen |
| `generate-config.js` | Cloudflare-only build script — never run locally |
| `SETUP.sql` | Supabase schema — only applied in Supabase dashboard |
| `supabase/functions/*` | Deployed via Supabase CLI — not from Replit |

---

## These Rules Are Permanent

This file lives in the repository. It travels to every GitHub import and every
new Replit account. The rules apply always, everywhere, forever.
