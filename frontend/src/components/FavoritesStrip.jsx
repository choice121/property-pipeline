import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { getFavorites, removeFavorite, clearFavorites, FAVORITES_EVENT } from '../utils/favorites'
import { transformImage } from '../utils/imageUrl'

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

function formatPrice(price) {
  if (price == null) return null
  return '$' + Number(price).toLocaleString()
}

export default function FavoritesStrip({ properties }) {
  const [favs, setFavs] = useState(() => getFavorites())

  useEffect(() => {
    function refresh() { setFavs(getFavorites()) }
    window.addEventListener(FAVORITES_EVENT, refresh)
    window.addEventListener('focus', refresh)
    return () => {
      window.removeEventListener(FAVORITES_EVENT, refresh)
      window.removeEventListener('focus', refresh)
    }
  }, [])

  const byId = useMemo(() => {
    const map = new Map()
    ;(properties || []).forEach((p) => map.set(String(p.id), p))
    return map
  }, [properties])

  const items = useMemo(() => {
    return favs
      .map((entry) => {
        const property = byId.get(String(entry.id))
        return property ? { ...entry, property } : null
      })
      .filter(Boolean)
  }, [favs, byId])

  if (!items.length) return null

  const handleRemove = (e, id) => {
    e.preventDefault()
    e.stopPropagation()
    removeFavorite(id)
  }

  const handleClear = () => {
    if (window.confirm('Remove all favorites?')) clearFavorites()
  }

  return (
    <section className="mb-5">
      <div className="flex items-center justify-between mb-2 px-1">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-amber-700 flex items-center gap-1.5">
          <svg className="w-3.5 h-3.5 fill-amber-500" viewBox="0 0 20 20">
            <path d="M10 1.5l2.625 5.32 5.875.855-4.25 4.14 1.005 5.85L10 14.91l-5.255 2.755L5.75 11.815 1.5 7.675l5.875-.855L10 1.5z" />
          </svg>
          Favorites ({items.length})
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
        {items.map(({ id, property }) => {
          const img = firstImageUrl(property)
          const thumbSrc = img ? transformImage(img, { w: 240, q: 70 }) : null
          const price = formatPrice(property.monthly_rent)
          return (
            <Link
              key={id}
              to={`/edit/${id}`}
              className="group relative flex-shrink-0 w-36 sm:w-40 snap-start rounded-lg overflow-hidden border border-amber-200 bg-white hover:border-amber-400 hover:shadow-sm transition-all"
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
                <span className="absolute top-1 left-1 z-10 w-5 h-5 rounded-full bg-amber-400/95 text-white text-xs flex items-center justify-center shadow">
                  <svg className="w-3 h-3 fill-current" viewBox="0 0 20 20">
                    <path d="M10 1.5l2.625 5.32 5.875.855-4.25 4.14 1.005 5.85L10 14.91l-5.255 2.755L5.75 11.815 1.5 7.675l5.875-.855L10 1.5z" />
                  </svg>
                </span>
                <button
                  type="button"
                  onClick={(e) => handleRemove(e, id)}
                  aria-label="Remove from favorites"
                  className="absolute top-1 right-1 w-6 h-6 rounded-full bg-black/55 text-white text-xs flex items-center justify-center opacity-0 group-hover:opacity-100 focus:opacity-100 hover:bg-black/75 transition-opacity"
                >
                  ×
                </button>
              </div>
              <div className="p-2">
                {price && (
                  <div className="text-xs font-semibold text-gray-900">{price}<span className="text-gray-400 font-normal">/mo</span></div>
                )}
                <div className="text-[11px] text-gray-700 truncate">
                  {property.address || 'Untitled'}
                </div>
                <div className="text-[10px] text-gray-400 truncate">
                  {[property.city, property.state].filter(Boolean).join(', ')}
                </div>
              </div>
            </Link>
          )
        })}
      </div>
    </section>
  )
}
