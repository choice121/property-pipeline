-- ============================================================
-- PIPE-1 BACKFILL: Fix property_type values on all pipeline-published listings
-- Run this ONCE in Supabase SQL Editor after deploying the pipeline fixes.
--
-- The pipeline was publishing HomeHarvest raw style values (SINGLE_FAMILY,
-- APARTMENT, etc.) instead of the lowercase values the Choice site expects
-- (house, apartment, condo, townhouse). This broke the type filter pills.
-- ============================================================

-- Preview what will change (run this first to verify)
SELECT id, title, property_type,
  CASE property_type
    WHEN 'SINGLE_FAMILY'  THEN 'house'
    WHEN 'APARTMENT'      THEN 'apartment'
    WHEN 'APARTMENTS'     THEN 'apartment'
    WHEN 'CONDO'          THEN 'condo'
    WHEN 'CONDOS'         THEN 'condo'
    WHEN 'CONDO_TOWNHOME' THEN 'condo'
    WHEN 'TOWNHOMES'      THEN 'townhouse'
    WHEN 'TOWNHOME'       THEN 'townhouse'
    WHEN 'MULTI_FAMILY'   THEN 'house'
    WHEN 'DUPLEX_TRIPLEX' THEN 'house'
    WHEN 'MOBILE'         THEN 'house'
    ELSE LOWER(property_type)
  END AS corrected_type
FROM properties
WHERE property_type ~ '^[A-Z_]+$'   -- only rows with ALL-CAPS types (pipeline-published)
ORDER BY property_type, created_at;

-- ── Apply the fix ──────────────────────────────────────────
-- Uncomment and run after reviewing the preview above.

/*
UPDATE properties
SET property_type = CASE property_type
    WHEN 'SINGLE_FAMILY'  THEN 'house'
    WHEN 'APARTMENT'      THEN 'apartment'
    WHEN 'APARTMENTS'     THEN 'apartment'
    WHEN 'CONDO'          THEN 'condo'
    WHEN 'CONDOS'         THEN 'condo'
    WHEN 'CONDO_TOWNHOME' THEN 'condo'
    WHEN 'TOWNHOMES'      THEN 'townhouse'
    WHEN 'TOWNHOME'       THEN 'townhouse'
    WHEN 'MULTI_FAMILY'   THEN 'house'
    WHEN 'DUPLEX_TRIPLEX' THEN 'house'
    WHEN 'MOBILE'         THEN 'house'
    ELSE LOWER(property_type)
  END
WHERE property_type ~ '^[A-Z_]+$';
*/

-- ── Verify after running ───────────────────────────────────
-- SELECT property_type, COUNT(*) FROM properties GROUP BY property_type ORDER BY count DESC;
