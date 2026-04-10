# Stage 7 — Publisher (Connects to Live Website)

  ## IMPORTANT: READ THIS BEFORE STARTING

  This stage connects to the owner's live Choice Properties website.
  It must NOT be started until:
  1. Stages 1 through 6 are ALL marked complete in STAGES.md
  2. The owner has reviewed the working tool and approved moving forward
  3. The owner has provided all required credentials
  4. The owner has explicitly said to proceed

  Do not prompt or pressure the owner for credentials. Wait for them to initiate.

  ---

  ## Goal
  Build the publish flow. When the owner clicks Publish to Choice Properties on a property, the tool uploads its images to their ImageKit account and inserts a record into their Supabase database with status active. The listing goes live immediately.

  ## Prerequisites
  - Stages 1 through 6 all complete
  - Owner approval received
  - All 5 credentials saved to backend/.env

  ## Required Credentials
  ```
  SUPABASE_URL=
  SUPABASE_SERVICE_ROLE_KEY=
  IMAGEKIT_PRIVATE_KEY=
  IMAGEKIT_PUBLIC_KEY=
  IMAGEKIT_URL_ENDPOINT=
  CHOICE_LANDLORD_ID=
  ```

  ## Acceptance Criteria
  - [ ] POST /api/publish/{id} uploads all property images to ImageKit
  - [ ] POST /api/publish/{id} inserts a row into Choice Properties Supabase properties table
  - [ ] Inserted row has status="active" and landlord_id from .env
  - [ ] This tool marks property as status="published" with published_at and choice_property_id
  - [ ] Listing appears correctly on the live website
  - [ ] Publishing an already-published property returns a 400 error
  - [ ] If ImageKit upload fails, Supabase insert is NOT attempted
  - [ ] Errors are surfaced clearly, not swallowed silently

  ---

  ## Task List

  ### 7.1 — Add Python dependencies

  Add to requirements.txt and install:
  ```
  supabase==2.5.0
  imagekitio==3.2.5
  ```

  ### 7.2 — Implement services/publisher_service.py

  Step 1: Upload images to ImageKit
  ```python
  from imagekitio import ImageKit
  import os

  def upload_images(property_id, local_image_paths):
      ik = ImageKit(
          private_key=os.getenv("IMAGEKIT_PRIVATE_KEY"),
          public_key=os.getenv("IMAGEKIT_PUBLIC_KEY"),
          url_endpoint=os.getenv("IMAGEKIT_URL_ENDPOINT")
      )
      results = []
      for path in local_image_paths:
          with open(path, "rb") as f:
              resp = ik.upload(file=f, file_name=os.path.basename(path),
                               options={"folder": f"/properties/{property_id}"})
          results.append({"url": resp.url, "file_id": resp.file_id})
      return results
  ```

  Step 2: Insert into Supabase properties table

  Key fields to populate from the property record:
  - id: new PROP- prefixed ID (different from the PP- ID used internally)
  - landlord_id: CHOICE_LANDLORD_ID from env
  - status: "active"
  - All address, location, bedroom, bathroom, rent fields
  - amenities, appliances: parse from JSON string to list
  - photo_urls: list of ImageKit URLs
  - photo_file_ids: list of ImageKit fileIds

  Use supabase-py:
  ```python
  from supabase import create_client
  client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))
  result = client.table("properties").insert(record).execute()
  ```

  Step 3: Update local record
  - Set status = "published"
  - Set published_at = current timestamp
  - Set choice_property_id = ID returned from Supabase insert

  Main publish function sequence:
  1. Check not already published — raise 400 if choice_property_id is already set
  2. Upload images to ImageKit — raise on failure before touching Supabase
  3. Insert into Supabase — raise on failure
  4. Update local DB record
  5. Return success

  ### 7.3 — Implement routers/publisher.py

  ```
  POST /api/publish/{id}
  ```
  - Fetch property from DB or 404
  - Call publisher_service.publish(property)
  - Return { "ok": true, "choice_property_id": "...", "message": "Published successfully" }

  ### 7.4 — Register publisher router in main.py

  ### 7.5 — Add PublishButton.jsx to the frontend

  Add to the Editor page. Only visible when property status is "ready".

  States:
  - Default: "Publish to Choice Properties" button
  - Confirm: "This will go live immediately on your website. Confirm?" with Confirm and Cancel
  - Loading: spinner with "Publishing..."
  - Success: green confirmation with published date
  - Error: red message with error text

  If property is already published: show static green label with published date instead of button.

  ---

  ## After This Stage

  1. Test with one property set to "ready"
  2. Click publish, verify image in ImageKit, verify listing on live website
  3. Verify cannot publish twice
  4. Commit all changes
  5. Update PROGRESS.md
  6. Update STAGES.md: Stage 7 complete
  7. Project is complete — notify the owner
  