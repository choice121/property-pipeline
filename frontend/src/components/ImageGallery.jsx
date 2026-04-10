export default function ImageGallery({ propertyId, images, onDelete, onReorder }) {
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
      <div className="flex gap-3 overflow-x-auto pb-2">
        {images.map((path, i) => (
          <div key={path} className="relative flex-shrink-0 w-36">
            <img
              src={getUrl(path)}
              alt={`Photo ${i + 1}`}
              className="w-36 h-28 object-cover rounded-lg border border-gray-200"
            />
            {i === 0 && (
              <span className="absolute bottom-1 left-1 bg-black bg-opacity-60 text-white text-xs px-1.5 py-0.5 rounded">
                Cover
              </span>
            )}
            <button
              onClick={() => onDelete(i + 1)}
              className="absolute top-1 right-1 bg-red-500 text-white rounded-full w-5 h-5 flex items-center justify-center text-xs hover:bg-red-600"
              title="Delete photo"
            >
              ×
            </button>
            <div className="flex gap-1 mt-1 justify-center">
              <button
                onClick={() => moveLeft(i)}
                disabled={i === 0}
                className="text-xs px-2 py-0.5 bg-gray-100 rounded hover:bg-gray-200 disabled:opacity-30"
              >
                ←
              </button>
              <button
                onClick={() => moveRight(i)}
                disabled={i === images.length - 1}
                className="text-xs px-2 py-0.5 bg-gray-100 rounded hover:bg-gray-200 disabled:opacity-30"
              >
                →
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
