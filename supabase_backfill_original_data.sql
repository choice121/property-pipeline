-- Backfill: compact existing pipeline_properties.original_data rows
--
-- Run this in the Supabase SQL Editor (project tlfmwetmhthpyrytrcfo).
-- It keeps only the allow-listed identifier/price keys and drops everything
-- else (photo arrays, full descriptions, agent blobs, etc.), matching the
-- behaviour of the Python _compact_original_data() function added in Phase 3.4.
--
-- Safe to run repeatedly — it skips rows where original_data is already
-- ≤ 4 096 bytes or is null/empty.
--
-- Estimated time: < 5 s for up to ~10 000 rows.

WITH allowed AS (
  -- Build a sub-object containing only the keys we want to keep.
  -- Adjust this list if _ORIGINAL_DATA_KEEP_KEYS ever changes in Python.
  SELECT
    id,
    (
      SELECT jsonb_object_agg(key, value)
      FROM jsonb_each(original_data::jsonb)
      WHERE key IN (
        'mls_id','listing_id','property_url','property_id',
        'list_price','list_price_min','list_price_max',
        'status','list_date','last_sold_date','last_sold_price',
        'tax','hoa_fee','neighborhoods','neighborhood',
        'agent_name','broker_name','office_name'
      )
      OR key LIKE '\_%'  -- keep _-prefixed internal flags
    ) AS compact_data,
    octet_length(original_data) AS original_bytes
  FROM pipeline_properties
  WHERE
    original_data IS NOT NULL
    AND original_data <> ''
    AND original_data <> 'null'
    AND octet_length(original_data) > 4096
)
UPDATE pipeline_properties pp
SET original_data = COALESCE(a.compact_data::text, '{}')
FROM allowed a
WHERE pp.id = a.id;

-- Confirm how many rows were compacted:
SELECT
  COUNT(*) FILTER (WHERE octet_length(original_data) <= 4096) AS rows_within_limit,
  COUNT(*) FILTER (WHERE octet_length(original_data) > 4096)  AS rows_still_over_limit,
  COUNT(*)                                                     AS total_rows,
  pg_size_pretty(SUM(octet_length(original_data)))             AS total_original_data_size
FROM pipeline_properties
WHERE original_data IS NOT NULL;
