import { useState } from 'react'

function parseArray(value) {
  try {
    const parsed = typeof value === 'string' ? JSON.parse(value || '[]') : value
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return typeof value === 'string' && value ? [value] : []
  }
}

function getImageUrl(path) {
  if (!path) return null
  const parts = path.split('/')
  const filename = parts[parts.length - 1]
  const propId = parts[parts.length - 2]
  return `/api/images/${propId}/${filename}`
}

function StatPill({ label, value }) {
  if (value == null || value === '') return null
  return (
    <div className="flex flex-col items-center bg-gray-50 border border-gray-200 rounded-lg px-4 py-3 min-w-0">
      <span className="text-base font-bold text-gray-900 leading-tight">{value}</span>
      <span className="text-xs text-gray-500 mt-0.5">{label}</span>
    </div>
  )
}

function TagList({ items, color = 'gray' }) {
  if (!items || items.length === 0) return <span className="text-sm text-gray-400">None listed</span>
  const colors = {
    gray: 'bg-gray-100 text-gray-700',
    blue: 'bg-blue-50 text-blue-700',
    green: 'bg-green-50 text-green-700',
  }
  return (
    <div className="flex flex-wrap gap-1.5">
      {items.map((item) => (
        <span key={item} className={`text-xs px-2.5 py-1 rounded-full font-medium ${colors[color] || colors.gray}`}>
          {item}
        </span>
      ))}
    </div>
  )
}

export default function ListingPreview({ property, onClose }) {
  const images = parseArray(property.local_image_paths).map(getImageUrl).filter(Boolean)
  const [activeImg, setActiveImg] = useState(0)

  const amenities = parseArray(property.amenities)
  const appliances = parseArray(property.appliances)
  const utilities = parseArray(property.utilities_included)
  const flooring = parseArray(property.flooring)
  const leaseTerms = parseArray(property.lease_terms)
  const petTypes = parseArray(property.pet_types_allowed)

  const rent = property.monthly_rent
    ? `$${Number(property.monthly_rent).toLocaleString()}/mo`
    : null

  const address = [property.address, property.city, property.state, property.zip]
    .filter(Boolean).join(', ')

  const title = property.title || address || 'Untitled Listing'

  function typeLabel(t) {
    if (!t) return null
    return t.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
  }

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/50 overflow-y-auto py-8 px-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl relative">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">Listing Preview</p>
            <p className="text-xs text-gray-400 mt-0.5">This is how your listing will appear on the live site</p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition-colors p-1 rounded-lg hover:bg-gray-100"
            aria-label="Close preview"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="overflow-y-auto max-h-[80vh]">
          {images.length > 0 ? (
            <div className="relative">
              <img
                src={images[activeImg]}
                alt={`Photo ${activeImg + 1}`}
                className="w-full h-72 object-cover"
              />
              {images.length > 1 && (
                <>
                  <button
                    onClick={() => setActiveImg((i) => (i - 1 + images.length) % images.length)}
                    className="absolute left-3 top-1/2 -translate-y-1/2 bg-black/50 text-white rounded-full w-8 h-8 flex items-center justify-center hover:bg-black/70"
                  >‹</button>
                  <button
                    onClick={() => setActiveImg((i) => (i + 1) % images.length)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 bg-black/50 text-white rounded-full w-8 h-8 flex items-center justify-center hover:bg-black/70"
                  >›</button>
                  <div className="absolute bottom-3 left-1/2 -translate-x-1/2 flex gap-1">
                    {images.map((_, i) => (
                      <button
                        key={i}
                        onClick={() => setActiveImg(i)}
                        className={`w-1.5 h-1.5 rounded-full transition-colors ${i === activeImg ? 'bg-white' : 'bg-white/50'}`}
                      />
                    ))}
                  </div>
                </>
              )}
              <div className="absolute bottom-3 right-3 bg-black/60 text-white text-xs px-2 py-1 rounded-full">
                {activeImg + 1} / {images.length}
              </div>
            </div>
          ) : (
            <div className="w-full h-48 bg-gray-100 flex items-center justify-center">
              <div className="text-center text-gray-400">
                <svg className="w-12 h-12 mx-auto mb-2 opacity-40" fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909M13.5 12h.008v.008H13.5V12zm4.5-4.5a.75.75 0 11-1.5 0 .75.75 0 011.5 0z" />
                </svg>
                <p className="text-sm">No photos uploaded yet</p>
              </div>
            </div>
          )}

          {images.length > 1 && (
            <div className="flex gap-2 overflow-x-auto px-5 py-3 border-b border-gray-100">
              {images.map((src, i) => (
                <button key={i} onClick={() => setActiveImg(i)} className={`flex-shrink-0 rounded-md overflow-hidden border-2 transition-colors ${i === activeImg ? 'border-gray-900' : 'border-transparent'}`}>
                  <img src={src} alt={`Thumb ${i + 1}`} className="w-16 h-12 object-cover" />
                </button>
              ))}
            </div>
          )}

          <div className="p-5 space-y-5">
            <div>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h1 className="text-xl font-bold text-gray-900 leading-tight">{title}</h1>
                  {address && <p className="text-sm text-gray-500 mt-0.5">{address}</p>}
                  {property.property_type && (
                    <span className="inline-block mt-1.5 text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full font-medium">
                      {typeLabel(property.property_type)}
                    </span>
                  )}
                </div>
                {rent && (
                  <div className="flex-shrink-0 text-right">
                    <p className="text-2xl font-bold text-gray-900">{rent}</p>
                  </div>
                )}
              </div>
            </div>

            <div className="grid grid-cols-4 gap-2">
              <StatPill label="Bedrooms" value={property.bedrooms != null ? `${property.bedrooms} bd` : null} />
              <StatPill label="Bathrooms" value={property.bathrooms != null ? `${property.bathrooms} ba` : null} />
              <StatPill label="Sq Ft" value={property.square_footage ? property.square_footage.toLocaleString() : null} />
              <StatPill label="Year Built" value={property.year_built} />
            </div>

            <div className="grid grid-cols-2 gap-3 text-sm">
              {property.available_date && (
                <div>
                  <p className="text-xs text-gray-500 font-medium mb-0.5">Available</p>
                  <p className="text-gray-800">{new Date(property.available_date).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}</p>
                </div>
              )}
              {property.security_deposit && (
                <div>
                  <p className="text-xs text-gray-500 font-medium mb-0.5">Security Deposit</p>
                  <p className="text-gray-800">${Number(property.security_deposit).toLocaleString()}</p>
                </div>
              )}
              {leaseTerms.length > 0 && (
                <div>
                  <p className="text-xs text-gray-500 font-medium mb-0.5">Lease Terms</p>
                  <p className="text-gray-800">{leaseTerms.join(', ')}</p>
                </div>
              )}
              {property.minimum_lease_months && (
                <div>
                  <p className="text-xs text-gray-500 font-medium mb-0.5">Minimum Lease</p>
                  <p className="text-gray-800">{property.minimum_lease_months} month{property.minimum_lease_months !== 1 ? 's' : ''}</p>
                </div>
              )}
            </div>

            {property.description && (
              <div>
                <h2 className="text-sm font-semibold text-gray-700 mb-2">About this property</h2>
                <p className="text-sm text-gray-600 leading-relaxed whitespace-pre-line">{property.description}</p>
              </div>
            )}

            <div>
              <h2 className="text-sm font-semibold text-gray-700 mb-3">Features</h2>
              <div className="space-y-3">
                {amenities.length > 0 && (
                  <div>
                    <p className="text-xs text-gray-500 font-medium mb-1.5">Amenities</p>
                    <TagList items={amenities} color="blue" />
                  </div>
                )}
                {appliances.length > 0 && (
                  <div>
                    <p className="text-xs text-gray-500 font-medium mb-1.5">Appliances</p>
                    <TagList items={appliances} color="gray" />
                  </div>
                )}
                {utilities.length > 0 && (
                  <div>
                    <p className="text-xs text-gray-500 font-medium mb-1.5">Utilities Included</p>
                    <TagList items={utilities} color="green" />
                  </div>
                )}
                {flooring.length > 0 && (
                  <div>
                    <p className="text-xs text-gray-500 font-medium mb-1.5">Flooring</p>
                    <TagList items={flooring} color="gray" />
                  </div>
                )}
              </div>
            </div>

            <div>
              <h2 className="text-sm font-semibold text-gray-700 mb-3">Policies</h2>
              <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
                <div className="flex items-center gap-2">
                  <span className={`w-4 h-4 rounded-full flex items-center justify-center flex-shrink-0 text-xs ${property.pets_allowed ? 'bg-green-100 text-green-600' : 'bg-red-50 text-red-400'}`}>
                    {property.pets_allowed ? '✓' : '✕'}
                  </span>
                  <span className="text-gray-700">Pets {property.pets_allowed ? 'Allowed' : 'Not Allowed'}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`w-4 h-4 rounded-full flex items-center justify-center flex-shrink-0 text-xs ${property.smoking_allowed ? 'bg-green-100 text-green-600' : 'bg-red-50 text-red-400'}`}>
                    {property.smoking_allowed ? '✓' : '✕'}
                  </span>
                  <span className="text-gray-700">Smoking {property.smoking_allowed ? 'Allowed' : 'Not Allowed'}</span>
                </div>
                {property.has_basement && (
                  <div className="flex items-center gap-2">
                    <span className="w-4 h-4 rounded-full flex items-center justify-center flex-shrink-0 text-xs bg-blue-50 text-blue-500">✓</span>
                    <span className="text-gray-700">Basement</span>
                  </div>
                )}
                {property.has_central_air && (
                  <div className="flex items-center gap-2">
                    <span className="w-4 h-4 rounded-full flex items-center justify-center flex-shrink-0 text-xs bg-blue-50 text-blue-500">✓</span>
                    <span className="text-gray-700">Central Air</span>
                  </div>
                )}
                {property.pets_allowed && petTypes.length > 0 && (
                  <div className="col-span-2 text-xs text-gray-500 pl-6">
                    {petTypes.join(', ')}{property.pet_weight_limit ? ` — max ${property.pet_weight_limit} lbs` : ''}
                  </div>
                )}
              </div>
            </div>

            <div className="grid grid-cols-3 gap-3 text-sm">
              {property.heating_type && (
                <div>
                  <p className="text-xs text-gray-500 font-medium mb-0.5">Heating</p>
                  <p className="text-gray-800">{property.heating_type}</p>
                </div>
              )}
              {property.cooling_type && (
                <div>
                  <p className="text-xs text-gray-500 font-medium mb-0.5">Cooling</p>
                  <p className="text-gray-800">{property.cooling_type}</p>
                </div>
              )}
              {property.laundry_type && (
                <div>
                  <p className="text-xs text-gray-500 font-medium mb-0.5">Laundry</p>
                  <p className="text-gray-800">{property.laundry_type}</p>
                </div>
              )}
              {property.parking && (
                <div>
                  <p className="text-xs text-gray-500 font-medium mb-0.5">Parking</p>
                  <p className="text-gray-800">{property.parking}</p>
                </div>
              )}
            </div>

            {property.showing_instructions && (
              <div className="bg-amber-50 border border-amber-100 rounded-lg px-4 py-3">
                <p className="text-xs font-semibold text-amber-800 mb-0.5">Showing Instructions</p>
                <p className="text-sm text-amber-700">{property.showing_instructions}</p>
              </div>
            )}

            {property.move_in_special && (
              <div className="bg-green-50 border border-green-100 rounded-lg px-4 py-3">
                <p className="text-xs font-semibold text-green-800 mb-0.5">Move-in Special</p>
                <p className="text-sm text-green-700">{property.move_in_special}</p>
              </div>
            )}
          </div>
        </div>

        <div className="px-5 py-3 border-t border-gray-100 flex justify-end">
          <button
            onClick={onClose}
            className="text-sm font-medium text-gray-600 hover:text-gray-900 px-4 py-2 rounded-lg hover:bg-gray-100 transition-colors"
          >
            Close Preview
          </button>
        </div>
      </div>
    </div>
  )
}
