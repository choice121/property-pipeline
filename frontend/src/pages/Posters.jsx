import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'

function api() {
  return {
    list:        ()   => axios.get('/api/posters').then(r => r.data),
    getById:     (id) => axios.get(`/api/posters/${id}`).then(r => r.data),
    recalculate: ()   => axios.post('/api/posters/recalculate').then(r => r.data),
    clearCache:  ()   => axios.delete('/api/posters/cache').then(r => r.data),
  }
}

function Avatar({ url, name, size = 'md' }) {
  const [broken, setBroken] = useState(false)
  const sz = size === 'lg' ? 'w-16 h-16 text-xl' : 'w-10 h-10 text-sm'
  const initials = (name || '?').split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase()

  if (url && !broken) {
    return (
      <img
        src={url}
        alt={name}
        onError={() => setBroken(true)}
        className={`${sz} rounded-full object-cover flex-none bg-gray-100`}
      />
    )
  }
  return (
    <div className={`${sz} rounded-full bg-indigo-100 text-indigo-700 font-bold flex items-center justify-center flex-none`}>
      {initials}
    </div>
  )
}

function StatusBadge({ status }) {
  const map = {
    published: 'bg-green-100 text-green-800',
    scraped:   'bg-gray-100 text-gray-700',
    enriched:  'bg-blue-100 text-blue-800',
    rejected:  'bg-red-100 text-red-700',
  }
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${map[status] || 'bg-gray-100 text-gray-600'}`}>
      {status}
    </span>
  )
}

function PropertyDrawer({ landlordId, onClose }) {
  const { data: poster, isLoading, error } = useQuery({
    queryKey: ['poster', landlordId],
    queryFn: () => api().getById(landlordId),
    enabled: !!landlordId,
  })

  return (
    <div className="fixed inset-0 z-50 flex justify-end" onClick={onClose}>
      <div
        className="w-full max-w-md bg-white shadow-2xl flex flex-col h-full overflow-hidden"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
          <h2 className="font-semibold text-gray-900">Poster Detail</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700 text-2xl leading-none">&times;</button>
        </div>

        {isLoading && (
          <div className="flex-1 flex items-center justify-center text-gray-400 text-sm">Loading…</div>
        )}
        {error && (
          <div className="p-5 text-red-600 text-sm">Failed to load poster details.</div>
        )}

        {poster && (
          <div className="flex-1 overflow-y-auto">
            <div className="px-5 py-4 border-b border-gray-50 flex gap-4 items-center">
              <Avatar url={poster.avatar_url} name={poster.contact_name} size="lg" />
              <div>
                <div className="font-semibold text-gray-900 text-lg">
                  {poster.contact_name || poster.business_name || 'Unknown'}
                </div>
                {poster.business_name && poster.contact_name && (
                  <div className="text-sm text-gray-500">{poster.business_name}</div>
                )}
                {poster.email && (
                  <div className="text-xs text-gray-400 mt-0.5">{poster.email}</div>
                )}
              </div>
            </div>

            <div className="px-5 py-3 border-b border-gray-50">
              <div className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">Details</div>
              <div className="grid grid-cols-2 gap-2 text-sm">
                {poster.phone && <div><span className="text-gray-400">Phone</span><br /><span className="text-gray-800">{poster.phone}</span></div>}
                {poster.license_number && <div><span className="text-gray-400">License</span><br /><span className="text-gray-800">{poster.license_number}</span></div>}
                {poster.license_state && <div><span className="text-gray-400">State</span><br /><span className="text-gray-800">{poster.license_state}</span></div>}
                {poster.years_experience && <div><span className="text-gray-400">Experience</span><br /><span className="text-gray-800">{poster.years_experience} yrs</span></div>}
                <div><span className="text-gray-400">Plan</span><br /><span className="text-gray-800 capitalize">{poster.plan || 'free'}</span></div>
                <div><span className="text-gray-400">Verified</span><br /><span className={poster.verified ? 'text-green-700' : 'text-gray-400'}>{poster.verified ? 'Yes' : 'No'}</span></div>
              </div>
            </div>

            <div className="px-5 py-3">
              <div className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">
                Properties ({(poster.properties || []).length})
              </div>
              {(!poster.properties || poster.properties.length === 0) && (
                <div className="text-sm text-gray-400">No pipeline properties linked.</div>
              )}
              <div className="space-y-2">
                {(poster.properties || []).map(p => (
                  <div key={p.id} className="flex items-center justify-between gap-2 bg-gray-50 rounded-lg px-3 py-2">
                    <div className="min-w-0">
                      <div className="text-sm font-medium text-gray-800 truncate">{p.title || p.address || p.id}</div>
                      <div className="text-xs text-gray-400">{[p.city, p.state].filter(Boolean).join(', ')}</div>
                    </div>
                    <div className="flex items-center gap-2 flex-none">
                      <StatusBadge status={p.status} />
                      {p.data_quality_score != null && (
                        <span className="text-xs text-gray-400">{Math.round(p.data_quality_score)}%</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default function Posters() {
  const qc = useQueryClient()
  const [selectedId, setSelectedId] = useState(null)
  const [search, setSearch] = useState('')

  const { data: posters = [], isLoading, error, refetch } = useQuery({
    queryKey: ['posters'],
    queryFn: api().list,
  })

  const recalc = useMutation({
    mutationFn: api().recalculate,
    onSuccess: () => {
      setTimeout(() => {
        qc.invalidateQueries({ queryKey: ['posters'] })
      }, 2000)
    },
  })

  const clearCache = useMutation({
    mutationFn: api().clearCache,
    onSuccess: () => refetch(),
  })

  const filtered = posters.filter(p => {
    if (!search) return true
    const q = search.toLowerCase()
    return (
      (p.contact_name || '').toLowerCase().includes(q) ||
      (p.business_name || '').toLowerCase().includes(q) ||
      (p.email || '').toLowerCase().includes(q)
    )
  })

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-5">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Poster Attribution</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Landlord profiles linked to scraped agent and broker names.
          </p>
        </div>
        <div className="flex gap-2 flex-none">
          <button
            onClick={() => clearCache.mutate()}
            disabled={clearCache.isPending}
            className="px-3 py-2 text-sm rounded-lg border border-gray-200 text-gray-600 hover:bg-gray-50 disabled:opacity-50"
          >
            Clear Cache
          </button>
          <button
            onClick={() => recalc.mutate()}
            disabled={recalc.isPending}
            className="px-4 py-2 text-sm rounded-lg bg-gray-900 text-white font-medium hover:bg-gray-700 disabled:opacity-50"
          >
            {recalc.isPending ? 'Recalculating…' : 'Recalculate All'}
          </button>
        </div>
      </div>

      {recalc.isSuccess && (
        <div className="mb-4 px-4 py-2 bg-green-50 border border-green-200 rounded-lg text-sm text-green-800">
          Recalculation started — refreshing in a moment.
        </div>
      )}

      {recalc.isError && (
        <div className="mb-4 px-4 py-2 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          Recalculation failed: {recalc.error?.message}
        </div>
      )}

      <div className="mb-4">
        <input
          type="text"
          placeholder="Search by name or email…"
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="w-full sm:w-72 px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-gray-300"
        />
      </div>

      {isLoading && (
        <div className="text-center py-16 text-gray-400 text-sm">Loading posters…</div>
      )}

      {error && (
        <div className="text-center py-16 text-red-500 text-sm">
          Failed to load posters. {error.message}
        </div>
      )}

      {!isLoading && !error && filtered.length === 0 && (
        <div className="text-center py-16 text-gray-400 text-sm">
          {search ? 'No posters match your search.' : 'No poster profiles yet. Run Recalculate All to generate them from scraped agent/broker names.'}
        </div>
      )}

      <div className="grid gap-3 sm:grid-cols-2">
        {filtered.map(poster => (
          <button
            key={poster.id}
            onClick={() => setSelectedId(poster.id)}
            className="flex items-center gap-3 bg-white border border-gray-200 rounded-xl px-4 py-3 hover:border-gray-400 hover:shadow-sm transition-all text-left w-full"
          >
            <Avatar url={poster.avatar_url} name={poster.contact_name || poster.business_name} />
            <div className="min-w-0 flex-1">
              <div className="font-medium text-gray-900 truncate">
                {poster.contact_name || poster.business_name || 'Unknown'}
              </div>
              {poster.business_name && poster.contact_name && (
                <div className="text-xs text-gray-400 truncate">{poster.business_name}</div>
              )}
            </div>
            <div className="flex-none text-right">
              <div className="text-sm font-semibold text-gray-900">{poster.property_count ?? 0}</div>
              <div className="text-xs text-gray-400">listings</div>
            </div>
          </button>
        ))}
      </div>

      {selectedId && (
        <PropertyDrawer landlordId={selectedId} onClose={() => setSelectedId(null)} />
      )}
    </div>
  )
}
