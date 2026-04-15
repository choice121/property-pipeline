import { useState, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate, Link } from 'react-router-dom'
import { getProperties, bulkAction } from '../api/client'
import PropertyCard from '../components/PropertyCard'

export default function Library() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [sort, setSort] = useState('scraped_at')
  const [selectMode, setSelectMode] = useState(false)
  const [selectedIds, setSelectedIds] = useState(new Set())
  const [bulkResult, setBulkResult] = useState(null)

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

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">
          Property Library
          <span className="ml-2 text-base font-normal text-gray-500">
            ({filtered.length} {filtered.length === 1 ? 'property' : 'properties'})
          </span>
        </h1>
        <div className="flex items-center gap-2">
          <button
            onClick={() => { setSelectMode(!selectMode); setSelectedIds(new Set()) }}
            className={`text-sm px-3 py-2 rounded-lg border transition-colors ${selectMode ? 'bg-gray-900 text-white border-gray-900' : 'border-gray-300 text-gray-600 hover:bg-gray-50'}`}
          >
            {selectMode ? 'Cancel' : 'Select'}
          </button>
          <Link
            to="/scraper"
            className="bg-gray-900 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-gray-700 transition-colors"
          >
            + Scrape More
          </Link>
        </div>
      </div>

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
          <div className="flex gap-2 ml-auto">
            <button
              onClick={() => handleBulkAction('ready')}
              disabled={selectedIds.size === 0 || bulkMutation.isPending}
              className="text-xs bg-amber-500 hover:bg-amber-400 text-white px-3 py-1.5 rounded-md font-medium disabled:opacity-40 transition-colors"
            >
              Mark Ready
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

      <div className="flex flex-wrap gap-3 mb-6">
        <input
          type="text"
          placeholder="Search by address or city..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm flex-1 min-w-48 focus:outline-none focus:ring-2 focus:ring-gray-400"
        />
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gray-400"
        >
          <option value="">All Statuses</option>
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
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gray-400"
        >
          <option value="scraped_at">Newest First</option>
          <option value="price_asc">Price: Low to High</option>
          <option value="price_desc">Price: High to Low</option>
          <option value="bedrooms">Most Bedrooms</option>
        </select>
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
            />
          ))}
        </div>
      )}
    </div>
  )
}
