export function SkeletonBox({ className = '' }) {
  return <div className={`animate-pulse bg-gray-200 rounded ${className}`} />
}

export function SkeletonCard() {
  return (
    <div className="bg-white rounded-lg border border-gray-100 overflow-hidden shadow-sm">
      <div className="w-full h-48 bg-gray-200 animate-pulse" />
      <div className="p-4 space-y-3">
        <div className="h-5 w-2/5 bg-gray-200 rounded animate-pulse" />
        <div className="h-4 w-4/5 bg-gray-200 rounded animate-pulse" />
        <div className="h-3 w-3/5 bg-gray-200 rounded animate-pulse" />
        <div className="flex gap-3 pt-1">
          <div className="h-3 w-10 bg-gray-200 rounded animate-pulse" />
          <div className="h-3 w-10 bg-gray-200 rounded animate-pulse" />
          <div className="h-3 w-14 bg-gray-200 rounded animate-pulse" />
        </div>
        <div className="h-1.5 w-full bg-gray-200 rounded-full animate-pulse mt-2" />
      </div>
    </div>
  )
}

export function SkeletonRow() {
  return (
    <div className="bg-white rounded-lg border border-gray-100 p-4 flex items-center gap-3">
      <div className="w-12 h-12 bg-gray-200 rounded animate-pulse flex-shrink-0" />
      <div className="flex-1 space-y-2">
        <div className="h-4 w-3/5 bg-gray-200 rounded animate-pulse" />
        <div className="h-3 w-2/5 bg-gray-200 rounded animate-pulse" />
      </div>
    </div>
  )
}
