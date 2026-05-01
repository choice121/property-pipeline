# Supabase Setup

This document covers the Supabase database configuration for the pipeline, plus the full database overview.

---

## Pipeline Schema Exposure — ALREADY DONE ✅

The `pipeline` schema is already exposed to the Supabase PostgREST API. No manual action is needed.

This was configured programmatically via the Supabase Management API:
```
PATCH https://api.supabase.com/v1/projects/tlfmwetmhthpyrytrcfo/config/database/postgrest
Body: {"db_schema": "public,graphql_public,pipeline"}
```

**If you ever need to re-do this** (e.g. after a Supabase project reset):
1. Use the token in `SUPABASE_MANAGEMENT_API_TOKEN` (Replit Secrets)
2. Send the PATCH request above
3. Or go to: https://supabase.com/dashboard/project/tlfmwetmhthpyrytrcfo/settings/api and add `pipeline` to "Extra schemas"

The setup screen in the app will show ✅ for both schemas when everything is correct.

---

## Why This Step Exists

When the Choice website team did a security cleanup (migration `20260426000002_pipeline_private_schema.sql`), they moved the pipeline tables from the public database area into a private `pipeline` schema. This is good security practice — it prevents tenants or anonymous users from ever seeing the internal pipeline data.

The tradeoff is that Supabase's API doesn't expose private schemas by default. Adding `pipeline` to the extra schemas list restores the pipeline's access while keeping the security benefit.

---

## Database Overview — What Lives Where

### `pipeline` schema (this project owns these)
| Table | What it contains |
|---|---|
| `pipeline.pipeline_properties` | All scraped listings (staging area before publishing) |
| `pipeline.pipeline_enrichment_log` | AI-generated content history per property |
| `pipeline.pipeline_scrape_runs` | Log of every scrape job |
| `pipeline.pipeline_chat_conversations` | AI chat history per property |

### `public` schema (Choice website owns these — do not alter from this project)
| Table | What it contains |
|---|---|
| `public.properties` | Live listings shown to tenants |
| `public.property_photos` | Photo URLs on ImageKit CDN |
| `public.landlords` | Landlord account |
| `public.applications` | Rental applications |
| `public.leases` | Signed leases |

---

## If You Need to Add New Pipeline Tables or Columns

Do **not** run ad-hoc SQL. Add a dated migration file to the Choice website repo:

```
choice121/Choice/supabase/migrations/YYYYMMDDHHMMSS_pipeline_your_change.sql
```

Use `CREATE TABLE IF NOT EXISTS` or `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` so migrations are safe to re-run. Then deploy via the Supabase CLI from the Choice repo.

---

## Optional: Set CHOICE_LANDLORD_ID

Your Supabase database has one landlord row. Setting this variable saves a Supabase lookup on every publish:

```sql
-- Run in Supabase SQL Editor to find your landlord UUID:
SELECT id FROM public.landlords LIMIT 1;
```

Copy that UUID and add it as `CHOICE_LANDLORD_ID` in your Replit Secrets.
