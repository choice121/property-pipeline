import { useEffect, useRef, useState } from 'react'

/**
 * Pull-to-refresh wrapper. Triggers `onRefresh()` when the user
 * pulls down past the threshold from the top of the page.
 * Only active on touch devices.
 */
export default function PullToRefresh({ onRefresh, children, threshold = 70 }) {
  const [pull, setPull] = useState(0)
  const [refreshing, setRefreshing] = useState(false)
  const startY = useRef(null)
  const triggered = useRef(false)

  useEffect(() => {
    function onTouchStart(e) {
      if (window.scrollY > 0) return
      startY.current = e.touches[0].clientY
      triggered.current = false
    }
    function onTouchMove(e) {
      if (startY.current == null || refreshing) return
      const dy = e.touches[0].clientY - startY.current
      if (dy > 0 && window.scrollY <= 0) {
        // Resistance curve
        const resisted = Math.min(160, dy * 0.5)
        setPull(resisted)
        if (resisted > threshold && !triggered.current) {
          triggered.current = true
          if (navigator.vibrate) navigator.vibrate(8)
        }
      }
    }
    async function onTouchEnd() {
      if (startY.current == null) return
      const shouldFire = triggered.current
      startY.current = null
      triggered.current = false
      if (shouldFire) {
        setRefreshing(true)
        setPull(threshold)
        try { await onRefresh?.() } catch {}
        setRefreshing(false)
      }
      setPull(0)
    }
    window.addEventListener('touchstart', onTouchStart, { passive: true })
    window.addEventListener('touchmove', onTouchMove, { passive: true })
    window.addEventListener('touchend', onTouchEnd, { passive: true })
    return () => {
      window.removeEventListener('touchstart', onTouchStart)
      window.removeEventListener('touchmove', onTouchMove)
      window.removeEventListener('touchend', onTouchEnd)
    }
  }, [onRefresh, threshold, refreshing])

  return (
    <div className="relative">
      <div
        className="pointer-events-none flex items-center justify-center text-gray-500 text-xs font-medium overflow-hidden"
        style={{
          height: pull,
          transition: pull === 0 ? 'height 0.25s ease-out' : 'none',
        }}
      >
        {pull > 0 && (
          <div className="flex items-center gap-2">
            <svg
              className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`}
              style={{ transform: refreshing ? undefined : `rotate(${Math.min(180, pull * 2.5)}deg)` }}
              fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"
            >
              {refreshing
                ? <><circle className="opacity-25" cx="12" cy="12" r="10" strokeWidth="4"/><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/></>
                : <path strokeLinecap="round" strokeLinejoin="round" d="M19 14l-7 7m0 0l-7-7m7 7V3" />
              }
            </svg>
            <span>{refreshing ? 'Refreshing…' : pull > threshold ? 'Release to refresh' : 'Pull to refresh'}</span>
          </div>
        )}
      </div>
      {children}
    </div>
  )
}
