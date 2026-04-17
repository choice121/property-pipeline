-- ============================================================
-- Property Pipeline — Supabase Migration
-- Run this entire script in your Supabase SQL Editor once.
-- ============================================================

CREATE TABLE IF NOT EXISTS pipeline_properties (
  id                    TEXT PRIMARY KEY,
  source                TEXT NOT NULL,
  source_url            TEXT,
  source_listing_id     TEXT,
  status                TEXT DEFAULT 'scraped',
  title                 TEXT,
  address               TEXT,
  city                  TEXT,
  state                 TEXT,
  zip                   TEXT,
  county                TEXT,
  lat                   DOUBLE PRECISION,
  lng                   DOUBLE PRECISION,
  bedrooms              INTEGER,
  bathrooms             DOUBLE PRECISION,
  half_bathrooms        INTEGER,
  square_footage        INTEGER,
  lot_size_sqft         INTEGER,
  monthly_rent          INTEGER,
  property_type         TEXT,
  year_built            INTEGER,
  floors                INTEGER,
  unit_number           TEXT,
  total_units           INTEGER,
  description           TEXT,
  showing_instructions  TEXT,
  available_date        TEXT,
  parking               TEXT,
  garage_spaces         INTEGER,
  pets_allowed          BOOLEAN,
  pet_types_allowed     TEXT,
  pet_weight_limit      INTEGER,
  pet_details           TEXT,
  smoking_allowed       BOOLEAN,
  lease_terms           TEXT,
  minimum_lease_months  INTEGER,
  security_deposit      INTEGER,
  last_months_rent      INTEGER,
  application_fee       INTEGER,
  pet_deposit           INTEGER,
  admin_fee             INTEGER,
  move_in_special       TEXT,
  parking_fee           INTEGER,
  amenities             TEXT,
  appliances            TEXT,
  utilities_included    TEXT,
  flooring              TEXT,
  heating_type          TEXT,
  cooling_type          TEXT,
  laundry_type          TEXT,
  total_bathrooms       DOUBLE PRECISION,
  has_basement          BOOLEAN,
  has_central_air       BOOLEAN,
  virtual_tour_url      TEXT,
  original_image_urls   TEXT,
  local_image_paths     TEXT DEFAULT '[]',
  original_data         TEXT,
  edited_fields         TEXT DEFAULT '[]',
  data_quality_score    INTEGER,
  missing_fields        TEXT DEFAULT '[]',
  inferred_features     TEXT DEFAULT '[]',
  published_at          TEXT,
  choice_property_id    TEXT,
  scraped_at            TIMESTAMPTZ DEFAULT NOW(),
  updated_at            TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS pipeline_enrichment_log (
  id             BIGSERIAL PRIMARY KEY,
  property_id    TEXT NOT NULL REFERENCES pipeline_properties(id) ON DELETE CASCADE,
  field          TEXT NOT NULL,
  method         TEXT NOT NULL,
  ai_value       TEXT,
  human_value    TEXT,
  was_overridden BOOLEAN DEFAULT FALSE,
  created_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pipeline_properties_status
  ON pipeline_properties (status);

CREATE INDEX IF NOT EXISTS idx_pipeline_properties_source_listing_id
  ON pipeline_properties (source_listing_id);

CREATE INDEX IF NOT EXISTS idx_pipeline_enrichment_log_property_id
  ON pipeline_enrichment_log (property_id);

-- Phase 4: Scrape run tracking
CREATE TABLE IF NOT EXISTS pipeline_scrape_runs (
  id             BIGSERIAL PRIMARY KEY,
  source         TEXT NOT NULL,
  location       TEXT NOT NULL,
  count_total    INTEGER DEFAULT 0,
  count_new      INTEGER DEFAULT 0,
  avg_score      DOUBLE PRECISION,
  error_message  TEXT,
  started_at     TIMESTAMPTZ DEFAULT NOW(),
  completed_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pipeline_scrape_runs_source
  ON pipeline_scrape_runs (source);

CREATE INDEX IF NOT EXISTS idx_pipeline_scrape_runs_completed_at
  ON pipeline_scrape_runs (completed_at DESC);
