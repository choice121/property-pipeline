-- ============================================================
-- Property Pipeline — Phase 3 + Phase 4 Migrations
-- Run this in the Supabase SQL Editor (one-time)
-- ============================================================

-- Phase 3 (3.2): New property detail fields
ALTER TABLE pipeline_properties ADD COLUMN IF NOT EXISTS neighborhood text;
ALTER TABLE pipeline_properties ADD COLUMN IF NOT EXISTS broker_name text;
ALTER TABLE pipeline_properties ADD COLUMN IF NOT EXISTS agent_name text;
ALTER TABLE pipeline_properties ADD COLUMN IF NOT EXISTS tax_value integer;
ALTER TABLE pipeline_properties ADD COLUMN IF NOT EXISTS hoa_fee integer;

-- Phase 4 (4.1): Expanded scrape run metric columns
--   Replaces the JSON blob stuffed in error_message with proper typed columns.
ALTER TABLE pipeline_scrape_runs ADD COLUMN IF NOT EXISTS count_watermarked integer DEFAULT 0;
ALTER TABLE pipeline_scrape_runs ADD COLUMN IF NOT EXISTS count_duplicate integer DEFAULT 0;
ALTER TABLE pipeline_scrape_runs ADD COLUMN IF NOT EXISTS count_validation_rejected integer DEFAULT 0;
ALTER TABLE pipeline_scrape_runs ADD COLUMN IF NOT EXISTS count_image_failed integer DEFAULT 0;
ALTER TABLE pipeline_scrape_runs ADD COLUMN IF NOT EXISTS meta_json text;
ALTER TABLE pipeline_scrape_runs ADD COLUMN IF NOT EXISTS idempotency_key text;

-- Optional: backfill metric columns from JSON blob in error_message
UPDATE pipeline_scrape_runs
SET
  meta_json     = error_message,
  count_watermarked         = COALESCE((error_message::jsonb->>'watermarked_dropped')::int,  0),
  count_duplicate           = COALESCE((error_message::jsonb->>'duplicate_skipped')::int,    0),
  count_validation_rejected = COALESCE((error_message::jsonb->>'validation_rejected')::int,  0)
WHERE error_message IS NOT NULL
  AND error_message != ''
  AND error_message ~ '^\{';
