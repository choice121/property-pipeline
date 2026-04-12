REFERENCE DOCUMENT — All issues listed here are resolved as of April 8, 2026.
  For ongoing project status, read PROJECT_STATUS.md in choice121/Apply_choice_properties.

  ---

  # Known Issues — Choice Listing Platform

  **Deep scan completed:** April 8, 2026
  **Companion fix document:** `PHASE9_BUG_FIXES.md` in choice121/Apply_choice_properties
  **Status:** All issues resolved — April 8, 2026

  ---

  ## Overview

  A comprehensive deep scan of both the Choice listing platform (this repo) and the
  Apply_choice_properties repo was completed April 8, 2026. The following issues were
  found in this repo. They are listed in priority order and cross-referenced with the
  Phase 9 fix plan in the Apply repo.

  Fix these in order. Do not skip ahead to lower-priority items.

  ---

  ## CRITICAL — Resolved

  ### ISSUE-C1 — Property detail page crashes when monthly_rent is null

  **Priority:** 🔴 Critical (Phase 9A-3)
  **Status:** ✅ Resolved — April 8, 2026 (commit: `fix: Phase 9A-3 — null-guard all p.monthly_rent.toLocaleString() calls in renderProperty()`)
  **File:** `property.html`
  **Function:** `renderProperty(p)` — OG meta description block

  **What breaks:**

  If any property in the Supabase `properties` table has a null or missing `monthly_rent`,
  the property detail page goes completely blank. No user-facing error — the page just
  white-screens and then redirects to the home page after 2 seconds.

  ```javascript
  // This line throws TypeError if p.monthly_rent is null:
  const ogDesc = `... · $${p.monthly_rent.toLocaleString()}/mo · ...`;
  ```

  **Exact fix:**

  ```javascript
  // Replace the monthly_rent reference in the ogDesc line:
  const rentDisplay = p.monthly_rent != null
    ? '$' + Number(p.monthly_rent).toLocaleString() + '/mo'
    : 'Rent TBD';
  const ogDesc = `... · ${rentDisplay} · ...`;
  ```

  Then search `renderProperty()` for any other direct access to `p.monthly_rent` without
  a null check (e.g. in the sidebar cost display) and apply the same guard.

  ---

  ## IMPORTANT — Resolved

  ### ISSUE-C2 — Pets/smoking "false" URL param is truthy

  **Priority:** 🟡 Important (Phase 9B-3)
  **Status:** ✅ Verified Safe — April 8, 2026 (no truthy conditional found in Apply form; Supabase returns native booleans in Choice repo — no code change needed)
  **File:** `property.html` (also `js/script.js` in Apply repo)
  **Relevant function:** Any code that reads `pets_allowed` or `smoking_allowed` for display

  **What breaks:**

  `buildApplyURL()` in `js/cp-api.js` encodes boolean values as the strings `"true"`
  or `"false"`. The string `"false"` is truthy in JavaScript.

  ```javascript
  p.set('pets',    property.pets_allowed    ? 'true' : 'false');
  p.set('smoking', property.smoking_allowed ? 'true' : 'false');
  ```

  Any conditional in the apply form that checks `if (pets)` or `if (smoking)` will
  evaluate as `true` even for non-pet-friendly / non-smoking properties. This causes
  pet and smoking policy chips/sections to display incorrectly.

  **Exact fix:**

  Everywhere the `pets` or `smoking` URL params are consumed (in `js/script.js` in the
  Apply repo), replace:

  ```javascript
  // WRONG — "false" string is truthy:
  if (pets) { showPetSection(); }

  // CORRECT:
  if (pets === 'true') { showPetSection(); }
  ```

  In this repo (`property.html`), check if `p.pets_allowed` or `p.smoking_allowed` are
  used in any conditional for display and ensure they are compared strictly (they should
  already be native booleans from Supabase here, so this may only affect the Apply side).

  ---

  ### ISSUE-C3 — Min/max rent filter returns empty results with no explanation

  **Priority:** 🟡 Important (Phase 9B-4)
  **Status:** ✅ Resolved — April 8, 2026 (commit: `fix: Phase 9B-4 — add min/max rent swap guard before fetchAndRender query`)
  **File:** `listings.html`
  **Location:** Filter state application logic, before the Supabase query fires

  **What breaks:**

  When a user sets minimum rent higher than maximum rent (e.g. min $3,000, max $1,000),
  the Supabase query fires with contradictory range constraints and returns zero results.
  The user sees "No properties found" with no explanation. The UI gives no indication
  that the filter range is invalid.

  **Exact fix:**

  Before the query fires, add a range validation. Locate the block where `activeMinRent`
  and `activeMaxRent` are applied to the query and add a swap before it:

  ```javascript
  // Swap min/max automatically if user set them backwards:
  if (activeMinRent && activeMaxRent) {
    const min = parseFloat(activeMinRent);
    const max = parseFloat(activeMaxRent);
    if (!isNaN(min) && !isNaN(max) && min > max) {
      activeMinRent = String(max);
      activeMaxRent = String(min);
      // Update UI inputs to reflect the swap:
      const minEl = document.getElementById('advMinRent') || document.getElementById('minRentFilter');
      const maxEl = document.getElementById('advMaxRent') || document.getElementById('maxRentFilter');
      if (minEl) minEl.value = activeMinRent;
      if (maxEl) maxEl.value = activeMaxRent;
    }
  }
  ```

  Verify the exact element IDs used in `listings.html` before applying — check the DOM
  for both the simple filter and the advanced filter panel.

  ---

  ## IMPROVEMENTS — Resolved

  ### ISSUE-C4 — Application fee URL param should always be present

  **Priority:** 🟢 Improvement (Phase 9C-1)
  **Status:** ✅ Resolved — April 8, 2026 (commit: `fix: Phase 9C — 9C-1 always send fee param; 9C-2 add source param to buildApplyURL`)
  **File:** `js/cp-api.js`
  **Function:** `buildApplyURL(property)`

  **Context:**

  The fee param is currently only added if the property has an `application_fee` value:

  ```javascript
  if (property.application_fee != null) p.set('fee', property.application_fee);
  ```

  If `application_fee` is null (property saved without a fee), the `fee` param is absent
  from the URL. The GAS backend then falls back to its hardcoded `APPLICATION_FEE` constant,
  which may not match what the property owner intends to charge.

  **Fix (coordinate with 9C-1 in Apply repo):**

  Always include the fee in the URL, defaulting to 0 rather than omitting it:

  ```javascript
  // BEFORE:
  if (property.application_fee != null) p.set('fee', property.application_fee);

  // AFTER:
  p.set('fee', property.application_fee ?? 0);
  ```

  This ensures GAS always receives an explicit fee value and never needs to guess.

  ---

  ### ISSUE-C5 — Add source URL param to buildApplyURL for return link

  **Priority:** 🟢 Improvement (Phase 9C-2)
  **Status:** ✅ Resolved — April 8, 2026 (commit: `fix: Phase 9C — 9C-1 always send fee param; 9C-2 add source param to buildApplyURL`)
  **File:** `js/cp-api.js`
  **Function:** `buildApplyURL(property)`

  **What to add:**

  After the application is submitted, the success screen in the Apply form has no link
  back to the original property listing. Add the current page URL as a `source` param:

  ```javascript
  // Add before the return statement in buildApplyURL():
  try {
    p.set('source', window.location.href);
  } catch (_) {}

  return `${base}?${p.toString()}`;
  ```

  The Apply form will read this param and show a "Back to this listing" link on the
  success screen (see PHASE9_BUG_FIXES.md 9C-2 for the Apply-side implementation).

  ---

  ## Integration Architecture Reference

  This platform connects to Apply_choice_properties via `buildApplyURL()` in `js/cp-api.js`.

  **Data flow summary:**
  1. User clicks Apply on `property.html` or `listings.html`
  2. `CP.buildApplyURL(property)` builds a URL with 30+ query params
  3. Browser navigates to `https://apply-choice-properties.pages.dev?...`
  4. Apply form reads params via `_prefillFromURL()`, populates hidden inputs
  5. User fills form and submits → multipart POST to GAS exec URL
  6. GAS writes to Google Sheet, sends confirmation email
  7. On admin approval → GAS calls Supabase REST API to set property `status = 'rented'`
  8. This platform reads `status` from Supabase and hides/shows the Apply button

  **The only sync from GAS → Supabase:**
  `PATCH /rest/v1/properties?id=eq.{propertyId}` with `{ status: 'rented' }`
  This uses the Supabase service role key stored in GAS Script Properties.

  **Fields that MUST match between both systems:**
  If you add a new property field to Supabase, you need to update in FOUR places:
  1. Supabase schema (`properties` table)
  2. `buildApplyURL()` in `js/cp-api.js` (add the URL param)
  3. Hidden `<input>` in `index.html` of Apply repo (receive the param)
  4. `processApplication()` switch in `backend/code.gs` of Apply repo (write to sheet)

  ---

  *Deep scan performed: April 8, 2026*
  *Both repos scanned: choice121/Choice + choice121/Apply_choice_properties*
  