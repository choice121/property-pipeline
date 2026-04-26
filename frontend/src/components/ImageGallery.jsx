import { useState } from 'react'
import { transformImage } from '../utils/imageUrl'

export default function ImageGallery({ propertyId, images, onDelete, onReorder }) {
  const [lightbox, setLightbox] = useState(null)

  if (!images || images.length === 0) {
    return (
      <div className="text-gray-400 text-sm py-6 text-center border border-dashed border-gray-300 rounded-lg">
        No photos available
      </div>
    )
  }

  function getUrl(path) {
    const parts = path.split('/')
    const filename = parts[parts.length - 1]
    const propId = parts[parts.length - 2]
    return `/api/images/${propId}/${filename}`
  }

  function getThumb(path) {
    const url = getUrl(path)
    // Local proxy URL — no transform available; rely on browser scaling.
    return url
  }

  function moveLeft(index) {
    if (index === 0) return
    const order = images.map((_, i) => i + 1)
    ;[order[index - 1], order[index]] = [order[index], order[index - 1]]
    onReorder(order)
  }

  function moveRight(index) {
    if (index === images.length - 1) return
    const order = images.map((_, i) => i + 1)
    ;[order[index], order[index + 1]] = [order[index + 1], order[index]]
    onReorder(order)
  }

  return (
    <div>
      <p className="text-sm text-gray-500 mb-2">{images.length} photo{images.length !== 1 ? 's' : ''}</p>
      <div className="flex gap-3 overflow-x-auto pb-2 -mx-1 px-1 snap-x snap-mandatory">
        {images.map((path, i) => (
          <div key={path} className="relative flex-shrink-0 w-32 sm:w-36 snap-start">
            <button
              type="button"
              onClick={() => setLightbox(i)}
              className="block w-full"
            >
              <img
                src={getThumb(path)}
                alt={`Photo ${i + 1}`}
                loading="lazy"
                decoding="async"
                className="w-32 sm:w-36 h-24 sm:h-28 object-cover rounded-lg border border-gray-200 bg-gray-100"
              />
            </button>
            {i === 0 && (
              <span className="absolute bottom-1 left-1 bg-black/65 text-white text-[10px] px-1.5 py-0.5 rounded font-medium">
                Cover
              </span>
            )}
            <button
              onClick={() => onDelete(i + 1)}
              className="absolute top-1 right-1 bg-red-500 text-white rounded-full w-6 h-6 flex items-center justify-center text-xs hover:bg-red-600 active:scale-95 transition-transform"
              title="Delete photo"
            >
              ×
            </button>
            <div className="flex gap-1 mt-1 justify-center">
              <button
                onClick={() => moveLeft(i)}
                disabled={i === 0}
                className="text-xs px-2 py-1 bg-gray-100 rounded hover:bg-gray-200 disabled:opacity-30 active:scale-95 transition-transform"
              >
                ←
              </button>
              <button
                onClick={() => moveRight(i)}
                disabled={i === images.length - 1}
                className="text-xs px-2 py-1 bg-gray-100 rounded hover:bg-gray-200 disabled:opacity-30 active:scale-95 transition-transform"
              >
                →
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Mobile-friendly lightbox */}
      {lightbox != null && (
        <div
          className="fixed inset-0 z-[70] bg-black/90 flex items-center justify-center animate-fade-in"
          onClick={() => setLightbox(null)}
        >
          <button
            onClick={() => setLightbox(null)}
            className="absolute top-4 right-4 text-white/80 hover:text-white touch-target"
            aria-label="Close"
          >
            <svg className="w-7 h-7" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
          {lightbox > 0 && (
            <button
              onClick={(e) => { e.stopPropagation(); setLightbox(lightbox - 1) }}
              className="absolute left-2 sm:left-6 text-white/80 hover:text-white touch-target"
              aria-label="Previous"
            >
              <svg className="w-8 h-8" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
              </svg>
            </button>
          )}
          {lightbox < images.length - 1 && (
            <button
              onClick={(e) => { e.stopPropagation(); setLightbox(lightbox + 1) }}
              className="absolute right-2 sm:right-6 text-white/80 hover:text-white touch-target"
              aria-label="Next"
            >
              <svg className="w-8 h-8" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
              </svg>
            </button>
          )}
          <img
            src={getUrl(images[lightbox])}
            alt={`Photo ${lightbox + 1}`}
            className="max-h-[90vh] max-w-[95vw] object-contain"
            onClick={(e) => e.stopPropagation()}
          />
          <div className="absolute bottom-4 left-0 right-0 text-center text-white/70 text-sm">
            {lightbox + 1} / {images.length}
          </div>
        </div>
      )}
    </div>
  )
}
