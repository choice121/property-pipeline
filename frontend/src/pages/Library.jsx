import { useState, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate, Link } from 'react-router-dom'
import { getProperties, bulkAction, aiBulkScan, aiBulkClean } from '../api/client'
import PropertyCard from '../components/PropertyCard'
import SyncStatus from '../components/SyncStatus'
import { computeCompleteness } from '../utils/completeness'

function buildContext(p) {
  const tryArr = (v) => { try { return JSON.parse(v || '[]').join(', ') } catch { return v || '' } }
  return {
    address: p.address, city: p.city, state: p.state,
    bedrooms: p.bedrooms != null ? Number(p.bedrooms) : null,
    bathrooms: p.bathrooms != null ? Number(p.bathrooms) : null,
    square_footage: p.square_footage ? Number(p.square_footage) : null,
    year_built: p.year_built ? Number(p.year_built) : null,
    monthly_rent: p.monthly_rent ? Number(p.monthly_rent) : null,
    property_type: p.property_type,
    amenities: tryArr(p.amenities), appliances: tryArr(p.appliances),
    pets_allowed: p.pets_allowed ?? null,
    parking: p.parking, heating_type: p.heating_type, cooling_type: p.cooling_type,
    laundry_type: p.laundry_type, utilities_included: tryArr(p.utilities_included),
    description: p.description, lease_terms: tryArr(p.lease_terms),
    flooring: tryArr(p.flooring),
    has_basement: p.has_basement ?? null, has_central_air: p.has_central_air ?? null,
  }
}

export default function Library() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [sort, setSort] = useState('scraped_at')
  const [selectMode, setSelectMode] = useState(false)
  const [selectedIds, setSelectedIds] = useState(new Set())
  const [bulkResult, setBulkResult] = useState(null)

  const [scanning, setScanning] = useState(false)
  const [scanHealthMap, setScanHealthMap] = useState(null)
  const [scanError, setScanError] = useState(null)

  const [cleaning, setCleaning] = useState(false)
  const [cleanResult, setCleanResult] = useState(null)
  const [cleanError, setCleanError] = useState(null)

  const { data, isLoading } = useQuery({
    queryKey: ['properties'],
    queryFn: () => getProperties().then((r) => r.data),
    refetchInterval: (query) => {
      const props = query.state.data
      if (!props) return false
      const hasDownloading = props.some(
        (p) => p.status === 'scraped' && (!p.local_image_paths || p.local_image_paths === '[]')
      )
      return hasDownloading ? 4000 : false
    },
  })

  const bulkMutation = useMutation({
    mutationFn: ({ ids, action }) => bulkAction([...ids], action).then(r => r.data),
    onSuccess: (result) => {
      setBulkResult(result)
      setSelectedIds(new Set())
      setSelectMode(false)
      queryClient.invalidateQueries({ queryKey: ['properties'] })
      setTimeout(() => setBulkResult(null), 4000)
    },
  })

  const filtered = useMemo(() => {
    if (!data) return []
    let list = [...data]

    if (statusFilter) {
      list = list.filter((p) => p.status === statusFilter)
    }

    if (search.trim()) {
      const term = search.toLowerCase()
      list = list.filter(
        (p) =>
          (p.address || '').toLowerCase().includes(term) ||
          (p.city || '').toLowerCase().includes(term)
      )
    }

    if (sort === 'scraped_at') {
      list.sort((a, b) => new Date(b.scraped_at) - new Date(a.scraped_at))
    } else if (sort === 'price_asc') {
      list.sort((a, b) => (a.monthly_rent || 0) - (b.monthly_rent || 0))
    } else if (sort === 'price_desc') {
      list.sort((a, b) => (b.monthly_rent || 0) - (a.monthly_rent || 0))
    } else if (sort === 'bedrooms') {
      list.sort((a, b) => (b.bedrooms || 0) - (a.bedrooms || 0))
    } else if (sort === 'completeness_asc') {
      list.sort((a, b) => computeCompleteness(a).score - computeCompleteness(b).score)
    } else if (sort === 'completeness_desc') {
      list.sort((a, b) => computeCompleteness(b).score - computeCompleteness(a).score)
    }

    return list
  }, [data, search, statusFilter, sort])

  function toggleSelect(id) {
    setSelectedIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  function toggleSelectAll() {
    if (selectedIds.size === filtered.length) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(filtered.map(p => p.id)))
    }
  }

  function exitSelectMode() {
    setSelectMode(false)
    setSelectedIds(new Set())
  }

  function handleBulkAction(action) {
    if (selectedIds.size === 0) return
    const label = action === 'delete'
      ? `Delete ${selectedIds.size} propert${selectedIds.size === 1 ? 'y' : 'ies'}? This cannot be undone.`
      : `Apply "${action}" to ${selectedIds.size} propert${selectedIds.size === 1 ? 'y' : 'ies'}?`
    if (!window.confirm(label)) return
    bulkMutation.mutate({ ids: selectedIds, action })
  }

  async function handleBulkClean() {
    if (!data || data.length === 0) return
    const toClean = data.filter(p => p.description && p.description.length > 20).map(p => p.id)
    if (toClean.length === 0) return
    if (!window.confirm(`Clean descriptions for ${toClean.length} properties? AI will remove contact info, tour language, and gatekeeping text.`)) return
    setCleaning(true)
    setCleanResult(null)
    setCleanError(null)
    try {
      const res = await aiBulkClean({ property_ids: toClean })
      setCleanResult(res.data)
      queryClient.invalidateQueries({ queryKey: ['properties'] })
      setTimeout(() => setCleanResult(null), 8000)
    } catch (e) {
      setCleanError(e.response?.data?.detail || e.message || 'Bulk clean failed.')
      setTimeout(() => setCleanError(null), 6000)
    } finally {
      setCleaning(false)
    }
  }

  async function handleAiScan() {
    if (scanning || filtered.length === 0) return
    setScanning(true)
    setScanHealthMap(null)
    setScanError(null)
    try {
      const properties = filtered.map(p => ({ id: String(p.id), property: buildContext(p) }))
      const res = await aiBulkScan({ properties })
      const results = res.data.results || []
      const map = {}
      results.forEach(r => { map[r.id] = r })
      setScanHealthMap(map)
    } catch (e) {
      setScanError(e.response?.data?.detail || e.message || 'AI scan failed.')
    } finally {
      setScanning(false)
    }
  }

  const scanSummary = useMemo(() => {
    if (!scanHealthMap) return null
    let errors = 0, warnings = 0, clean = 0
    Object.values(scanHealthMap).forEach(r => {
      if (r.errors > 0) errors++
      else if (r.warnings > 0) warnings++
      else clean++
    })
    return { errors, warnings, clean, total: Object.keys(scanHealthMap).length }
  }, [scanHealthMap])

  return (
    <div>
      <div className="flex items-center justify-between mb-3 gap-2">
        <h1 className="text-xl sm:text-2xl font-bold text-gray-900 truncate">
          Library
          <span className="ml-2 text-sm sm:text-base font-normal text-gray-500">
            ({filtered.length})
          </span>
        </h1>
        <div className="flex items-center gap-2 flex-shrink-0">
          {/* Clean All */}
          <button
            onClick={handleBulkClean}
            disabled={cleaning || !data || data.length === 0}
            title="Clean all descriptions with AI"
            className="flex items-center gap-1.5 text-sm px-2.5 sm:px-3 py-2 rounded-lg border border-emerald-300 bg-emerald-50 text-emerald-700 hover:bg-emerald-100 disabled:opacity-50 transition-colors touch-target"
          >
            <svg className={`w-4 h-4 flex-shrink-0 ${cleaning ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              {cleaning
                ? <><circle className="opacity-25" cx="12" cy="12" r="10" strokeWidth="4"/><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/></>
                : <path strokeLinecap="round" strokeLinejoin="round" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
              }
            </svg>
            <span className="hidden sm:inline">{cleaning ? 'Cleaning…' : 'Clean All'}</span>
            <span className="sm:hidden">{cleaning ? '…' : 'Clean'}</span>
          </button>

          {/* AI Scan — icon-only on mobile, full label on desktop */}
          <button
            onClick={handleAiScan}
            disabled={scanning || filtered.length === 0}
            title={`AI Scan (${filtered.length})`}
            className="flex items-center gap-1.5 text-sm px-2.5 sm:px-3 py-2 rounded-lg border border-purple-300 bg-purple-50 text-purple-700 hover:bg-purple-100 disabled:opacity-50 transition-colors touch-target"
          >
            <svg className={`w-4 h-4 flex-shrink-0 ${scanning ? 'animate-spin' : ''}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              {scanning
                ? <><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" /></>
                : <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
              }
            </svg>
            <span className="hidden sm:inline">{scanning ? 'Scanning…' : `AI Scan (${filtered.length})`}</span>
            <span className="sm:hidden">{scanning ? '…' : 'Scan'}</span>
          </button>

          {/* Select */}
          <button
            onClick={() => { setSelectMode(!selectMode); setSelectedIds(new Set()) }}
            className={`text-sm px-2.5 sm:px-3 py-2 rounded-lg border transition-colors touch-target ${selectMode ? 'bg-gray-900 text-white border-gray-900' : 'border-gray-300 text-gray-600 hover:bg-gray-50'}`}
          >
            {selectMode ? 'Cancel' : 'Select'}
          </button>

          {/* + Create and + Scrape — desktop only; bottom tab bar handles mobile */}
          <Link
            to="/create"
            className="hidden sm:block border border-gray-300 text-gray-700 px-4 py-2 rounded-lg text-sm font-medium hover:bg-gray-50 transition-colors"
          >
            + Create
          </Link>
          <Link
            to="/scraper"
            className="hidden sm:block bg-gray-900 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-gray-700 transition-colors"
          >
            + Scrape
          </Link>
        </div>
      </div>

      <div className="flex items-center justify-between mb-4">
        <SyncStatus />
      </div>

      {/* Clean results banners */}
      {cleanError && (
        <div className="mb-4 px-4 py-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700 flex items-center justify-between">
          <span>Clean failed: {cleanError}</span>
          <button onClick={() => setCleanError(null)} className="text-red-400 hover:text-red-600 ml-3 text-lg leading-none">&times;</button>
        </div>
      )}
      {cleanResult && (
        <div className="mb-4 px-4 py-3 bg-emerald-50 border border-emerald-200 rounded-lg">
          <div className="flex items-center justify-between">
            <span className="text-sm font-semibold text-emerald-900">
              Bulk Clean Complete — {cleanResult.cleaned} descriptions updated
            </span>
            <button onClick={() => setCleanResult(null)} className="text-emerald-400 hover:text-emerald-600 text-lg leading-none">&times;</button>
          </div>
          <div className="flex gap-4 mt-1">
            <span className="text-sm text-gray-600"><strong>{cleanResult.skipped}</strong> already clean</span>
            {cleanResult.errors > 0 && <span className="text-sm text-red-600"><strong>{cleanResult.errors}</strong> errors</span>}
          </div>
        </div>
      )}

      {/* AI Scan results banner */}
      {scanError && (
        <div className="mb-4 px-4 py-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700 flex items-center justify-between">
          <span>AI scan failed: {scanError}</span>
          <button onClick={() => setScanError(null)} className="text-red-400 hover:text-red-600 ml-3 text-lg leading-none">&times;</button>
        </div>
      )}

      {scanSummary && (
        <div className="mb-4 px-4 py-3 bg-purple-50 border border-purple-200 rounded-lg">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5">
              <svg className="w-4 h-4 text-purple-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
              </svg>
              <span className="text-sm font-semibold text-purple-900">AI Scan Complete — {scanSummary.total} listings reviewed</span>
            </div>
            <button onClick={() => setScanHealthMap(null)} className="text-purple-400 hover:text-purple-600 text-lg leading-none">&times;</button>
          </div>
          <div className="flex gap-4 mt-2">
            {scanSummary.errors > 0 && (
              <span className="flex items-center gap-1.5 text-sm text-red-700">
                <span className="w-2.5 h-2.5 rounded-full bg-red-500 inline-block" />
                <strong>{scanSummary.errors}</strong> need fixes
              </span>
            )}
            {scanSummary.warnings > 0 && (
              <span className="flex items-center gap-1.5 text-sm text-amber-700">
                <span className="w-2.5 h-2.5 rounded-full bg-amber-400 inline-block" />
                <strong>{scanSummary.warnings}</strong> have warnings
              </span>
            )}
            {scanSummary.clean > 0 && (
              <span className="flex items-center gap-1.5 text-sm text-green-700">
                <span className="w-2.5 h-2.5 rounded-full bg-green-500 inline-block" />
                <strong>{scanSummary.clean}</strong> look good
              </span>
            )}
          </div>
        </div>
      )}

      {/* Bulk action bar */}
      {selectMode && (
        <div className="mb-4 flex flex-wrap items-center gap-3 bg-gray-900 text-white px-4 py-3 rounded-lg">
          <button
            onClick={toggleSelectAll}
            className="text-sm text-gray-300 hover:text-white underline"
          >
            {selectedIds.size === filtered.length ? 'Deselect All' : `Select All (${filtered.length})`}
          </button>
          <span className="text-gray-400 text-sm">{selectedIds.size} selected</span>
          <div className="flex gap-2 ml-auto flex-wrap">
            <button
              onClick={() => handleBulkAction('ready')}
              disabled={selectedIds.size === 0 || bulkMutation.isPending}
              className="text-xs bg-amber-500 hover:bg-amber-400 text-white px-3 py-1.5 rounded-md font-medium disabled:opacity-40 transition-colors"
            >
              Mark Ready
            </button>
            <button
              onClick={() => handleBulkAction('sync')}
              disabled={selectedIds.size === 0 || bulkMutation.isPending}
              title="Sync field changes to the live site for all selected published listings"
              className="text-xs bg-blue-600 hover:bg-blue-500 text-white px-3 py-1.5 rounded-md font-medium disabled:opacity-40 transition-colors"
            >
              Sync to Live
            </button>
            <button
              onClick={() => handleBulkAction('archive')}
              disabled={selectedIds.size === 0 || bulkMutation.isPending}
              className="text-xs bg-gray-600 hover:bg-gray-500 text-white px-3 py-1.5 rounded-md font-medium disabled:opacity-40 transition-colors"
            >
              Archive
            </button>
            <button
              onClick={() => handleBulkAction('delete')}
              disabled={selectedIds.size === 0 || bulkMutation.isPending}
              className="text-xs bg-red-600 hover:bg-red-500 text-white px-3 py-1.5 rounded-md font-medium disabled:opacity-40 transition-colors"
            >
              Delete
            </button>
          </div>
        </div>
      )}

      {/* Bulk action result */}
      {bulkResult && (
        <div className={`mb-4 px-4 py-2 rounded-lg text-sm ${bulkResult.failed > 0 ? 'bg-amber-50 text-amber-800 border border-amber-200' : 'bg-green-50 text-green-800 border border-green-200'}`}>
          {bulkResult.success} succeeded{bulkResult.failed > 0 ? `, ${bulkResult.failed} failed` : ''}
        </div>
      )}

      <div className="flex flex-col sm:flex-row gap-2 sm:gap-3 mb-6">
        <input
          type="text"
          placeholder="Search by address or city..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-2.5 sm:py-2 flex-1 focus:outline-none focus:ring-2 focus:ring-gray-400"
        />
        <div className="flex gap-2">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-2.5 sm:py-2 flex-1 sm:flex-none focus:outline-none focus:ring-2 focus:ring-gray-400 bg-white"
          >
            <option value="">All Statuses</option>
            <option value="draft">Draft</option>
            <option value="scraped">Scraped</option>
            <option value="edited">Edited</option>
            <option value="ready">Ready</option>
            <option value="published">Published</option>
            <option value="rented">Rented</option>
            <option value="archived">Archived</option>
          </select>
          <select
            value={sort}
            onChange={(e) => setSort(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-2.5 sm:py-2 flex-1 sm:flex-none focus:outline-none focus:ring-2 focus:ring-gray-400 bg-white"
          >
            <option value="scraped_at">Newest First</option>
            <option value="price_asc">Price ↑</option>
            <option value="price_desc">Price ↓</option>
            <option value="bedrooms">Bedrooms</option>
            <option value="completeness_asc">Needs Attention</option>
            <option value="completeness_desc">Most Complete</option>
          </select>
        </div>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="bg-gray-200 rounded-lg h-64 animate-pulse" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-16 text-gray-400">
          <p className="text-lg">No properties found.</p>
          <p className="text-sm mt-2">
            Try adjusting your filters or{' '}
            <Link to="/scraper" className="text-gray-700 underline">
              scrape new listings
            </Link>
            .
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map((property) => (
            <PropertyCard
              key={property.id}
              property={property}
              onClick={() => !selectMode && navigate(`/edit/${property.id}`)}
              selectable={selectMode}
              selected={selectedIds.has(property.id)}
              onSelect={() => toggleSelect(property.id)}
              aiHealth={scanHealthMap ? (scanHealthMap[String(property.id)] || null) : null}
            />
          ))}
        </div>
      )}
    </div>
  )
}
