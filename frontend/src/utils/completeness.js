function hasImages(property) {
  try {
    const local = JSON.parse(property.local_image_paths || '[]')
    if (local.length > 0) return true
  } catch {}
  try {
    const live = JSON.parse(property.photo_urls || '[]')
    if (live.length > 0) return true
  } catch {}
  if (property.original_image_urls) {
    try {
      const orig = JSON.parse(property.original_image_urls || '[]')
      if (orig.length > 0) return true
    } catch {}
  }
  return false
}

const CHECKS = [
  { label: 'Address',        weight: 12, fn: p => !!(p.address) },
  { label: 'Monthly rent',   weight: 12, fn: p => p.monthly_rent != null },
  { label: 'Bedrooms',       weight: 10, fn: p => p.bedrooms != null },
  { label: 'Bathrooms',      weight: 10, fn: p => p.bathrooms != null },
  { label: 'Description',    weight: 12, fn: p => !!(p.description && p.description.length > 20) },
  { label: 'Photos',         weight: 12, fn: p => hasImages(p) },
  { label: 'City / State / Zip', weight: 8, fn: p => !!(p.city && p.state && p.zip) },
  { label: 'Square footage', weight: 6,  fn: p => p.square_footage != null },
  { label: 'Available date', weight: 6,  fn: p => !!(p.available_date) },
  { label: 'Amenities',      weight: 6,  fn: p => !!(p.amenities) },
  { label: 'Pet policy',     weight: 6,  fn: p => p.pets_allowed != null },
]

const TOTAL_WEIGHT = CHECKS.reduce((sum, c) => sum + c.weight, 0)

export function computeCompleteness(property) {
  let earned = 0
  const missing = []

  for (const check of CHECKS) {
    if (check.fn(property)) {
      earned += check.weight
    } else {
      missing.push(check.label)
    }
  }

  const score = Math.round((earned / TOTAL_WEIGHT) * 100)
  return { score, missing }
}

export function completenessColor(score) {
  if (score >= 90) return { bar: '#22c55e', text: '#15803d' }
  if (score >= 70) return { bar: '#3b82f6', text: '#1d4ed8' }
  if (score >= 40) return { bar: '#f59e0b', text: '#b45309' }
  return { bar: '#ef4444', text: '#b91c1c' }
}
