# Stage 5 — Property Library UI

  ## Goal
  Build the main Library page. This is the home screen of the app. It shows all scraped properties in a grid, with photos, key details, and status badges. Includes search, filter by status, and sort controls.

  ## Prerequisites
  - Stage 3 must be complete (images are being downloaded and served)
  - Stage 4 must be complete (React app shell is running)

  ## Acceptance Criteria
  - [ ] / loads the Library page with real data from GET /api/properties
  - [ ] Each property shows: first photo, address, city/state, beds, baths, price, status badge
  - [ ] If a property has no images, a placeholder image is shown
  - [ ] Status badge shows correct label with color: scraped (gray), edited (blue), ready (yellow), published (green)
  - [ ] Clicking a property card navigates to /edit/{id}
  - [ ] Search input filters properties by address or city in real time (client-side)
  - [ ] Status dropdown filters by status (All, Scraped, Edited, Ready, Published)
  - [ ] Sort dropdown: Newest First, Price Low to High, Price High to Low, Beds
  - [ ] Empty state shown when no properties match filter
  - [ ] Loading state shown while data is fetching

  ---

  ## Task List

  ### 5.1 — Write src/components/StatusBadge.jsx
  Accepts a status prop. Returns a colored pill label.
  - scraped: gray background
  - edited: blue background
  - ready: yellow/amber background
  - published: green background

  ### 5.2 — Write src/components/PropertyCard.jsx
  Props: property object, onClick handler.

  Card contents:
  - Image: first item in local_image_paths served from /api/images/{id}/filename, or placeholder SVG if none
  - Price: formatted as $X,XXX/mo
  - Address: full address line
  - City, State, Zip on second line
  - Beds / Baths / Sqft row (show N/A if missing)
  - StatusBadge at top-right corner
  - Entire card is clickable

  Image URL construction:
  local_image_paths is a JSON array stored as a string. Parse it. Take the first path.
  The path looks like: "storage/images/PP-A1B2C3/1.jpg"
  Serve it at: /api/images/PP-A1B2C3/1.jpg

  ### 5.3 — Write src/pages/Library.jsx

  Use useQuery from TanStack Query to fetch GET /api/properties.

  State:
  - search: string
  - statusFilter: string ("" for all)
  - sort: string ("scraped_at")

  Apply filters client-side to the fetched list.

  Layout:
  - Page title "Property Library" with count of shown properties
  - Row of controls: search input, status dropdown, sort dropdown, and a "Scrape More" button linking to /scraper
  - Property grid (3 columns on desktop, 2 on tablet, 1 on mobile)
  - Loading skeleton when fetching
  - Empty state message when no results

  ### 5.4 — Polish
  - Responsive grid using Tailwind grid cols
  - Hover state on cards (subtle shadow or border)
  - Loading skeleton: gray rectangles where cards would be

  ---

  ## After This Stage

  1. Run both backend and frontend, scrape a location first to have data
  2. Verify library shows properties with photos
  3. Test search, filter, and sort
  4. Commit all files
  5. Update PROGRESS.md
  6. Update STAGES.md: Stage 5 complete, unlock Stage 6
  7. Next: Stage 6 — Property Editor UI
  