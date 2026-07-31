# AI Handoff Guide — Property Pipeline

Read this before touching any code.

---

## Current System State (July 2026)

**Fully operational end-to-end.** All features are working.

- ✅ All scrapers working (Zillow, Redfin, Realtor, Apartments, HotPads, Craigslist, Opendoor, Invitation Homes, Progress Residential)
- ✅ 400+ properties in `pipeline.pipeline_properties`
- ✅ Publisher writes to `public.properties` + `public.property_photos`
- ✅ AI enrichment working (Gemini 2.0 Flash + DeepSeek fallback)
- ✅ Image download, watermark scan, bulk publish all working
- ✅ Live sync (pipeline ← public.properties) working
- ✅ Published properties automatically hidden from library
- ✅ Published property IDs are **lowercase** `prop-xxxxxxxx` (critical — see below)

---

## Supabase Schema Architecture

```
pipeline schema (this tool)           public schema (Choice website)
────────────────────────────          ──────────────────────────────
pipeline.pipeline_properties  ──→    public.properties
pipeline.pipeline_enrichment_log     public.property_photos
pipeline.pipeline_scrape_runs        public.landlords (read-only)
pipeline.pipeline_chat_conversations
```

**Code rule**: Always use `get_pipeline_schema()` (not `get_supabase()`) for ALL `pipeline_*` table access. See `backend/database/supabase_client.py`.

The `pipeline` schema is already exposed in Supabase PostgREST. If you ever need to re-expose it:
```
PATCH https://api.supabase.com/v1/projects/tlfmwetmhthpyrytrcfo/config/database/postgrest
Body: {"db_schema": "public,graphql_public,pipeline"}
Auth: Bearer <SUPABASE_ACCESS_TOKEN from env>
```

---

## CRITICAL: Property ID Format

All IDs written to `public.properties` **must be lowercase**:

```python
# CORRECT:
choice_id = "prop-" + uuid.uuid4().hex[:8]    # → "prop-62db29d6"

# WRONG — breaks live URLs (PostgreSQL is case-sensitive):
choice_id = "PROP-" + uuid.uuid4().hex[:8].upper()  # → "PROP-62DB29D6"
```

The Choice website queries `id=eq.prop-62db29d6` (lowercase). An uppercase ID produces a 404 on every listing page.

---

## Library Behaviour

Published properties (those with a `choice_property_id` set) are **excluded from the library** automatically. The backend `GET /api/properties` accepts `exclude_published=true` — the library always passes this. Do not remove this filter.

---

## Credentials

All credentials are in Replit environment variables. Do not ask the owner for them.

| Variable | Purpose |
|---|---|
| `SUPABASE_URL` | `https://tlfmwetmhthpyrytrcfo.supabase.co` |
| `SUPABASE_SERVICE_ROLE_KEY` | Full DB access |
| `SUPABASE_ACCESS_TOKEN` | Supabase Management API |
| `GEMINI_API_KEY` | Primary AI (gemini-2.0-flash) |
| `DEEPSEEK_API_KEY` | Fallback AI |
| `IMAGEKIT_PUBLIC_KEY` | ImageKit uploads |
| `IMAGEKIT_PRIVATE_KEY` | ImageKit uploads (server-side) |
| `IMAGEKIT_URL_ENDPOINT` | ImageKit CDN base URL |
| `GITHUB_TOKEN` | GitHub API (push code changes) |
| `GEOAPIFY_API_KEY` | Geocoding |
| `CHOICE_LANDLORD_ID` | Optional — auto-resolved from Supabase |

---

## GitHub Push (Git CLI is blocked in Replit — use the API)

```javascript
// Push a file via GitHub API (Node.js / CodeExecution tool):
const token = process.env.GITHUB_TOKEN;
const headers = {
  Authorization: `Bearer ${token}`,
  "Accept": "application/vnd.github+json",
  "Content-Type": "application/json"
};

async function pushFile(repo, path, content, message) {
  const shaResp = await fetch(
    `https://api.github.com/repos/choice121/${repo}/contents/${encodeURIComponent(path)}`,
    { headers }
  );
  const sha = shaResp.ok ? (await shaResp.json()).sha : null;
  const body = { message, content: Buffer.from(content).toString("base64") };
  if (sha) body.sha = sha;
  const resp = await fetch(
    `https://api.github.com/repos/choice121/${repo}/contents/${encodeURIComponent(path)}`,
    { method: "PUT", headers, body: JSON.stringify(body) }
  );
  return resp.ok;
}
```

Push files **sequentially** (not in parallel) to avoid SHA conflicts.

Repos: `property-pipeline`, `Choice`

---

## Known Issues

- `pets_allowed` and `smoking_allowed` are force-set to `True` in `publisher_service.py` regardless of scraped values — needs fixing.
- `neighborhood` is scraped and published but not editable in the Editor UI.

---

## How to Run

```bash
bash start.sh
```

Frontend: `http://localhost:5000`  
Backend: `http://localhost:8000`
