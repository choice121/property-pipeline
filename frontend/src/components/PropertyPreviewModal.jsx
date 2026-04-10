import { useState, useEffect } from 'react'

function formatPrice(price) {
  if (price == null) return 'N/A'
  return '$' + Number(price).toLocaleString() + '/mo'
}

function formatLabel(str) {
  if (!str) return ''
  return str.replace(/_/g, ' ')
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

function ListingAgeFull({ listDate, daysOnMarket }) {
  let text = null
  if (daysOnMarket != null) {
    if (daysOnMarket === 0) text = 'Listed today'
    else if (daysOnMarket === 1) text = 'Listed yesterday'
    else text = `Listed ${daysOnMarket} days ago`
  } else if (listDate) {
    const d = new Date(listDate)
    const days = Math.floor((Date.now() - d.getTime()) / 86400000)
    if (!isNaN(days)) {
      if (days === 0) text = 'Listed today'
      else if (days === 1) text = 'Listed yesterday'
      else text = `Listed ${days} days ago`
    }
    if (listDate) text = (text ? text + ' · ' : '') + listDate
  }
  if (!text) return null
  return (
    <span className="inline-flex items-center gap-1 text-xs bg-gray-100 text-gray-600 px-2.5 py-1 rounded-full">
      <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
        <rect x="3" y="4" width="18" height="18" rx="2" ry="2" /><line x1="16" y1="2" x2="16" y2="6" /><line x1="8" y1="2" x2="8" y2="6" /><line x1="3" y1="10" x2="21" y2="10" />
      </svg>
      {text}
    </span>
  )
}

function PhotoSlot({ src, alt }) {
  const [error, setError] = useState(false)
  if (error) {
    return (
      <div className="w-full h-full bg-gray-200 flex items-center justify-center text-gray-400 text-sm">
        Photo unavailable
      </div>
    )
  }
  return (
    <img
      src={src}
      alt={alt}
      className="w-full h-full object-contain"
      onError={() => setError(true)}
    />
  )
}

function ThumbnailSlot({ src, onClick, active }) {
  const [error, setError] = useState(false)
  return (
    <button
      onClick={onClick}
      className={`shrink-0 w-14 h-10 rounded overflow-hidden border-2 transition-colors ${
        active ? 'border-white' : 'border-transparent opacity-60 hover:opacity-90'
      } ${error ? 'bg-gray-700' : ''}`}
    >
      {!error ? (
        <img src={src} alt="" className="w-full h-full object-cover" onError={() => setError(true)} />
      ) : (
        <div className="w-full h-full flex items-center justify-center text-gray-500 text-xs">×</div>
      )}
    </button>
  )
}

export default function PropertyPreviewModal({ result, isSaved, isSaving, isInLibrary, onSave, onClose }) {
  const [photoIndex, setPhotoIndex] = useState(0)
  const photos = result.image_urls || []
  const savedState = isSaved || isInLibrary

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
    <div
      className="fixed inset-0 z-50 flex flex-col"
      style={{ background: 'rgba(0,0,0,0.75)' }}
      onClick={onClose}
    >
      <div
        className="bg-white flex flex-col h-full max-w-2xl w-full mx-auto shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >

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
            disabled={savedState || isSaving}
            className={`shrink-0 px-4 py-1.5 rounded-lg text-sm font-semibold transition-colors ${
              savedState
                ? 'bg-green-100 text-green-700'
                : isSaving
                ? 'bg-gray-100 text-gray-500'
                : 'bg-gray-900 text-white hover:bg-gray-700'
            }`}
          >
            {savedState ? '✓ Saved' : isSaving ? 'Saving…' : 'Save to Library'}
          </button>
        </div>

        {/* Scrollable content */}
        <div className="overflow-y-auto flex-1">

          {/* Photo gallery */}
          {photos.length > 0 ? (
            <div>
              <div className="relative bg-black" style={{ aspectRatio: '16/9' }}>
                <PhotoSlot key={photoIndex} src={photos[photoIndex]} alt={`Photo ${photoIndex + 1}`} />

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

              {photos.length > 1 && (
                <div className="flex gap-1.5 overflow-x-auto p-2 bg-gray-900">
                  {photos.map((url, i) => (
                    <ThumbnailSlot
                      key={i}
                      src={url}
                      active={i === photoIndex}
                      onClick={() => setPhotoIndex(i)}
                    />
                  ))}
                </div>
              )}
            </div>
          ) : (
            <div className="h-48 bg-gray-100 flex items-center justify-center text-gray-400 text-sm">
              No photos available
            </div>
          )}

          <div className="p-5 space-y-4">

            {/* Price + address */}
            <div>
              <div className="flex items-start justify-between gap-2 mb-1">
                <p className="text-2xl font-bold text-gray-900">{formatPrice(result.monthly_rent)}</p>
                {isInLibrary && !isSaved && (
                  <span className="shrink-0 text-xs bg-amber-100 text-amber-700 px-2 py-1 rounded font-medium mt-1">
                    Already in library
                  </span>
                )}
              </div>
              <p className="text-base text-gray-800">{addressLine}</p>
              <div className="flex flex-wrap items-center gap-2 mt-2">
                {result.property_type && (
                  <span className="text-sm text-gray-500 capitalize">{formatLabel(result.property_type)}</span>
                )}
                {result.listing_type && (
                  <span className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded capitalize">
                    {formatLabel(result.listing_type)}
                  </span>
                )}
                <ListingAgeFull listDate={result.list_date} daysOnMarket={result.days_on_market} />
              </div>
            </div>

            {/* Key stats */}
            <div className="grid grid-cols-4 gap-3 py-4 border-y border-gray-100">
              <Stat label="Bedrooms" value={result.bedrooms} />
              <Stat label="Bathrooms" value={result.bathrooms} />
              <Stat label="Sqft" value={result.square_footage != null ? Number(result.square_footage).toLocaleString() : null} />
              <Stat label="Year Built" value={result.year_built} />
            </div>

            {/* Pets + Parking + Extra */}
            {(result.pets_allowed != null || result.parking || result.lot_size_sqft || result.half_bathrooms || result.county) && (
              <div className="grid grid-cols-2 gap-3 text-sm">
                {result.pets_allowed != null && (
                  <div>
                    <p className="text-xs text-gray-500">Pets</p>
                    <p className="font-medium">{result.pets_allowed ? '🐾 Allowed' : 'Not allowed'}</p>
                  </div>
                )}
                {result.parking && (
                  <div>
                    <p className="text-xs text-gray-500">Parking</p>
                    <p className="font-medium">🚗 {result.parking}</p>
                  </div>
                )}
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
