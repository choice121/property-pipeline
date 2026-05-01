# Supabase One-Time Setup

This document covers the single manual step required to connect the pipeline to your Supabase database, plus the full database overview.

---

## Required: Expose the Pipeline Schema (One Step)

The pipeline uses a private `pipeline` schema in your Supabase database. This schema must be exposed to the Supabase API. You only do this once.

### Steps

1. Go to your Supabase dashboard:
   **https://supabase.com/dashboard/project/tlfmwetmhthpyrytrcfo/settings/api**

2. Scroll to **"API Settings"**

3. Find the field labeled **"Extra schemas to expose in your API"** (also called `db_extra_search_path`)

4. Add `pipeline` to the list (alongside the default `public`)

5. Click **Save**

6. Come back to this app and click **Recheck** on the setup screen — it should now show green

That's it. The pipeline schema is already set up with all its tables (35,000+ properties from previous scraping). This step just tells Supabase's API layer that it's allowed to talk to them.

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
