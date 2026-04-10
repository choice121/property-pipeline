import { NavLink, Outlet } from 'react-router-dom'

export default function Layout() {
  const linkClass = ({ isActive }) =>
    isActive
      ? 'font-bold text-white underline underline-offset-4'
      : 'text-gray-200 hover:text-white transition-colors'

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-gray-900 px-6 py-4 flex items-center justify-between shadow-md">
        <span className="text-white text-xl font-semibold tracking-tight">
          Property Pipeline
        </span>
        <div className="flex gap-6">
          <NavLink to="/" end className={linkClass}>
            Library
          </NavLink>
          <NavLink to="/scraper" className={linkClass}>
            Scrape
          </NavLink>
        </div>
      </nav>
      <main className="p-6">
        <Outlet />
      </main>
    </div>
  )
}
