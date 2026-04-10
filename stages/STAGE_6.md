# Stage 6 — Property Editor UI

  ## Goal
  Build the full property editor page. When you click a property in the Library, you open the Editor. You can edit every field, manage photos (reorder, delete), set the property status, and save. The original scraped data is shown alongside for comparison.

  ## Prerequisites
  - Stage 5 must be complete

  ## Acceptance Criteria
  - [ ] Clicking a property card in the Library navigates to /edit/{id}
  - [ ] All property fields are pre-filled with current data
  - [ ] Every field is editable (input, textarea, select as appropriate)
  - [ ] Photo gallery shows all local images
  - [ ] Clicking the X on a photo deletes it (calls DELETE /api/properties/{id}/images/{index})
  - [ ] Photos can be reordered by drag-and-drop or up/down buttons
  - [ ] Saving calls PUT /api/properties/{id} with changed fields
  - [ ] After save, edited_fields tracking is visible (a small note showing which fields were modified)
  - [ ] Status can be changed via a dropdown: Scraped, Edited, Ready to Publish
  - [ ] Back button returns to Library
  - [ ] A "Compare with Original" toggle shows original scraped values next to current values
  - [ ] Delete button removes the property and returns to Library

  ---

  ## Task List

  ### 6.1 — Write src/components/ImageGallery.jsx

  Props: propertyId, images (array of path strings), onDelete(index), onReorder(newOrder)

  Display:
  - Horizontal scrollable row of image thumbnails
  - Each thumbnail has an X button to delete
  - Arrow buttons (left/right) on each image to reorder
  - First image is marked as "Cover Photo"
  - Show count: "3 photos"

  Image URL construction:
  Path format: "storage/images/PP-ABC/1.jpg"
  Display URL: "/api/images/PP-ABC/1.jpg"
  Parse the filename from the path and construct the URL.

  ### 6.2 — Write src/pages/Editor.jsx

  Use useParams to get the property id.
  Use useQuery to fetch GET /api/properties/{id}.
  Use useMutation for PUT /api/properties/{id}.

  Local state: a form object initialized from the fetched property. All edits stay in local state until Save is clicked.

  Form sections (use fieldset or section dividers):
  1. Basic Info: title, property_type, status dropdown
  2. Location: address, city, state, zip, county
  3. Details: bedrooms, bathrooms, half_bathrooms, square_footage, lot_size_sqft, year_built
  4. Pricing: monthly_rent, security_deposit, application_fee, pet_deposit
  5. Policies: pets_allowed (checkbox), pet_details, smoking_allowed (checkbox), parking
  6. Description: textarea for description, virtual_tour_url
  7. Amenities: text input for comma-separated list (display as tag chips)
  8. Photos: ImageGallery component

  Buttons:
  - Save Changes: PUT /api/properties/{id} with full form state
  - Mark as Ready: sets status to "ready" and saves
  - Delete Property: confirm dialog, then DELETE /api/properties/{id}, then navigate to /
  - Back to Library: link to /

  Compare with Original toggle:
  - Small toggle button at top of page
  - When on: show a side panel or inline annotation with original_data values for each field
  - Fields that have been edited are highlighted

  Edited fields indicator:
  - After save, show a small note: "3 fields edited from original"

  ### 6.3 — Register /edit/:id route in App.jsx
  It should already be there from Stage 4. Confirm Editor.jsx is imported correctly.

  ---

  ## After This Stage

  1. Scrape a location, click a property, edit several fields, save
  2. Verify edited_fields tracking works
  3. Test image delete and reorder
  4. Test status change and delete
  5. Commit all files
  6. Update PROGRESS.md
  7. Update STAGES.md: Stage 6 complete
  8. Stage 7 is locked — it requires owner approval and credentials
  9. Note in PROGRESS.md that the tool is ready for owner review before Stage 7
  