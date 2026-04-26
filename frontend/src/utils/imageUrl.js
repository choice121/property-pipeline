const PROXY_DOMAINS = [
  'rdcpix.com',
  'realtor.com',
  'zillowstatic.com',
  'zillow.com',
  'cdn-redfin.com',
  'redfin.com',
  'trulia.com',
  'cloudinary.com',
  'amazonaws.com',
]

const IMAGEKIT_ENDPOINT =
  (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_IMAGEKIT_URL_ENDPOINT) ||
  ''

function isImageKit(url) {
  if (!url) return false
  return url.includes('ik.imagekit.io') || (IMAGEKIT_ENDPOINT && url.startsWith(IMAGEKIT_ENDPOINT))
}

function needsProxy(url) {
  if (!url || !url.startsWith('http')) return false
  try {
    const hostname = new URL(url).hostname
    return PROXY_DOMAINS.some((d) => hostname.endsWith(d))
  } catch {
    return false
  }
}

export function resolveImageUrl(url) {
  if (!url) return url

  if (url.startsWith('storage/images/')) {
    const parts = url.replace('storage/images/', '').split('/')
    return `/api/images/${parts.join('/')}`
  }

  if (url.startsWith('/api/') || url.startsWith('/storage/')) {
    return url
  }

  if (needsProxy(url)) {
    return `/api/proxy-image?url=${encodeURIComponent(url)}`
  }

  return url
}

export function resolveImageUrls(urls) {
  if (!Array.isArray(urls)) return []
  return urls.map(resolveImageUrl)
}

/**
 * Add ImageKit transformations to a URL.
 * Falls back to the plain URL when the source is not an ImageKit asset.
 *
 * Common preset usage:
 *   transformImage(url, { w: 400, q: 70 })
 *   transformImage(url, { w: 800, h: 600, c: 'maintain_ratio' })
 */
export function transformImage(url, opts = {}) {
  if (!url) return url
  if (!isImageKit(url)) return url
  const params = []
  if (opts.w) params.push(`w-${opts.w}`)
  if (opts.h) params.push(`h-${opts.h}`)
  if (opts.q) params.push(`q-${opts.q}`)
  if (opts.dpr) params.push(`dpr-${opts.dpr}`)
  if (opts.c) params.push(`c-${opts.c}`)
  params.push(`f-${opts.f || 'auto'}`)
  params.push(`pr-true`) // progressive
  const tr = params.join(',')
  const sep = url.includes('?') ? '&' : '?'
  return `${url}${sep}tr=${tr}`
}

/**
 * Returns a srcSet string for responsive images.
 * Only emits transformations for ImageKit assets; otherwise returns null.
 */
export function imageSrcSet(url, widths = [320, 480, 640, 960, 1280], opts = {}) {
  if (!isImageKit(url)) return null
  return widths
    .map((w) => `${transformImage(url, { ...opts, w })} ${w}w`)
    .join(', ')
}

/**
 * One-call helper that returns { src, srcSet } for any property image url.
 * Resolves through the proxy/local-storage layer first, then layers
 * ImageKit transforms on top when applicable.
 */
export function responsiveImage(url, { width = 640, sizes = [320, 480, 640, 960, 1280], q = 70 } = {}) {
  if (!url) return { src: null, srcSet: null }
  const resolved = resolveImageUrl(url)
  if (!isImageKit(resolved)) {
    return { src: resolved, srcSet: null }
  }
  return {
    src: transformImage(resolved, { w: width, q }),
    srcSet: imageSrcSet(resolved, sizes, { q }),
  }
}
