-- ============================================================
-- PIPE-2 BACKFILL: Remove duplicate listings published by the pipeline
-- Run this ONCE in Supabase SQL Editor after deploying the pipeline fixes.
--
-- The pipeline had no dedup check vs Supabase, so some properties were
-- published multiple times. This script identifies and removes duplicates,
-- keeping the OLDEST record (first published) for each address.
-- ============================================================

-- Preview duplicates (run first to review)
SELECT
  address, city, state,
  COUNT(*) AS duplicate_count,
  ARRAY_AGG(id ORDER BY created_at ASC) AS ids,
  MIN(created_at) AS first_published
FROM properties
WHERE status = 'active'
  AND landlord_id IS NULL   -- pipeline-published listings have no landlord
GROUP BY address, city, state
HAVING COUNT(*) > 1
ORDER BY duplicate_count DESC;

-- ── Remove duplicates, keep the oldest record ──────────────
-- Uncomment and run after reviewing the preview above.

/*
DELETE FROM properties
WHERE id IN (
  SELECT id FROM (
    SELECT
      id,
      ROW_NUMBER() OVER (
        PARTITION BY address, city, state
        ORDER BY created_at ASC   -- keep oldest (first published)
      ) AS rn
    FROM properties
    WHERE status = 'active'
      AND landlord_id IS NULL
  ) ranked
  WHERE rn > 1
);
*/

-- ── Verify after running ───────────────────────────────────
-- SELECT COUNT(*) FROM properties WHERE status = 'active';
