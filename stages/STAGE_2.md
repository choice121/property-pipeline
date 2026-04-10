# Stage 2 — Scraping Engine

  ## Goal
  Integrate HomeHarvest into the backend. Build POST /api/scrape endpoint that takes a location and filters, runs HomeHarvest, normalizes returned data, and saves property records to SQLite.

  ## Prerequisites
  - Stage 1 must be complete
  - Backend running and responding to GET /api/health

  ## Acceptance Criteria
  - [ ] POST /api/scrape with body returns properties from the given location
  - [ ] Properties saved to SQLite properties table
  - [ ] GET /api/properties returns saved properties
  - [ ] Each property has: id, source, status="scraped", address, city, state, bedrooms, monthly_rent, original_data, scraped_at
  - [ ] Same scrape twice does not create duplicates (upsert by source_listing_id)
  - [ ] No results returns { "count": 0, "properties": [] } without error
  - [ ] HomeHarvest error returns HTTP 500 with clear message

  ---

  ## Task List

  ### 2.1 — Implement services/scraper_service.py

  HomeHarvest usage:
  ```python
  from homeharvest import scrape_property

  results = scrape_property(
      location="Austin, TX",
      listing_type="for_rent",
      site_name=["zillow"],
      past_days=60
  )
  # results is a pandas DataFrame
  ```

  Field mapping (HomeHarvest to our schema):
  - street -> address
  - city -> city
  - state -> state
  - zip_code -> zip
  - county -> county
  - latitude -> lat, longitude -> lng
  - beds -> bedrooms, full_baths -> bathrooms
  - sqft -> square_footage, lot_sqft -> lot_size_sqft
  - list_price -> monthly_rent
  - style -> property_type
  - year_built -> year_built
  - text -> description
  - property_url -> source_url
  - mls_id -> source_listing_id
  - img_srcs -> original_image_urls (json dump of list)
  - virtual_tours -> virtual_tour_url (first item or null)

  Property ID format: "PP-" + first 6 chars of uuid4 uppercase. Example: PP-A1B2C3

  original_data: Full raw row as JSON string. Never modify after first insert.

  Status on insert: always "scraped"

  Upsert logic: If source_listing_id already exists, skip. Return existing record.

  ### 2.2 — Implement routers/scraper.py

  Request (Pydantic model):
  ```python
  class ScrapeRequest(BaseModel):
      location: str
      source: str = "zillow"
      listing_type: str = "for_rent"
      min_price: Optional[int] = None
      max_price: Optional[int] = None
      bedrooms: Optional[int] = None
  ```

  Endpoint logic:
  1. Call scraper_service.scrape(request)
  2. Upsert each result to DB
  3. Return { count, properties[] }

  ### 2.3 — Implement routers/properties.py

  GET /api/properties
  - Query params: status, search (matches address/city), sort (scraped_at|monthly_rent|bedrooms)
  - Returns list

  GET /api/properties/{id}
  - Returns single or 404

  PUT /api/properties/{id}
  - Body: partial fields
  - Compare each field against original_data, add differing field names to edited_fields
  - Set status="edited" unless already "ready" or "published"
  - Update updated_at
  - Return updated property

  DELETE /api/properties/{id}
  - Delete record
  - Return { "ok": true }

  ### 2.4 — Register routes in main.py

  ---

  ## After This Stage

  1. Test with curl: POST /api/scrape then GET /api/properties
  2. Commit all changes
  3. Update PROGRESS.md
  4. Update STAGES.md: Stage 2 complete, unlock Stage 3
  5. Next: Stage 3 — Image Downloading and Storage
  