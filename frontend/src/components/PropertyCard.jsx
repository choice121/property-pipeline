import StatusBadge from './StatusBadge'

function formatPrice(price) {
  if (price == null) return 'N/A'
  return '$' + Number(price).toLocaleString() + '/mo'
}

function getImageUrl(property) {
  try {
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
    <div className="w-full h-48 bg-gray-200 flex items-center justify-center">
      <svg className="w-16 h-16 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z" />
        <polyline strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} points="9 22 9 12 15 12 15 22" />
      </svg>
    </div>
  )
}

export default function PropertyCard({ property, onClick }) {
  const imageUrl = getImageUrl(property)

  return (
    <div
      onClick={onClick}
      className="bg-white rounded-lg shadow hover:shadow-md border border-gray-100 cursor-pointer transition-shadow overflow-hidden relative"
    >
      <div className="absolute top-2 right-2 z-10">
        <StatusBadge status={property.status} />
      </div>

      {imageUrl ? (
        <img
          src={imageUrl}
          alt={property.address || 'Property'}
          className="w-full h-48 object-cover"
          onError={(e) => { e.target.style.display = 'none'; e.target.nextSibling.style.display = 'flex' }}
        />
      ) : null}
      <div style={{ display: imageUrl ? 'none' : 'flex' }} className="w-full h-48 bg-gray-100 items-center justify-center">
        <PlaceholderImage />
      </div>

      <div className="p-4">
        <p className="text-lg font-semibold text-gray-900">{formatPrice(property.monthly_rent)}</p>
        <p className="text-sm text-gray-700 truncate mt-1">{property.address || 'No address'}</p>
        <p className="text-xs text-gray-500">{[property.city, property.state, property.zip].filter(Boolean).join(', ')}</p>
        <div className="flex gap-4 mt-2 text-xs text-gray-600">
          <span>{property.bedrooms != null ? `${property.bedrooms} bd` : 'N/A'}</span>
          <span>{property.bathrooms != null ? `${property.bathrooms} ba` : 'N/A'}</span>
          <span>{property.square_footage != null ? `${Number(property.square_footage).toLocaleString()} sqft` : 'N/A'}</span>
        </div>
      </div>
    </div>
  )
}
