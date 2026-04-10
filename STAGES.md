# Stages — Master List

  Each stage must be **fully complete and verified** before the next one begins.
  Any AI working on this project must update this file and PROGRESS.md after completing a stage.

  ---

  ## Status Key

  | Symbol | Meaning |
  |---|---|
  | ⬜ Not Started | Work has not begun |
  | 🔵 In Progress | Currently being worked on |
  | ✅ Complete | Done, tested, and verified |
  | 🔒 Locked | Cannot start — depends on a prior stage |

  ---

  | # | Stage Title | Status | Depends On |
  |---|---|---|---|
  | 1 | Project Setup & Foundation | ✅ Complete | None |
  | 2 | Scraping Engine | ✅ Complete | Stage 1 |
  | 3 | Image Downloading & Storage | ✅ Complete | Stage 2 |
  | 4 | React Frontend Foundation | ✅ Complete | Stage 1 |
  | 5 | Property Library UI | ✅ Complete | Stages 3 + 4 |
  | 6 | Property Editor UI | ✅ Complete | Stage 5 |
  | 7 | Publisher | 🔒 Locked | Stage 6 + Owner credentials |

  ---

  ## One-Line Summaries

  - **Stage 1** — Create the full folder structure, Python/FastAPI backend skeleton, SQLite DB, and React/Vite frontend skeleton. App starts and responds to health check.
  - **Stage 2** — Add HomeHarvest scraping. POST /api/scrape takes location + filters, runs HomeHarvest, saves normalized property records to DB.
  - **Stage 3** — After scraping, download all property images to local storage. Serve them via GET /api/images. Handle missing/broken images gracefully.
  - **Stage 4** — Build React app shell: routing, API client, nav layout, and placeholder pages for Scraper / Library / Editor.
  - **Stage 5** — Build the Library page: property grid with photos, status badges, search, filter, sort. Data is live from the API.
  - **Stage 6** — Build the Editor page: full property form with every field, image management (reorder, delete), save with edit tracking.
  - **Stage 7** — Build the Publisher: upload images to ImageKit, insert property into Supabase, mark as published. Requires owner credentials.
