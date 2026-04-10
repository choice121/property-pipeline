# Stage 4 — React Frontend Foundation

  ## Goal
  Set up the React and Vite frontend with routing, an API client, app navigation, and empty placeholder pages. This is the shell that all future UI stages fill in.

  ## Prerequisites
  - Stage 1 must be complete (folder structure and package.json already exist)
  - Runs in parallel with Stage 3 — does not need Stage 3

  ## Acceptance Criteria
  - [ ] npm install in /frontend completes without errors
  - [ ] npm run dev starts dev server at http://localhost:5173
  - [ ] App loads with navigation bar showing Library and Scrape links
  - [ ] / shows Library page placeholder
  - [ ] /scraper shows Scraper page placeholder
  - [ ] /api/* requests proxy correctly to backend at http://localhost:8000
  - [ ] No console errors on load

  ---

  ## Task List

  ### 4.1 — Install dependencies
  Run in /frontend:
  ```bash
  npm install react react-dom react-router-dom @tanstack/react-query axios
  npm install -D vite @vitejs/plugin-react tailwindcss postcss autoprefixer
  npx tailwindcss init -p
  ```

  ### 4.2 — Configure Tailwind
  tailwind.config.js content:
  ```js
  content: ["./index.html", "./src/**/*.{js,jsx}"]
  ```
  src/index.css:
  ```css
  @tailwind base;
  @tailwind components;
  @tailwind utilities;
  ```

  ### 4.3 — Write vite.config.js
  ```js
  import { defineConfig } from 'vite'
  import react from '@vitejs/plugin-react'
  export default defineConfig({
    plugins: [react()],
    server: {
      port: 5173,
      proxy: { '/api': 'http://localhost:8000' }
    }
  })
  ```

  ### 4.4 — Write src/api/client.js
  ```js
  import axios from 'axios'
  const api = axios.create({ baseURL: '/api' })
  export const scrapeProperties = (data) => api.post('/scrape', data)
  export const getProperties = (params) => api.get('/properties', { params })
  export const getProperty = (id) => api.get('/properties/' + id)
  export const updateProperty = (id, data) => api.put('/properties/' + id, data)
  export const deleteProperty = (id) => api.delete('/properties/' + id)
  export const deleteImage = (id, index) => api.delete('/properties/' + id + '/images/' + index)
  export const reorderImages = (id, order) => api.put('/properties/' + id + '/images/reorder', { order })
  export const publishProperty = (id) => api.post('/publish/' + id)
  export default api
  ```

  ### 4.5 — Write src/main.jsx
  Wrap app in QueryClientProvider with a new QueryClient. Render App into root div.

  ### 4.6 — Write src/App.jsx
  Use createBrowserRouter. Routes:
  - / -> Library
  - /scraper -> Scraper
  - /edit/:id -> Editor
  All wrapped in Layout component.

  ### 4.7 — Write src/components/Layout.jsx
  - Top nav: app name "Property Pipeline" on left, nav links Library and Scrape on right
  - Active link visually distinct (bold or underlined)
  - Render Outlet below nav
  - Use Tailwind for all styling

  ### 4.8 — Write placeholder pages
  Library.jsx, Scraper.jsx, and Editor.jsx each show a title h1 and one line description.
  No real data or API calls yet.

  ### 4.9 — Write index.html
  Standard Vite HTML with div#root and script src="/src/main.jsx" with type="module".

  ---

  ## After This Stage

  1. npm run dev and visit all pages
  2. Confirm no console errors
  3. Commit all files
  4. Update PROGRESS.md
  5. Update STAGES.md: Stage 4 complete
  6. If Stage 3 is also complete, Stage 5 is now unlocked
  7. Next: Stage 5 — Property Library UI (needs both Stage 3 and Stage 4)
  