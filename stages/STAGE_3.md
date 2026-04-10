# Stage 3 — Image Downloading & Storage

  ## Goal
  Download property images from scraped URLs and store them locally. Serve stored images via a backend endpoint. Update the property record with local image paths. The frontend always loads images from local storage — not from the original scraped URLs.

  ## Prerequisites
  - Stage 2 must be ✅ Complete
  - At least one property in the DB with original_image_urls populated

  ## Acceptance Criteria
  - [ ] Images download automatically after a scrape and are stored at backend/storage/images/{property_id}/1.jpg, 2.jpg, etc.
  - [ ] GET /api/images/{property_id}/1.jpg serves the image file
  - [ ] Properties in the DB have local_image_paths set to a JSON list of relative paths
  - [ ] Failed image downloads are skipped gracefully — the rest still save
  - [ ] Properties with no images have local_image_paths = "[]"
  - [ ] DELETE /api/properties/{id}/images/{index} removes the file and renumbers remaining images
  - [ ] PUT /api/properties/{id}/images/reorder reorders the images by renaming files

  ---

  ## Task List

  ### 3.1 — Implement services/image_service.py

  **download_images(property_id: str, image_urls: list) → List[str]**
  - Create directory: backend/storage/images/{property_id}/
  - Download up to 20 images from the list
  - For each URL:
    - Use httpx with 15s timeout
    - Set User-Agent: `Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36`
    - Skip if response is not 200 or Content-Type does not start with "image/"
    - Skip if file is smaller than 5KB (broken/placeholder image)
    - Save as {n}.jpg where n starts at 1
  - Return list of relative paths: ["storage/images/{property_id}/1.jpg", ...]
  - If all downloads fail, return []

  **delete_image(property_id: str, index: int) → List[str]**
  - index is 1-based (matches filename)
  - Delete the file
  - Rename remaining files sequentially with no gaps
  - Return updated list of paths

  **reorder_images(property_id: str, new_order: List[int]) → List[str]**
  - new_order is list of current 1-based indexes in desired sequence
  - Use temp filenames to avoid collision during rename
  - Return updated list of paths in new order

  ### 3.2 — Hook downloads into the scrape flow

  In scraper_service.py, after inserting a property to the DB:
  - Call image_service.download_images(property_id, original_image_urls_list)
  - Update the property row: set local_image_paths = JSON dump of returned paths
  - Run this in a FastAPI BackgroundTask so scrape endpoint responds immediately
  - Image download continues in background after response is sent

  ### 3.3 — Implement routers/images.py

  ```python
  GET /api/images/{property_id}/{filename}
  ```
  - Construct path: backend/storage/images/{property_id}/{filename}
  - Return FileResponse
  - Return 404 if file not found

  ```python
  DELETE /api/properties/{id}/images/{index}
  ```
  - Call image_service.delete_image(id, index)
  - Update local_image_paths in DB
  - Return updated property

  ```python
  PUT /api/properties/{id}/images/reorder
  Body: { "order": [2, 1, 3] }
  ```
  - Call image_service.reorder_images(id, order)
  - Update local_image_paths in DB
  - Return updated property

  ### 3.4 — Register image routes in main.py

  ---

  ## After Completing This Stage

  1. Scrape a location and wait ~30 seconds for background downloads
  2. Check GET /api/images/{property_id}/1.jpg returns an actual photo
  3. Test image delete and reorder
  4. Commit all changes
  5. Update PROGRESS.md
  6. Update STAGES.md: Stage 3 ✅
  7. Stage 4 (frontend) can run in parallel with Stage 3 — if Stage 4 is not started yet, start it next
  8. Stage 5 requires BOTH Stage 3 and Stage 4 to be ✅ before starting
  