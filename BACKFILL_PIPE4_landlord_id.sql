-- ============================================================
-- PIPE-4 BACKFILL: Set landlord_id on all orphaned pipeline listings
-- Run this ONCE in Supabase SQL Editor after deploying the pipeline fixes.
--
-- All 58 pipeline-published listings have landlord_id = null because
-- CHOICE_LANDLORD_ID was not set in the environment. This links them
-- to the correct landlord account so they appear in the dashboard.
--
-- IMPORTANT: Replace 'YOUR-LANDLORD-UUID-HERE' with the actual UUID
-- from your Supabase landlords table before running.
-- ============================================================

-- Step 1: Find your landlord ID
-- SELECT id, contact_name, email FROM landlords LIMIT 10;

-- Step 2: Preview which rows will be updated
SELECT id, title, city, state, landlord_id, created_at
FROM properties
WHERE landlord_id IS NULL
  AND status = 'active'
ORDER BY created_at DESC;

-- Step 3: Apply the backfill
-- Uncomment and replace the UUID before running.

/*
UPDATE properties
SET landlord_id = 'YOUR-LANDLORD-UUID-HERE'
WHERE landlord_id IS NULL
  AND status = 'active';
*/

-- Step 4: Verify
-- SELECT landlord_id, COUNT(*) FROM properties WHERE status = 'active' GROUP BY landlord_id;
