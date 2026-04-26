const STORAGE_KEY = 'pp_recently_viewed_v1'
const MAX_ENTRIES = 30
const DEFAULT_MAX_AGE_MS = 24 * 60 * 60 * 1000

function readRaw() {
  if (typeof window === 'undefined') return []
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed.filter(
      (e) => e && (typeof e.id === 'number' || typeof e.id === 'string') && typeof e.ts === 'number',
    )
  } catch {
    return []
  }
}

function writeRaw(entries) {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(entries.slice(0, MAX_ENTRIES)))
    window.dispatchEvent(new CustomEvent('pp:recently-viewed-changed'))
  } catch {
    /* quota or disabled storage — ignore */
  }
}

export function markViewed(id) {
  if (id == null) return
  const key = String(id)
  const now = Date.now()
  const existing = readRaw().filter((e) => String(e.id) !== key)
  existing.unshift({ id, ts: now })
  writeRaw(existing)
}

export function getRecentlyViewed({ maxAgeMs = DEFAULT_MAX_AGE_MS, limit = MAX_ENTRIES } = {}) {
  const cutoff = Date.now() - maxAgeMs
  return readRaw()
    .filter((e) => e.ts >= cutoff)
    .sort((a, b) => b.ts - a.ts)
    .slice(0, limit)
}

export function clearRecentlyViewed() {
  writeRaw([])
}

export function removeRecentlyViewed(id) {
  const key = String(id)
  writeRaw(readRaw().filter((e) => String(e.id) !== key))
}
