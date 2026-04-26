const STORAGE_KEY = 'pp_favorites_v1'
const EVENT = 'pp:favorites-changed'

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
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(entries))
    window.dispatchEvent(new CustomEvent(EVENT))
  } catch {
    /* ignore */
  }
}

export function getFavorites() {
  return readRaw().sort((a, b) => b.ts - a.ts)
}

export function getFavoriteIdSet() {
  return new Set(readRaw().map((e) => String(e.id)))
}

export function isFavorite(id) {
  if (id == null) return false
  const key = String(id)
  return readRaw().some((e) => String(e.id) === key)
}

export function toggleFavorite(id) {
  if (id == null) return false
  const key = String(id)
  const list = readRaw()
  const idx = list.findIndex((e) => String(e.id) === key)
  if (idx >= 0) {
    list.splice(idx, 1)
    writeRaw(list)
    return false
  }
  list.unshift({ id, ts: Date.now() })
  writeRaw(list)
  return true
}

export function removeFavorite(id) {
  const key = String(id)
  writeRaw(readRaw().filter((e) => String(e.id) !== key))
}

export function clearFavorites() {
  writeRaw([])
}

export const FAVORITES_EVENT = EVENT
