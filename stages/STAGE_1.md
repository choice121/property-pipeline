# Stage 1 — Project Setup & Foundation

  ## Goal
  Create the complete folder structure for the project, a working FastAPI backend with SQLite database, and a working React + Vite frontend. No scraping yet. Just the skeleton everything else builds on.

  ## Prerequisites
  - None. This is the first stage.

  ## Acceptance Criteria
  By the end of this stage:
  - [ ] Running `python main.py` in /backend starts a server at http://localhost:8000
  - [ ] GET http://localhost:8000/api/health returns `{ "status": "ok" }`
  - [ ] The SQLite database file is created at backend/data/pipeline.db on first run
  - [ ] The properties table exists in the database (even if empty)
  - [ ] Running `npm run dev` in /frontend starts a React app at http://localhost:5173
  - [ ] The React app loads without errors and shows a placeholder home page
  - [ ] `/api/*` requests from the frontend proxy through to the backend (Vite proxy config)

  ---

  ## Task List

  ### 1.1 — Create backend folder structure
  Create these files and folders exactly:
  ```
  backend/
  ├── main.py
  ├── requirements.txt
  ├── .env.example
  ├── .gitignore
  ├── database/
  │   ├── __init__.py     (empty)
  │   ├── db.py
  │   └── models.py
  ├── routers/
  │   ├── __init__.py     (empty)
  │   ├── health.py
  │   ├── scraper.py      (stub only)
  │   ├── properties.py   (stub only)
  │   ├── images.py       (stub only)
  │   └── publisher.py    (stub only — DO NOT implement)
  ├── services/
  │   ├── __init__.py     (empty)
  │   ├── scraper_service.py    (stub only)
  │   ├── image_service.py      (stub only)
  │   └── publisher_service.py  (empty — DO NOT implement)
  └── storage/
      └── images/         (empty folder — add .gitkeep)
  ```

  ### 1.2 — Write requirements.txt
  ```
  fastapi==0.111.0
  uvicorn[standard]==0.30.1
  sqlalchemy==2.0.30
  python-dotenv==1.0.1
  httpx==0.27.0
  pillow==10.3.0
  homeharvest==0.6.0
  pydantic==2.7.1
  ```

  ### 1.3 — Write .env.example
  ```
  # Backend config
  PORT=8000

  # Stage 7 only — do not fill in until Stage 7 is approved by owner
  SUPABASE_URL=
  SUPABASE_SERVICE_ROLE_KEY=
  IMAGEKIT_PRIVATE_KEY=
  IMAGEKIT_PUBLIC_KEY=
  IMAGEKIT_URL_ENDPOINT=
  CHOICE_LANDLORD_ID=
  ```

  ### 1.4 — Write backend/.gitignore
  ```
  .env
  __pycache__/
  *.pyc
  data/
  storage/images/
  ```

  ### 1.5 — Write database/db.py
  - Create SQLAlchemy engine pointing to `backend/data/pipeline.db`
  - Create `SessionLocal` factory
  - Create `Base` declarative base
  - Create `get_db` dependency function for FastAPI
  - Create `init_db()` function that calls `Base.metadata.create_all(engine)`

  ### 1.6 — Write database/models.py
  Implement the Property SQLAlchemy model with all columns from ARCHITECTURE.md schema.
  Use `Text` type for all JSON arrays (amenities, appliances, etc.) — they are stored as JSON strings.
  Use `String` for all other text fields. Use `Float` for lat/lng and bathrooms. Use `Integer` for numeric counts.

  ### 1.7 — Write routers/health.py
  ```python
  from fastapi import APIRouter
  router = APIRouter()

  @router.get("/health")
  def health_check():
      return {"status": "ok"}
  ```

  ### 1.8 — Write stub routers
  Each stub router should just have a router instance and a single placeholder comment.
  Do NOT implement any logic in stubs — just the APIRouter() declaration.

  ### 1.9 — Write main.py
  - Import FastAPI, CORS middleware, dotenv
  - Load .env with load_dotenv()
  - Add CORSMiddleware allowing all origins (this is a private local tool)
  - Call init_db() on startup
  - Include routers: health at /api, scraper at /api, properties at /api, images at /api
  - Run with uvicorn on PORT from env (default 8000)

  ### 1.10 — Create frontend folder structure
  ```
  frontend/
  ├── index.html
  ├── package.json
  ├── vite.config.js
  ├── tailwind.config.js
  ├── postcss.config.js
  └── src/
      ├── main.jsx
      ├── App.jsx
      ├── index.css
      ├── api/
      │   └── client.js         (stub — just export axios instance)
      ├── pages/
      │   ├── Scraper.jsx       (placeholder page)
      │   ├── Library.jsx       (placeholder page)
      │   └── Editor.jsx        (placeholder page)
      └── components/
          └── Layout.jsx        (nav + outlet)
  ```

  ### 1.11 — Write package.json
  Dependencies:
  - react, react-dom, react-router-dom
  - @tanstack/react-query
  - axios
  Dev dependencies:
  - vite, @vitejs/plugin-react
  - tailwindcss, postcss, autoprefixer

  ### 1.12 — Write vite.config.js
  Configure the Vite dev server proxy:
  ```js
  server: {
    proxy: {
      '/api': 'http://localhost:8000'
    }
  }
  ```
  This is what makes /api calls from the React app reach the FastAPI backend.

  ### 1.13 — Write App.jsx
  Set up React Router with these routes:
  - / → Library page
  - /scraper → Scraper page
  - /edit/:id → Editor page
  Wrap everything in Layout component and QueryClientProvider.

  ### 1.14 — Write Layout.jsx
  Simple nav with three links: Library (/), Scrape (/scraper), and a logo/title.
  Render `<Outlet />` for the page content.

  ### 1.15 — Write placeholder pages
  Each placeholder page should just show the page title in an h1 and a brief description. No real content yet.

  ---

  ## After Completing This Stage

  1. Test all acceptance criteria manually
  2. Commit all files to the repo
  3. Update PROGRESS.md with what was done
  4. Update STAGES.md: mark Stage 1 ✅ Complete, change Stage 2 and Stage 4 from 🔒 to ⬜
  5. The next stage to work on is **Stage 2** (Scraping Engine)
  