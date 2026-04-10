import { useState, useEffect } from 'react'

function formatPrice(price) {
  if (price == null) return 'N/A'
  return '$' + Number(price).toLocaleString() + '/mo'
}

function Stat({ label, value }) {
  if (value == null || value === '') return null
  return (
    <div className="text-center">
      <p className="text-lg font-bold text-gray-900">{value}</p>
      <p className="text-xs text-gray-500 mt-0.5">{label}</p>
    </div>
  )
}

export default function PropertyPreviewModal({ result, isSaved, isSaving, onSave, onClose }) {
  const [photoIndex, setPhotoIndex] = useState(0)
  const photos = result.image_urls || []

  useEffect(() => {
    setPhotoIndex(0)
    const onKey = (e) => {
      if (e.key === 'Escape') onClose()
      if (e.key === 'ArrowRight') setPhotoIndex((i) => Math.min(i + 1, photos.length - 1))
      if (e.key === 'ArrowLeft') setPhotoIndex((i) => Math.max(i - 1, 0))
    }
    window.addEventListener('keydown', onKey)
    document.body.style.overflow = 'hidden'
    return () => {
      window.removeEventListener('keydown', onKey)
      document.body.style.overflow = ''
    }
  }, [result])

  const addressLine = [result.address, result.city, result.state, result.zip].filter(Boolean).join(', ')

  return (
    <div className="fixed inset-0 z-50 flex flex-col" style={{ background: 'rgba(0,0,0,0.7)' }}>
      <div className="bg-white flex flex-col h-full max-w-2xl w-full mx-auto shadow-2xl">

        {/* Sticky header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 shrink-0">
          <button onClick={onClose} className="p-1.5 rounded-full hover:bg-gray-100 transition-colors">
            <svg className="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>

          <p className="text-sm font-semibold text-gray-800 truncate mx-3 flex-1 text-center">
            {result.address || 'Property Preview'}
          </p>

          <button
            onClick={onSave}
            disabled={isSaved || isSaving}
            className={`shrink-0 px-4 py-1.5 rounded-lg text-sm font-semibold transition-colors ${
              isSaved
                ? 'bg-green-100 text-green-700'
                : isSaving
                ? 'bg-gray-100 text-gray-500'
                : 'bg-gray-900 text-white hover:bg-gray-700'
            }`}
          >
            {isSaved ? '✓ Saved' : isSaving ? 'Saving…' : 'Save to Library'}
          </button>
        </div>

        {/* Scrollable content */}
        <div className="overflow-y-auto flex-1">

          {/* Photo gallery */}
          {photos.length > 0 ? (
            <div>
              <div className="relative bg-black" style={{ aspectRatio: '16/9' }}>
                <img
                  key={photoIndex}
                  src={photos[photoIndex]}
                  alt={`Photo ${photoIndex + 1}`}
                  className="w-full h-full object-contain"
                  onError={(e) => { e.target.style.display = 'none' }}
                />

                {photos.length > 1 && (
                  <>
                    <button
                      onClick={() => setPhotoIndex((i) => Math.max(i - 1, 0))}
                      disabled={photoIndex === 0}
                      className="absolute left-2 top-1/2 -translate-y-1/2 bg-black/50 hover:bg-black/70 text-white rounded-full w-9 h-9 flex items-center justify-center disabled:opacity-30 transition-colors"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
                      </svg>
                    </button>
                    <button
                      onClick={() => setPhotoIndex((i) => Math.min(i + 1, photos.length - 1))}
                      disabled={photoIndex === photos.length - 1}
                      className="absolute right-2 top-1/2 -translate-y-1/2 bg-black/50 hover:bg-black/70 text-white rounded-full w-9 h-9 flex items-center justify-center disabled:opacity-30 transition-colors"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                      </svg>
                    </button>
                    <div className="absolute bottom-2 left-1/2 -translate-x-1/2 bg-black/50 text-white text-xs px-2.5 py-1 rounded-full">
                      {photoIndex + 1} / {photos.length}
                    </div>
                  </>
                )}
              </div>

              {/* Thumbnails */}
              {photos.length > 1 && (
                <div className="flex gap-1.5 overflow-x-auto p-2 bg-gray-900">
                  {photos.map((url, i) => (
                    <button
                      key={i}
                      onClick={() => setPhotoIndex(i)}
                      className={`shrink-0 w-14 h-10 rounded overflow-hidden border-2 transition-colors ${
                        i === photoIndex ? 'border-white' : 'border-transparent opacity-60 hover:opacity-90'
                      }`}
                    >
                      <img src={url} alt="" className="w-full h-full object-cover" onError={(e) => { e.target.style.display = 'none' }} />
                    </button>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <div className="h-48 bg-gray-100 flex items-center justify-center text-gray-400 text-sm">
              No photos available
            </div>
          )}

          <div className="p-5 space-y-5">

            {/* Price + address */}
            <div>
              <p className="text-2xl font-bold text-gray-900">{formatPrice(result.monthly_rent)}</p>
              <p className="text-base text-gray-800 mt-1">{addressLine}</p>
              {result.property_type && (
                <p className="text-sm text-gray-500 mt-0.5 capitalize">{result.property_type.replace(/_/g, ' ')}</p>
              )}
            </div>

            {/* Key stats */}
            <div className="grid grid-cols-4 gap-3 py-4 border-y border-gray-100">
              <Stat label="Bedrooms" value={result.bedrooms} />
              <Stat label="Bathrooms" value={result.bathrooms} />
              <Stat label="Sqft" value={result.square_footage != null ? Number(result.square_footage).toLocaleString() : null} />
              <Stat label="Year Built" value={result.year_built} />
            </div>

            {/* Extra details */}
            {(result.lot_size_sqft || result.half_bathrooms || result.county) && (
              <div className="grid grid-cols-2 gap-3 text-sm">
                {result.lot_size_sqft && (
                  <div>
                    <p className="text-xs text-gray-500">Lot Size</p>
                    <p className="font-medium">{Number(result.lot_size_sqft).toLocaleString()} sqft</p>
                  </div>
                )}
                {result.half_bathrooms != null && (
                  <div>
                    <p className="text-xs text-gray-500">Half Baths</p>
                    <p className="font-medium">{result.half_bathrooms}</p>
                  </div>
                )}
                {result.county && (
                  <div>
                    <p className="text-xs text-gray-500">County</p>
                    <p className="font-medium">{result.county}</p>
                  </div>
                )}
              </div>
            )}

            {/* Description */}
            {result.description && (
              <div>
                <h3 className="text-sm font-semibold text-gray-700 mb-1">Description</h3>
                <p className="text-sm text-gray-600 leading-relaxed">{result.description}</p>
              </div>
            )}

            {/* Source */}
            <div className="pt-2 border-t border-gray-100 flex items-center justify-between">
              <p className="text-xs text-gray-400">
                Source: {result.source || 'Realtor.com'}
                {result.source_listing_id && ` · ID: ${result.source_listing_id}`}
              </p>
              {result.source_url && (
                <a
                  href={result.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-blue-600 hover:underline"
                  onClick={(e) => e.stopPropagation()}
                >
                  View original →
                </a>
              )}
            </div>

          </div>
        </div>
      </div>
    </div>
  )
}
