# AI Handoff Guide

  Read this file completely before touching any code. It is mandatory.

  ---

  ## What This Project Is

  A private property management tool for the owner of Choice Properties (choice121/Choice on GitHub).

  It allows the owner to:
  1. Scrape property listings from Zillow, Realtor.com, and Redfin
  2. View and edit scraped properties in a private dashboard
  3. Publish approved listings to their live website

  Nothing touches the live website until Stage 7, and only with explicit owner approval.

  ---

  ## How to Orient Yourself (Do This First)

  1. Read this file completely
  2. Read PROGRESS.md — find out what is done and what is next
  3. Read STAGES.md — confirm which stage to work on
  4. Read ARCHITECTURE.md — understand the full system
  5. Open stages/STAGE_X.md for the current stage
  6. Begin work

  ---

  ## Non-Negotiable Rules

  ### Do not touch the live website before Stage 7
  Stage 7 is the only stage that connects to Supabase or ImageKit.
  No other stage should import or reference supabase or imagekitio.
  publisher_service.py must remain empty until Stage 7 is explicitly approved.

  ### One stage at a time
  Do not start the next stage until the current one is complete and marked in STAGES.md.
  Every stage depends on the previous. Do not skip.

  ### Update documentation when done
  After completing a stage, update both PROGRESS.md and STAGES.md.
  If you do not, the next AI starts blind and may duplicate or break your work.

  ### No hardcoded credentials
  All secrets go in backend/.env only.
  .env must be listed in .gitignore and never committed.
  .env.example shows which variables are needed but contains no real values.

  ### No invented features
  Build exactly what is described in the stage file.
  If something is unclear, note it in PROGRESS.md and do not guess.

  ### Preserve original scraped data
  The original_data column is written once (on scrape) and never changed.
  The edited_fields column tracks what the owner changed.

  ---

  ## PROGRESS.md Update Format

  Add this block at the TOP of Completed Work when you finish a stage:

  ### [DATE] — Stage X: [Title]
  **What was done:**
  - Specific file created or changed

  **What was NOT done (if anything):**
  - Incomplete tasks and why

  **Issues encountered:**
  - Problems found, decisions made

  **Next step:**
  - Exact first thing the next AI should do

  ---

  ## The Two Databases

  | | This Tool | Choice Properties Website |
  |---|---|---|
  | Type | SQLite (local file) | Supabase PostgreSQL (cloud) |
  | Location | backend/data/pipeline.db | Owner's Supabase project |
  | Used by | All stages | Stage 7 only |

  ---

  ## Stages at a Glance

  | Stage | Builds | Key Files |
  |---|---|---|
  | 1 | Folder structure, FastAPI, SQLite, React/Vite | main.py, models.py, db.py, App.jsx |
  | 2 | HomeHarvest scraping endpoint | scraper.py, scraper_service.py |
  | 3 | Image download and serve | image_service.py, images.py |
  | 4 | React app shell, routing, nav | Layout.jsx, client.js, page stubs |
  | 5 | Property library grid UI | Library.jsx, PropertyCard.jsx, StatusBadge.jsx |
  | 6 | Property editor UI | Editor.jsx, ImageGallery.jsx |
  | 7 | Publisher to live website | publisher_service.py, publisher.py, PublishButton.jsx |

  ---

  ## Acceptance Criteria

  Each stage file lists what must work before marking the stage complete.
  Only mark a stage complete when all criteria pass.
  If a criterion cannot be met, document the blocker in PROGRESS.md and do not mark complete.

  ---

  ## The Owner Reviews Before Stage 7

  After Stage 6 is complete, the owner reviews the tool before approving Stage 7.
  Do not prompt for credentials. Wait for the owner to initiate Stage 7.
  