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
