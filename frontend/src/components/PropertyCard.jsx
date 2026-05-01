import { useEffect, useState } from 'react'
import StatusBadge from './StatusBadge'
import { downloadProperty, redownloadImages } from '../api/client'
import { computeCompleteness, completenessColor } from '../utils/completeness'
import { resolveImageUrl, responsiveImage } from '../utils/imageUrl'
import { isFavorite, toggleFavorite, FAVORITES_EVENT } from '../utils/favorites'
import { tapHaptic } from '../utils/haptics'

function formatPrice(price) {
  if (price == null) return 'N/A'
  return '$' + Number(price).toLocaleString() + '/mo'
}

function getRawImageUrl(property) {
  try {
    const originals = JSON.parse(property.original_image_urls || '[]')
    if (originals.length > 0) return originals[0]
    const paths = JSON.parse(property.local_image_paths || '[]')
    if (paths.length === 0) return null
    const path = paths[0]
    const parts = path.split('/')
    const filename = parts[parts.length - 1]
    const propId = parts[parts.length - 2]
    return `/api/images/${propId}/${filename}`
  } catch {
    return null
  }
}

function PlaceholderImage() {
  return (
    <div className="w-full h-44 sm:h-48 bg-gray-100 flex items-center justify-center">
      <svg className="w-16 h-16 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z" />
        <polyline strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} points="9 22 9 12 15 12 15 22" />
      </svg>
    </div>
  )
}

function AiHealthBadge({ health }) {
  if (!health) return null
  const hasErrors = health.errors > 0
  const hasWarnings = health.warnings > 0
  const color = hasErrors ? 'bg-red-500' : hasWarnings ? 'bg-amber-400' : 'bg-green-500'
  const label = hasErrors
    ? `${health.errors} error${health.errors !== 1 ? 's' : ''}`
    : hasWarnings
      ? `${health.warnings} warning${health.warnings !== 1 ? 's' : ''}`
      : 'Looks good'
  return (
    <div
      title={health.top_issue || label}
      className={`absolute bottom-2 right-2 z-10 flex items-center gap-1 text-white text-xs font-semibold px-2 py-0.5 rounded-full shadow-sm ${color}`}
    >
      <span className="w-1.5 h-1.5 rounded-full bg-white/60 inline-block" />
      {label}
    </div>
  )
}

function ResponsiveImage({ rawUrl, alt }) {
  const [loaded, setLoaded] = useState(false)
  const [errored, setErrored] = useState(false)
  const url = rawUrl ? resolveImageUrl(rawUrl) : null
  const { src, srcSet } = responsiveImage(rawUrl, { width: 480, sizes: [320, 480, 640, 960] })

  if (!rawUrl || errored) return <PlaceholderImage />

  return (
    <div className="relative w-full h-44 sm:h-48 bg-gray-100">
      {!loaded && <div className="absolute inset-0 bg-gray-200 animate-pulse" />}
      <img
        src={src || url}
        srcSet={srcSet || undefined}
        sizes="(max-width: 640px) 100vw, 480px"
        alt={alt || 'Property'}
        loading="lazy"
        decoding="async"
        width="640"
        height="384"
        className={`w-full h-full object-cover fade-in ${loaded ? 'loaded' : ''}`}
        onLoad={() => setLoaded(true)}
        onError={() => setErrored(true)}
      />
    </div>
  )
}

export default function PropertyCard({ property, onClick, selectable, selected, onSelect, aiHealth, onRedownload }) {
  const rawImageUrl = getRawImageUrl(property)
  const [downloading, setDownloading] = useState(false)
  const [fetchState, setFetchState] = useState(null)
  const [showMissing, setShowMissing] = useState(false)
  const [fav, setFav] = useState(() => isFavorite(property.id))
  const { score, missing } = computeCompleteness(property)
  const { bar, text } = completenessColor(score)

  const sourceCount = (() => { try { return JSON.parse(property.original_image_urls || '[]').length } catch { return 0 } })()
  const localCount  = (() => { try { return JSON.parse(property.local_image_paths  || '[]').length } catch { return 0 } })()

  useEffect(() => {
    function sync() { setFav(isFavorite(property.id)) }
    window.addEventListener(FAVORITES_EVENT, sync)
    return () => window.removeEventListener(FAVORITES_EVENT, sync)
  }, [property.id])

  function handleToggleFavorite(e) {
    e.stopPropagation()
    const next = toggleFavorite(property.id)
    setFav(next)
    if (next) tapHaptic()
  }

  async function handleDownload(e) {
    e.stopPropagation()
    setDownloading(true)
    try {
      const res = await downloadProperty(property.id)
      const disposition = res.headers['content-disposition'] || ''
      const match = disposition.match(/filename="?([^"]+)"?/)
      const filename = match ? match[1] : `${property.id}.zip`
      const url = window.URL.createObjectURL(new Blob([res.data]))
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      a.remove()
      window.URL.revokeObjectURL(url)
    } catch {
      alert('Download failed. Please try again.')
    } finally {
      setDownloading(false)
    }
  }

  async function handleRefetchImages(e) {
    e.stopPropagation()
    if (fetchState === 'fetching') return
    setFetchState('fetching')
    try {
      await redownloadImages(property.id)
      setFetchState('queued')
      if (onRedownload) onRedownload(property.id)
      setTimeout(() => setFetchState(null), 3000)
    } catch (err) {
      const msg = err?.response?.data?.detail || 'Could not queue re-download.'
      alert(msg)
      setFetchState(null)
    }
  }

  function handleCardClick() {
    if (selectable) {
      onSelect && onSelect()
    } else {
      onClick && onClick()
    }
  }

  return (
    <div
      onClick={handleCardClick}
      className={`bg-white rounded-lg shadow-sm border cursor-pointer transition-all overflow-hidden relative no-select active:scale-[0.99]
        ${selectable
          ? selected
            ? 'border-gray-900 ring-2 ring-gray-900 shadow-md'
            : 'border-gray-200'
          : 'border-gray-100 hover:shadow-md'
        }`}
    >
      {/* Selection checkbox */}
      {selectable && (
        <div className="absolute top-2 left-2 z-20">
          <div className={`w-6 h-6 rounded-full border-2 flex items-center justify-center transition-colors shadow
            ${selected ? 'bg-gray-900 border-gray-900' : 'bg-white/95 border-gray-300'}`}
          >
            {selected && (
              <svg className="w-3.5 h-3.5 text-white" fill="none" stroke="currentColor" strokeWidth="3" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
              </svg>
            )}
          </div>
        </div>
      )}

      {/* Status badge */}
      <div className={`absolute z-10 ${selectable ? 'top-2 left-10' : 'top-2 left-2'}`}>
        <StatusBadge status={property.status} />
      </div>

      {/* Favorite + Download buttons */}
      {!selectable && (
        <>
          <button
            onClick={handleToggleFavorite}
            title={fav ? 'Remove favorite' : 'Add favorite'}
            aria-pressed={fav}
            aria-label={fav ? 'Remove from favorites' : 'Add to favorites'}
            className={`absolute top-2 right-12 z-10 rounded-full p-2 shadow transition-colors touch-target ${
              fav
                ? 'bg-amber-400/95 hover:bg-amber-400 text-white'
                : 'bg-white/90 hover:bg-white text-gray-500 hover:text-amber-500'
            }`}
          >
            <svg className="w-4 h-4" viewBox="0 0 20 20" fill={fav ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="1.6">
              <path strokeLinejoin="round" d="M10 1.5l2.625 5.32 5.875.855-4.25 4.14 1.005 5.85L10 14.91l-5.255 2.755L5.75 11.815 1.5 7.675l5.875-.855L10 1.5z" />
            </svg>
          </button>
          <button
            onClick={handleDownload}
            disabled={downloading}
            title="Download ZIP"
            className="absolute top-2 right-2 z-10 bg-white/90 hover:bg-white text-gray-600 hover:text-blue-600 rounded-full p-2 shadow transition-colors disabled:opacity-50"
          >
            {downloading ? (
              <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
              </svg>
            ) : (
              <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2M7 10l5 5 5-5M12 15V3" />
              </svg>
            )}
          </button>
        </>
      )}

      <ResponsiveImage rawUrl={rawImageUrl} alt={property.address} />

      <div className="p-3 sm:p-4">
        <p className="text-base sm:text-lg font-semibold text-gray-900">{formatPrice(property.monthly_rent)}</p>
        <p className="text-sm text-gray-700 truncate mt-1">{property.address || 'No address'}</p>
        <p className="text-xs text-gray-500 truncate">{[property.city, property.state, property.zip].filter(Boolean).join(', ')}</p>
        <div className="flex items-center gap-3 mt-2 text-xs text-gray-600">
          <span>{property.bedrooms != null ? `${property.bedrooms} bd` : '— bd'}</span>
          <span>{property.bathrooms != null ? `${property.bathrooms} ba` : '— ba'}</span>
          <span>{property.square_footage != null ? `${Number(property.square_footage).toLocaleString()} sqft` : '— sqft'}</span>

          {sourceCount > 0 && (
            <button
              onClick={handleRefetchImages}
              disabled={fetchState === 'fetching'}
              title={fetchState === 'queued' ? 'Queued!' : `Re-fetch ${sourceCount} source images`}
              className={`ml-auto flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium transition-colors disabled:opacity-60
                ${fetchState === 'queued'
                  ? 'bg-green-100 text-green-700'
                  : fetchState === 'fetching'
                    ? 'bg-blue-50 text-blue-500'
                    : localCount === 0
                      ? 'bg-amber-50 text-amber-700 hover:bg-amber-100'
                      : 'bg-gray-100 text-gray-500 hover:bg-gray-200 hover:text-gray-700'
                }`}
            >
              {fetchState === 'fetching' ? (
                <svg className="w-3 h-3 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
                </svg>
              ) : fetchState === 'queued' ? (
                <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7"/>
                </svg>
              ) : (
                <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"/>
                </svg>
              )}
              <span>
                {fetchState === 'fetching' ? 'Fetching…'
                  : fetchState === 'queued' ? 'Queued!'
                  : localCount > 0 ? `${localCount}/${sourceCount}`
                  : `${sourceCount} photos`}
              </span>
            </button>
          )}
        </div>

        <AiHealthBadge health={aiHealth} />

        {/* Completeness bar */}
        <div className="mt-3 relative">
          <div
            className="flex items-center justify-between mb-1 cursor-pointer select-none"
            onClick={(e) => { e.stopPropagation(); setShowMissing(v => !v) }}
          >
            <span className="text-xs font-medium" style={{ color: text }}>
              {score}% complete
            </span>
            {missing.length > 0 && (
              <span className="text-xs text-gray-400">
                {missing.length} missing ▾
              </span>
            )}
          </div>
          <div className="w-full h-1.5 bg-gray-100 rounded-full overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{ width: `${score}%`, backgroundColor: bar }}
            />
          </div>

          {showMissing && missing.length > 0 && (
            <div
              className="absolute bottom-full mb-2 left-0 right-0 bg-gray-900 text-white text-xs rounded-lg p-2.5 shadow-lg z-30"
              onClick={(e) => e.stopPropagation()}
            >
              <p className="font-semibold mb-1.5 text-gray-300">Missing fields:</p>
              <ul className="space-y-0.5">
                {missing.map(m => (
                  <li key={m} className="flex items-center gap-1.5">
                    <span className="w-1 h-1 rounded-full bg-amber-400 flex-shrink-0" />
                    {m}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
