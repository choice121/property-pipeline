import { NavLink, Outlet, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getSetupStatus } from '../api/client'

function RequirementList({ title, items }) {
  return (
    <div className="bg-white border border-gray-200 rounded-xl p-4">
      <h3 className="font-semibold text-gray-900 mb-3">{title}</h3>
      <div className="space-y-3">
        {items.map((item) => (
          <div key={item.key} className="flex gap-3">
            <span className={`mt-1 w-2.5 h-2.5 rounded-full flex-none ${item.present ? 'bg-green-500' : 'bg-amber-500'}`} />
            <div>
              <div className="font-mono text-sm text-gray-900">{item.key}</div>
              <div className="text-sm text-gray-500">{item.description}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function SetupScreen({ status, error, refetch, isFetching }) {
  const groups = status?.groups
  return (
    <div className="min-h-screen bg-gray-50 p-4 sm:p-6">
      <div className="max-w-4xl mx-auto">
        <div className="bg-gray-900 text-white rounded-2xl p-5 sm:p-6 shadow-lg mb-6">
          <p className="text-sm uppercase tracking-wide text-gray-300 mb-2">Import setup</p>
          <h1 className="text-2xl sm:text-3xl font-bold mb-3">Connect Choice Properties before use</h1>
          <p className="text-gray-200 text-sm sm:text-base">
            This project starts safely in every Replit account, then verifies the live website database before syncing. Add the required secrets in your Replit secrets panel, restart the app, and this screen will confirm when it is ready.
          </p>
        </div>

        {error ? (
          <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-red-700 mb-6">
            Setup check failed: {error.message}
          </div>
        ) : (
          <div className="bg-white border border-gray-200 rounded-xl p-4 mb-6">
            <div className="flex items-center justify-between gap-4">
              <div>
                <div className="font-semibold text-gray-900">{status?.summary || 'Checking setup...'}</div>
                {status?.services?.supabase && (
                  <div className="text-sm text-gray-500 mt-1">{status.services.supabase.message}</div>
                )}
              </div>
              <button
                onClick={() => refetch()}
                disabled={isFetching}
                className="px-4 py-2 rounded-lg bg-gray-900 text-white text-sm font-medium disabled:opacity-50 touch-target"
              >
                {isFetching ? 'Checking...' : 'Recheck'}
              </button>
            </div>
          </div>
        )}

        {groups && (
          <div className="grid md:grid-cols-2 gap-4">
            <RequirementList title="Required to open and sync" items={groups.core} />
            <RequirementList title="Required for publishing" items={groups.publishing} />
            <RequirementList title="Optional enhancements" items={groups.optional} />
          </div>
        )}
      </div>
    </div>
  )
}

function SetupBanner({ status }) {
  if (!status || status.fully_configured) return null
  const publishingMissing = status.missing?.publishing || []
  const missingText = publishingMissing.length ? ` Missing for publishing: ${publishingMissing.join(', ')}` : ''
  return (
    <div className="bg-amber-50 border-b border-amber-200 px-4 py-2 text-xs sm:text-sm text-amber-900">
      {status.summary}{missingText}
    </div>
  )
}

/* ── Icon components for bottom tab bar ─────────────────────────────────── */
function IconLibrary({ active }) {
  return (
    <svg className={`w-5 h-5 mb-0.5 ${active ? 'text-gray-900' : 'text-gray-400'}`} fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
      <rect x="3" y="3" width="7" height="7" rx="1" />
      <rect x="14" y="3" width="7" height="7" rx="1" />
      <rect x="3" y="14" width="7" height="7" rx="1" />
      <rect x="14" y="14" width="7" height="7" rx="1" />
    </svg>
  )
}
function IconScrape({ active }) {
  return (
    <svg className={`w-5 h-5 mb-0.5 ${active ? 'text-gray-900' : 'text-gray-400'}`} fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
      <circle cx="11" cy="11" r="8" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-4.35-4.35" />
    </svg>
  )
}
function IconCreate({ active }) {
  return (
    <svg className={`w-5 h-5 mb-0.5 ${active ? 'text-gray-900' : 'text-gray-400'}`} fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
      <circle cx="12" cy="12" r="10" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v8M8 12h8" />
    </svg>
  )
}
function IconAudit({ active }) {
  return (
    <svg className={`w-5 h-5 mb-0.5 ${active ? 'text-gray-900' : 'text-gray-400'}`} fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
    </svg>
  )
}
function IconPosters({ active }) {
  return (
    <svg className={`w-5 h-5 mb-0.5 ${active ? 'text-gray-900' : 'text-gray-400'}`} fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
      <circle cx="12" cy="8" r="4" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M4 20c0-4 3.582-7 8-7s8 3 8 7" />
    </svg>
  )
}

export default function Layout() {
  const setup = useQuery({
    queryKey: ['setup-status'],
    queryFn: () => getSetupStatus().then((r) => r.data),
    refetchInterval: 60000,
  })

  const desktopLink = ({ isActive }) =>
    isActive
      ? 'font-bold text-white underline underline-offset-4'
      : 'text-gray-200 hover:text-white transition-colors'

  if (setup.isLoading || setup.error || (setup.data && !setup.data.core_ready)) {
    return (
      <SetupScreen
        status={setup.data}
        error={setup.error}
        refetch={setup.refetch}
        isFetching={setup.isFetching}
      />
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">

      {/* ── Top nav (visible on all sizes, links hidden on mobile) ── */}
      <nav className="bg-gray-900 px-4 sm:px-6 py-3 sm:py-4 flex items-center justify-between shadow-md sticky top-0 z-40">
        <span className="text-white text-lg sm:text-xl font-semibold tracking-tight">
          Property Pipeline
        </span>
        {/* Desktop nav links — hidden on mobile (bottom bar handles it) */}
        <div className="hidden sm:flex gap-6">
          <NavLink to="/" end className={desktopLink}>Library</NavLink>
          <NavLink to="/scraper" className={desktopLink}>Scrape</NavLink>
          <NavLink to="/audit" className={desktopLink}>Audit</NavLink>
          <NavLink to="/posters" className={desktopLink}>Posters</NavLink>
          <NavLink to="/create" className={desktopLink}>+ Create</NavLink>
        </div>
      </nav>

      <SetupBanner status={setup.data} />

      {/* Main content — extra bottom padding on mobile for the tab bar */}
      <main className="px-3 py-4 sm:p-6 pb-24 sm:pb-6">
        <Outlet />
      </main>

      {/* ── Mobile bottom tab bar (hidden on sm+) ─────────────────── */}
      <nav
        className="sm:hidden fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 flex z-50 pb-safe"
        style={{ paddingBottom: 'max(env(safe-area-inset-bottom, 0px), 4px)' }}
      >
        <NavLink
          to="/"
          end
          className={({ isActive }) =>
            `flex-1 flex flex-col items-center justify-center py-2 text-xs font-medium transition-colors ${isActive ? 'text-gray-900' : 'text-gray-400'}`
          }
        >
          {({ isActive }) => (<><IconLibrary active={isActive} />Library</>)}
        </NavLink>

        <NavLink
          to="/scraper"
          className={({ isActive }) =>
            `flex-1 flex flex-col items-center justify-center py-2 text-xs font-medium transition-colors ${isActive ? 'text-gray-900' : 'text-gray-400'}`
          }
        >
          {({ isActive }) => (<><IconScrape active={isActive} />Scrape</>)}
        </NavLink>

        <NavLink
          to="/create"
          className={({ isActive }) =>
            `flex-1 flex flex-col items-center justify-center py-2 text-xs font-medium transition-colors ${isActive ? 'text-gray-900' : 'text-gray-400'}`
          }
        >
          {({ isActive }) => (<><IconCreate active={isActive} />Create</>)}
        </NavLink>

        <NavLink
          to="/audit"
          className={({ isActive }) =>
            `flex-1 flex flex-col items-center justify-center py-2 text-xs font-medium transition-colors ${isActive ? 'text-gray-900' : 'text-gray-400'}`
          }
        >
          {({ isActive }) => (<><IconAudit active={isActive} />Audit</>)}
        </NavLink>

        <NavLink
          to="/posters"
          className={({ isActive }) =>
            `flex-1 flex flex-col items-center justify-center py-2 text-xs font-medium transition-colors ${isActive ? 'text-gray-900' : 'text-gray-400'}`
          }
        >
          {({ isActive }) => (<><IconPosters active={isActive} />Posters</>)}
        </NavLink>
      </nav>
    </div>
  )
}
