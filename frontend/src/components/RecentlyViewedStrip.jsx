import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { getRecentlyViewed, removeRecentlyViewed, clearRecentlyViewed } from '../utils/recentlyViewed'
import { transformImage } from '../utils/imageUrl'

function relativeTime(ts) {
  const diff = Date.now() - ts
  const min = Math.floor(diff / 60000)
  if (min < 1) return 'just now'
  if (min < 60) return `${min}m ago`
  const h = Math.floor(min / 60)
  if (h < 24) return `${h}h ago`
  return `${Math.floor(h / 24)}d ago`
}

function firstImageUrl(p) {
  if (!p) return null
  try {
    const live = JSON.parse(p.live_image_urls || '[]')
    if (Array.isArray(live) && live.length) return live[0]
  } catch { /* ignore */ }
  try {
    const local = JSON.parse(p.local_image_paths || '[]')
    if (Array.isArray(local) && local.length) {
      const first = local[0]
      if (typeof first === 'string') {
        return first.startsWith('/') ? first : `/${first.replace(/^backend\//, '')}`
      }
    }
  } catch { /* ignore */ }
  return null
}

export default function RecentlyViewedStrip({ properties, onSelectionLink }) {
  const [recent, setRecent] = useState(() => getRecentlyViewed())

  useEffect(() => {
    function refresh() { setRecent(getRecentlyViewed()) }
    window.addEventListener('pp:recently-viewed-changed', refresh)
    window.addEventListener('focus', refresh)
    const tick = setInterval(refresh, 60000)
    return () => {
      window.removeEventListener('pp:recently-viewed-changed', refresh)
      window.removeEventListener('focus', refresh)
      clearInterval(tick)
    }
  }, [])

  const byId = useMemo(() => {
    const map = new Map()
    ;(properties || []).forEach((p) => map.set(String(p.id), p))
    return map
  }, [properties])

  const items = useMemo(() => {
    return recent
      .map((entry) => {
        const property = byId.get(String(entry.id))
        return property ? { ...entry, property } : null
      })
      .filter(Boolean)
      .slice(0, 12)
  }, [recent, byId])

  if (!items.length) return null

  const handleRemove = (e, id) => {
    e.preventDefault()
    e.stopPropagation()
    removeRecentlyViewed(id)
  }

  const handleClear = () => {
    clearRecentlyViewed()
  }

  return (
    <section className="mb-5">
      <div className="flex items-center justify-between mb-2 px-1">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-gray-500">
          Recently viewed
        </h2>
        <button
          onClick={handleClear}
          className="text-xs text-gray-400 hover:text-gray-700 underline-offset-2 hover:underline"
        >
          Clear
        </button>
      </div>
      <div
        className="flex gap-3 overflow-x-auto pb-2 -mx-3 px-3 sm:mx-0 sm:px-0 snap-x snap-mandatory scroll-smooth"
        style={{ scrollbarWidth: 'thin' }}
      >
        {items.map(({ id, ts, property }) => {
          const img = firstImageUrl(property)
          const thumbSrc = img ? transformImage(img, { w: 240, q: 70 }) : null
          return (
            <Link
              key={id}
              to={`/edit/${id}`}
              onClick={onSelectionLink}
              className="group relative flex-shrink-0 w-36 sm:w-40 snap-start rounded-lg overflow-hidden border border-gray-200 bg-white hover:border-gray-400 hover:shadow-sm transition-all"
            >
              <div className="aspect-[4/3] bg-gray-100 overflow-hidden">
                {thumbSrc ? (
                  <img
                    src={thumbSrc}
                    alt=""
                    loading="lazy"
                    decoding="async"
                    className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-gray-300 text-xs">
                    No photo
                  </div>
                )}
                <button
                  type="button"
                  onClick={(e) => handleRemove(e, id)}
                  aria-label="Remove from recently viewed"
                  className="absolute top-1 right-1 w-6 h-6 rounded-full bg-black/55 text-white text-xs flex items-center justify-center opacity-0 group-hover:opacity-100 focus:opacity-100 hover:bg-black/75 transition-opacity"
                >
                  ×
                </button>
              </div>
              <div className="p-2">
                <div className="text-xs font-medium text-gray-900 truncate">
                  {property.address || 'Untitled'}
                </div>
                <div className="text-[11px] text-gray-500 truncate">
                  {property.city ? `${property.city}, ${property.state || ''}` : relativeTime(ts)}
                </div>
                {property.city && (
                  <div className="text-[10px] text-gray-400 mt-0.5">{relativeTime(ts)}</div>
                )}
              </div>
            </Link>
          )
        })}
      </div>
    </section>
  )
}
