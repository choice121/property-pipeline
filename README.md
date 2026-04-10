# Property Pipeline

  A private, standalone property management tool for Choice Properties.

  ## What This Is

  This tool lets you:
  1. **Scrape** property listings from Zillow, Realtor.com, and Redfin using HomeHarvest
  2. **View** all scraped properties with photos in a private dashboard
  3. **Edit** any property field before publishing
  4. **Publish** approved listings directly to your live Choice Properties website

  Nothing touches your live website until you explicitly click Publish.

  ---

  ## How to Use This Documentation

  This project is built in **7 stages**. Each stage is small, self-contained, and fully documented.

  ### For Any AI Working on This Project

  1. Read `AI_HANDOFF.md` first — mandatory before touching any code
  2. Read `PROGRESS.md` — tells you exactly what has been done and what is next
  3. Read `STAGES.md` — master list of all stages and current status
  4. Open the relevant stage file in `stages/` and follow it precisely
  5. Update `PROGRESS.md` when you finish any work

  ### Document Structure

  ```
  property-pipeline/
  ├── README.md              # Project overview
  ├── ARCHITECTURE.md        # Full tech stack and design decisions
  ├── STAGES.md              # Master stage list with status
  ├── PROGRESS.md            # Running log of all work done (AI must update)
  ├── AI_HANDOFF.md          # Rules every AI must read before working
  └── stages/
      ├── STAGE_1.md         # Project setup & foundation
      ├── STAGE_2.md         # Scraping engine
      ├── STAGE_3.md         # Image downloading & storage
      ├── STAGE_4.md         # React frontend foundation
      ├── STAGE_5.md         # Property library UI
      ├── STAGE_6.md         # Property editor UI
      └── STAGE_7.md         # Publisher (connects to live website)
  ```

  ---

  ## Quick Start (After All Stages Complete)

  ```bash
  # Clone the repo
  git clone https://github.com/choice121/property-pipeline
  cd property-pipeline

  # Backend
  cd backend
  pip install -r requirements.txt
  cp .env.example .env
  python main.py

  # Frontend
  cd frontend
  npm install
  npm run dev
  ```

  ---

  ## Important Rules

  - **Never write to the live Supabase database** without the owner's explicit approval
  - **Stage 7 (Publisher)** requires credentials provided by the owner — do not attempt without them
  - **Always update PROGRESS.md** after completing any work
  - **Never skip a stage** — each one builds on the previous
  