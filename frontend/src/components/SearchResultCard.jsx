import { useState } from 'react'
import { resolveImageUrl } from '../utils/imageUrl'

function formatPrice(price) {
  if (price == null) return 'N/A'
  return '$' + Number(price).toLocaleString() + '/mo'
}

function formatLabel(str) {
  if (!str) return ''
  return str.replace(/_/g, ' ')
}

function ListingAge({ listDate, daysOnMarket }) {
  if (daysOnMarket != null) {
    if (daysOnMarket === 0) return <span className="text-green-600 font-medium">Listed today</span>
    if (daysOnMarket === 1) return <span className="text-green-600 font-medium">Listed yesterday</span>
    if (daysOnMarket <= 7) return <span className="text-green-600 font-medium">{daysOnMarket}d ago</span>
    if (daysOnMarket <= 30) return <span className="text-gray-500">{daysOnMarket}d ago</span>
    return <span className="text-gray-400">{daysOnMarket}d ago</span>
  }
  if (listDate) {
    const d = new Date(listDate)
    const days = Math.floor((Date.now() - d.getTime()) / 86400000)
    if (isNaN(days)) return null
    if (days === 0) return <span className="text-green-600 font-medium">Listed today</span>
    if (days <= 7) return <span className="text-green-600 font-medium">{days}d ago</span>
    if (days <= 30) return <span className="text-gray-500">{days}d ago</span>
    return <span className="text-gray-400">{days}d ago</span>
  }
  return null
}

export default function SearchResultCard({ result, isSaved, isSaving, isInLibrary, onSave, onPreview }) {
  const [imgError, setImgError] = useState(false)
  const firstPhoto = !imgError ? resolveImageUrl(result.image_urls?.[0] || null) : null
  const photoCount = result.image_urls?.length || 0

  const savedState = isSaved || isInLibrary

  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden hover:shadow-md transition-shadow flex flex-col">

      {/* Photo */}
      <div className="relative cursor-pointer flex-shrink-0" onClick={onPreview}>
        {firstPhoto ? (
          <img
            src={firstPhoto}
            alt={result.address || 'Property'}
            className="w-full h-44 object-cover"
            onError={() => setImgError(true)}
          />
        ) : (
          <div className="w-full h-44 bg-gray-100 flex flex-col items-center justify-center gap-1">
            <svg className="w-10 h-10 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z" />
            </svg>
            <span className="text-xs text-gray-400">No photo</span>
          </div>
        )}

        {photoCount > 1 && (
          <div className="absolute bottom-2 right-2 bg-black/60 text-white text-xs px-2 py-0.5 rounded-full">
            {photoCount} photos
          </div>
        )}

        {result.listing_type && (
          <div className="absolute top-2 left-2 bg-black/60 text-white text-xs px-2 py-1 rounded capitalize">
            {formatLabel(result.listing_type)}
          </div>
        )}

        {isInLibrary && !isSaved && (
          <div className="absolute top-2 right-2 bg-amber-500/90 text-white text-xs px-2 py-1 rounded font-medium">
            In library
          </div>
        )}
      </div>

      {/* Content */}
      <div className="p-3 flex flex-col flex-1 gap-2">

        {/* Price + age */}
        <div className="flex items-start justify-between gap-2">
          <p className="text-base font-bold text-gray-900 leading-tight">{formatPrice(result.monthly_rent)}</p>
          <span className="text-xs shrink-0 mt-0.5">
            <ListingAge listDate={result.list_date} daysOnMarket={result.days_on_market} />
          </span>
        </div>

        {/* Address */}
        <div className="cursor-pointer" onClick={onPreview}>
          <p className="text-sm text-gray-800 truncate font-medium">{result.address || 'No address'}</p>
          <p className="text-xs text-gray-500">{[result.city, result.state, result.zip].filter(Boolean).join(', ')}</p>
        </div>

        {/* Key stats */}
        <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-gray-600">
          {result.bedrooms != null && <span>{result.bedrooms} bd</span>}
          {result.bathrooms != null && <span>{result.bathrooms} ba</span>}
          {result.square_footage != null && <span>{Number(result.square_footage).toLocaleString()} sqft</span>}
          {result.property_type && (
            <span className="text-gray-400 capitalize">{formatLabel(result.property_type)}</span>
          )}
        </div>

        {/* Amenity pills */}
        {(result.pets_allowed != null || result.parking) && (
          <div className="flex flex-wrap gap-1">
            {result.pets_allowed === true && (
              <span className="text-xs bg-green-50 text-green-700 border border-green-200 px-2 py-0.5 rounded-full">
                🐾 Pets OK
              </span>
            )}
            {result.pets_allowed === false && (
              <span className="text-xs bg-gray-50 text-gray-500 border border-gray-200 px-2 py-0.5 rounded-full">
                No pets
              </span>
            )}
            {result.parking && (
              <span className="text-xs bg-blue-50 text-blue-700 border border-blue-200 px-2 py-0.5 rounded-full">
                🚗 {result.parking}
              </span>
            )}
          </div>
        )}

        {/* Actions */}
        <div className="mt-auto pt-1 flex gap-2">
          <button
            onClick={onPreview}
            className="flex-none px-3 py-1.5 rounded-lg border border-gray-300 text-xs text-gray-600 hover:bg-gray-50 transition-colors"
          >
            Details
          </button>
          <button
            onClick={onSave}
            disabled={savedState || isSaving}
            className={`flex-1 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
              savedState
                ? 'bg-green-50 text-green-700 border border-green-200'
                : isSaving
                ? 'bg-gray-100 text-gray-400 border border-gray-200'
                : 'bg-gray-900 text-white hover:bg-gray-700'
            }`}
          >
            {savedState ? '✓ Saved' : isSaving ? 'Saving…' : 'Save to Library'}
          </button>
        </div>
      </div>
    </div>
  )
}


export function SearchResultRow({ result, isSaved, isSaving, isInLibrary, onSave, onPreview }) {
  const [imgError, setImgError] = useState(false)
  const firstPhoto = !imgError ? resolveImageUrl(result.image_urls?.[0] || null) : null
  const photoCount = result.image_urls?.length || 0
  const savedState = isSaved || isInLibrary

  return (
    <div className="bg-white border border-gray-200 rounded-xl flex items-center gap-4 px-4 py-3 hover:shadow-sm transition-shadow">

      {/* Thumbnail */}
      <div className="flex-shrink-0 w-20 h-16 rounded-lg overflow-hidden bg-gray-100 cursor-pointer relative" onClick={onPreview}>
        {firstPhoto ? (
          <img src={firstPhoto} alt="" className="w-full h-full object-cover" onError={() => setImgError(true)} />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <svg className="w-7 h-7 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z" />
            </svg>
          </div>
        )}
        {photoCount > 1 && (
          <div className="absolute bottom-0.5 right-0.5 bg-black/60 text-white text-xs px-1 rounded-sm leading-tight">
            {photoCount}
          </div>
        )}
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0 cursor-pointer" onClick={onPreview}>
        <div className="flex items-baseline gap-3">
          <p className="font-bold text-gray-900">{formatPrice(result.monthly_rent)}</p>
          <span className="text-xs">
            <ListingAge listDate={result.list_date} daysOnMarket={result.days_on_market} />
          </span>
          {isInLibrary && !isSaved && (
            <span className="text-xs bg-amber-100 text-amber-700 px-1.5 py-0.5 rounded font-medium">In library</span>
          )}
        </div>
        <p className="text-sm text-gray-800 truncate">{result.address || 'No address'}</p>
        <div className="flex flex-wrap gap-x-3 text-xs text-gray-500 mt-0.5">
          <span>{[result.city, result.state, result.zip].filter(Boolean).join(', ')}</span>
          {result.bedrooms != null && <span>{result.bedrooms} bd</span>}
          {result.bathrooms != null && <span>{result.bathrooms} ba</span>}
          {result.square_footage != null && <span>{Number(result.square_footage).toLocaleString()} sqft</span>}
          {result.property_type && <span className="capitalize">{formatLabel(result.property_type)}</span>}
          {result.pets_allowed === true && <span className="text-green-600">Pets OK</span>}
          {result.parking && <span className="text-blue-600">{result.parking}</span>}
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2 shrink-0">
        <button
          onClick={onPreview}
          className="px-3 py-1.5 rounded-lg border border-gray-300 text-xs text-gray-600 hover:bg-gray-50 transition-colors"
        >
          Details
        </button>
        <button
          onClick={onSave}
          disabled={savedState || isSaving}
          className={`px-4 py-1.5 rounded-lg text-xs font-semibold transition-colors min-w-[90px] text-center ${
            savedState
              ? 'bg-green-50 text-green-700 border border-green-200'
              : isSaving
              ? 'bg-gray-100 text-gray-400 border border-gray-200'
              : 'bg-gray-900 text-white hover:bg-gray-700'
          }`}
        >
          {savedState ? '✓ Saved' : isSaving ? 'Saving…' : 'Save'}
        </button>
      </div>
    </div>
  )
}
