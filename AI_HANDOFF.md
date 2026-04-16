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
  All credentials are stored in Replit Secrets / environment variables.
  There is no backend/.env file — never create one or commit one.
  GitHub Actions reads these same credentials from GitHub Repository Secrets.
  To sync credentials from Replit → GitHub, run:
      python3 scripts/sync-secrets-to-github.py

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

  ---

  ## Credentials & Environment Setup (Read Before Asking the Owner Anything)

  All credentials are stored in Replit as environment variables and secrets.
  DO NOT ask the owner for credentials. Read them from the environment directly.
  If a variable is missing, check Replit Secrets first, then ask.

  ### How credentials flow
  - Replit environment → app at runtime (automatic, already configured)
  - Replit environment → GitHub Actions → run:  python3 scripts/sync-secrets-to-github.py

  ### Required credentials (app will not work without these)

  | Variable | What it is | Where to find it |
  |---|---|---|
  | SUPABASE_URL | Supabase project REST URL | Replit env / Supabase dashboard |
  | SUPABASE_SERVICE_ROLE_KEY | Supabase service-role JWT | Replit Secret |
  | DEEPSEEK_API_KEY | DeepSeek AI key for all AI features | Replit Secret |
  | IMAGEKIT_PUBLIC_KEY | ImageKit public key for uploads | Replit env |
  | IMAGEKIT_PRIVATE_KEY | ImageKit private key for uploads | Replit Secret |
  | IMAGEKIT_URL_ENDPOINT | ImageKit CDN base URL | Replit env |

  ### Optional credentials (features degrade gracefully without these)

  | Variable | What it enables |
  |---|---|
  | SUPABASE_ANON_KEY | Public website reads from Supabase |
  | SUPABASE_ACCESS_TOKEN | Supabase management API access |
  | GEMINI_API_KEY | Gemini AI as fallback model |
  | GEOAPIFY_API_KEY | Map/geocoding features |
  | CLOUDFLARE_API_TOKEN | Cloudflare cache purge on publish |
  | GOOGLE_APPS_SCRIPT_URL | Email relay via Google Apps Script |
  | GOOGLE_APPS_SCRIPT_AUTH_TOKEN | Auth token for the above |
  | GITHUB_TOKEN | Used by sync script to push secrets to GitHub |

  ### Supabase project reference
  - Project ID: tlfmwetmhthpyrytrcfo
  - URL: https://tlfmwetmhthpyrytrcfo.supabase.co

  ### ImageKit reference
  - Account ID: 21rg7lvzo
  - CDN endpoint: https://ik.imagekit.io/21rg7lvzo

  ### To sync all secrets to GitHub (run once from Replit shell after any secret change)
      python3 scripts/sync-secrets-to-github.py
  