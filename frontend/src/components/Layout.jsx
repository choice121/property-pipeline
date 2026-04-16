import { NavLink, Outlet } from 'react-router-dom'
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
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-4xl mx-auto">
        <div className="bg-gray-900 text-white rounded-2xl p-6 shadow-lg mb-6">
          <p className="text-sm uppercase tracking-wide text-gray-300 mb-2">Import setup</p>
          <h1 className="text-3xl font-bold mb-3">Connect Choice Properties before use</h1>
          <p className="text-gray-200">
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
                className="px-4 py-2 rounded-lg bg-gray-900 text-white text-sm font-medium disabled:opacity-50"
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
  return (
    <div className="bg-amber-50 border-b border-amber-200 px-6 py-3 text-sm text-amber-900">
      {status.summary} Missing: {[...(status.missing?.publishing || []), ...(status.missing?.optional || [])].join(', ') || 'none'}
    </div>
  )
}

export default function Layout() {
  const setup = useQuery({
    queryKey: ['setup-status'],
    queryFn: () => getSetupStatus().then((r) => r.data),
    refetchInterval: 60000,
  })

  const linkClass = ({ isActive }) =>
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
      <SetupBanner status={setup.data} />
      <main className="p-6">
        <Outlet />
      </main>
    </div>
  )
}
