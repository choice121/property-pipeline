function fmt(price) {
  if (price == null) return null
  return '$' + Number(price).toLocaleString()
}

export default function ResultsFilterBar({
  results,
  filters,
  onFiltersChange,
  sort,
  onSortChange,
  viewMode,
  onViewModeChange,
}) {
  const prices = results.map((r) => r.monthly_rent).filter((p) => p != null)
  const minPrice = prices.length ? Math.min(...prices) : null
  const maxPrice = prices.length ? Math.max(...prices) : null
  const withPhotos = results.filter((r) => r.image_urls?.length > 0).length
  const alreadySaved = results.filter((r) => r._alreadyInLibrary).length

  function change(key, val) {
    onFiltersChange({ ...filters, [key]: val })
  }

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-4 mb-4 space-y-3">

      {/* Stats row */}
      <div className="flex flex-wrap gap-x-5 gap-y-1 text-sm text-gray-500">
        <span>
          <span className="font-semibold text-gray-800">{results.length}</span> properties
        </span>
        {minPrice != null && (
          <span>
            <span className="font-semibold text-gray-800">{fmt(minPrice)} – {fmt(maxPrice)}/mo</span> price range
          </span>
        )}
        {withPhotos > 0 && (
          <span>
            <span className="font-semibold text-gray-800">{withPhotos}</span> with photos
          </span>
        )}
        {alreadySaved > 0 && (
          <span className="text-amber-600">
            <span className="font-semibold">{alreadySaved}</span> already in your library
          </span>
        )}
      </div>

      {/* Controls row */}
      <div className="flex flex-wrap gap-2 items-center">

        {/* Sort */}
        <select
          value={sort}
          onChange={(e) => onSortChange(e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-gray-400 bg-white"
        >
          <option value="default">Sort: Default</option>
          <option value="price_asc">Price: Low → High</option>
          <option value="price_desc">Price: High → Low</option>
          <option value="beds_desc">Most Bedrooms</option>
          <option value="sqft_desc">Largest First</option>
          <option value="date_asc">Oldest Listed</option>
          <option value="date_desc">Newest Listed</option>
        </select>

        {/* Min beds filter */}
        <select
          value={filters.minBeds ?? ''}
          onChange={(e) => change('minBeds', e.target.value ? parseInt(e.target.value) : null)}
          className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-gray-400 bg-white"
        >
          <option value="">Any beds</option>
          <option value="1">1+ bed</option>
          <option value="2">2+ beds</option>
          <option value="3">3+ beds</option>
          <option value="4">4+ beds</option>
          <option value="5">5+ beds</option>
        </select>

        {/* Max price filter */}
        <div className="relative">
          <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 text-sm">$</span>
          <input
            type="number"
            placeholder="Max price"
            value={filters.maxPrice ?? ''}
            onChange={(e) => change('maxPrice', e.target.value ? parseInt(e.target.value) : null)}
            className="border border-gray-300 rounded-lg pl-6 pr-3 py-1.5 text-sm w-32 focus:outline-none focus:ring-2 focus:ring-gray-400"
          />
        </div>

        {/* Pets filter */}
        <label className="flex items-center gap-1.5 text-sm text-gray-600 cursor-pointer select-none border border-gray-300 rounded-lg px-3 py-1.5 hover:bg-gray-50 transition-colors">
          <input
            type="checkbox"
            checked={filters.petsOnly ?? false}
            onChange={(e) => change('petsOnly', e.target.checked)}
            className="rounded"
          />
          Pets OK
        </label>

        {/* Hide no-photo */}
        <label className="flex items-center gap-1.5 text-sm text-gray-600 cursor-pointer select-none border border-gray-300 rounded-lg px-3 py-1.5 hover:bg-gray-50 transition-colors">
          <input
            type="checkbox"
            checked={filters.photoOnly ?? false}
            onChange={(e) => change('photoOnly', e.target.checked)}
            className="rounded"
          />
          Photos only
        </label>

        {/* Clear filters */}
        {(filters.minBeds || filters.maxPrice || filters.petsOnly || filters.photoOnly) && (
          <button
            onClick={() => onFiltersChange({ minBeds: null, maxPrice: null, petsOnly: false, photoOnly: false })}
            className="text-xs text-gray-400 hover:text-gray-700 underline"
          >
            Clear filters
          </button>
        )}

        {/* View toggle — pushed to the right */}
        <div className="ml-auto flex border border-gray-300 rounded-lg overflow-hidden">
          <button
            onClick={() => onViewModeChange('grid')}
            className={`px-3 py-1.5 transition-colors ${viewMode === 'grid' ? 'bg-gray-900 text-white' : 'text-gray-600 hover:bg-gray-50'}`}
            title="Grid view"
          >
            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 16 16">
              <rect x="1" y="1" width="6" height="6" rx="1" /><rect x="9" y="1" width="6" height="6" rx="1" />
              <rect x="1" y="9" width="6" height="6" rx="1" /><rect x="9" y="9" width="6" height="6" rx="1" />
            </svg>
          </button>
          <button
            onClick={() => onViewModeChange('list')}
            className={`px-3 py-1.5 border-l border-gray-300 transition-colors ${viewMode === 'list' ? 'bg-gray-900 text-white' : 'text-gray-600 hover:bg-gray-50'}`}
            title="List view"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  )
}
