function formatPrice(price) {
  if (price == null) return 'N/A'
  return '$' + Number(price).toLocaleString() + '/mo'
}

export default function SearchResultCard({ result, isSaved, isSaving, onSave, onPreview }) {
  const firstPhoto = result.image_urls?.[0] || null
  const photoCount = result.image_urls?.length || 0

  return (
    <div className="bg-white rounded-lg border border-gray-200 overflow-hidden hover:shadow-md transition-shadow flex flex-col">
      <div className="relative cursor-pointer" onClick={onPreview}>
        {firstPhoto ? (
          <img
            src={firstPhoto}
            alt={result.address || 'Property'}
            className="w-full h-48 object-cover"
            onError={(e) => {
              e.target.style.display = 'none'
              e.target.nextSibling.style.display = 'flex'
            }}
          />
        ) : null}
        <div
          style={{ display: firstPhoto ? 'none' : 'flex' }}
          className="w-full h-48 bg-gray-100 items-center justify-center"
        >
          <svg className="w-14 h-14 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z" />
          </svg>
        </div>

        {photoCount > 1 && (
          <div className="absolute bottom-2 right-2 bg-black/60 text-white text-xs px-2 py-0.5 rounded-full">
            {photoCount} photos
          </div>
        )}

        <div className="absolute top-2 left-2 bg-black/60 text-white text-xs px-2 py-1 rounded">
          {result.listing_type?.replace('_', ' ') || ''}
        </div>
      </div>

      <div className="p-4 flex flex-col flex-1">
        <div className="flex-1 cursor-pointer" onClick={onPreview}>
          <p className="text-lg font-bold text-gray-900">{formatPrice(result.monthly_rent)}</p>
          <p className="text-sm text-gray-800 mt-0.5 truncate">{result.address || 'No address'}</p>
          <p className="text-xs text-gray-500">{[result.city, result.state, result.zip].filter(Boolean).join(', ')}</p>
          <div className="flex flex-wrap gap-3 mt-2 text-xs text-gray-600">
            {result.bedrooms != null && <span>{result.bedrooms} bd</span>}
            {result.bathrooms != null && <span>{result.bathrooms} ba</span>}
            {result.square_footage != null && <span>{Number(result.square_footage).toLocaleString()} sqft</span>}
            {result.property_type && <span className="text-gray-400">{result.property_type.replace(/_/g, ' ')}</span>}
          </div>
        </div>

        <div className="mt-3 flex gap-2">
          <button
            onClick={onPreview}
            className="flex-1 py-1.5 rounded border border-gray-300 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
          >
            View Details
          </button>
          <button
            onClick={onSave}
            disabled={isSaved || isSaving}
            className={`flex-1 py-1.5 rounded text-sm font-medium transition-colors ${
              isSaved
                ? 'bg-green-100 text-green-700 border border-green-200'
                : isSaving
                ? 'bg-gray-100 text-gray-500 border border-gray-200'
                : 'bg-gray-900 text-white hover:bg-gray-700'
            }`}
          >
            {isSaved ? '✓ Saved' : isSaving ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  )
}
