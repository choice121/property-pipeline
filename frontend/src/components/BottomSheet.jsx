import { useEffect, useRef, useState } from 'react'

/**
 * Mobile bottom sheet with swipe-down-to-dismiss.
 * On screens >= sm, falls back to a centered modal-like panel.
 *
 * Props:
 *   open: boolean
 *   onClose: () => void
 *   title: string
 *   children: ReactNode
 *   maxHeightVh: number  // default 85
 *   desktopMode: 'modal' | 'inline'  // default 'modal' on sm+
 */
export default function BottomSheet({ open, onClose, title, children, maxHeightVh = 85, desktopMode = 'modal' }) {
  const sheetRef = useRef(null)
  const [dragY, setDragY] = useState(0)
  const startY = useRef(null)
  const startScrollTop = useRef(0)

  useEffect(() => {
    if (!open) return
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = prev }
  }, [open])

  useEffect(() => {
    if (!open) return
    function onKey(e) { if (e.key === 'Escape') onClose?.() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  function onTouchStart(e) {
    const scroller = sheetRef.current?.querySelector('[data-sheet-scroller]')
    startScrollTop.current = scroller ? scroller.scrollTop : 0
    if (startScrollTop.current > 0) return
    startY.current = e.touches[0].clientY
  }

  function onTouchMove(e) {
    if (startY.current == null) return
    const dy = e.touches[0].clientY - startY.current
    if (dy > 0) setDragY(dy)
  }

  function onTouchEnd() {
    if (startY.current == null) return
    if (dragY > 120) {
      onClose?.()
    }
    setDragY(0)
    startY.current = null
  }

  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-[60] flex items-end sm:items-center sm:justify-center"
      onClick={onClose}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/50 transition-opacity" />

      {/* Sheet */}
      <div
        ref={sheetRef}
        onClick={(e) => e.stopPropagation()}
        onTouchStart={onTouchStart}
        onTouchMove={onTouchMove}
        onTouchEnd={onTouchEnd}
        style={{
          transform: dragY ? `translateY(${dragY}px)` : undefined,
          transition: dragY ? 'none' : 'transform 0.25s ease-out',
          maxHeight: `${maxHeightVh}vh`,
        }}
        className={`
          relative w-full sm:max-w-2xl sm:w-[640px]
          bg-white rounded-t-2xl sm:rounded-2xl shadow-2xl
          flex flex-col overflow-hidden
          animate-slide-up
        `}
      >
        {/* Drag handle */}
        <div className="sm:hidden pt-2 pb-1 flex justify-center">
          <div className="w-10 h-1.5 rounded-full bg-gray-300" />
        </div>

        {/* Header */}
        {title && (
          <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
            <h3 className="text-base font-semibold text-gray-900">{title}</h3>
            <button
              onClick={onClose}
              aria-label="Close"
              className="touch-target -mr-2 text-gray-400 hover:text-gray-700 active:scale-95 transition-all"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        )}

        {/* Scrollable content */}
        <div
          data-sheet-scroller
          className="flex-1 overflow-y-auto overscroll-contain"
          style={{ paddingBottom: 'max(env(safe-area-inset-bottom, 0px), 16px)' }}
        >
          {children}
        </div>
      </div>
    </div>
  )
}
