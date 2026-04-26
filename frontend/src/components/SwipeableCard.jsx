import { useRef, useState } from 'react'

/**
 * Wraps a card so the user can swipe left to reveal action buttons.
 * Tap on the card surface still propagates to the inner content.
 *
 * Props:
 *   actions: [{ icon, label, color, onClick }]
 *   children
 */
export default function SwipeableCard({ actions = [], children, disabled = false }) {
  const [offset, setOffset] = useState(0)
  const [dragging, setDragging] = useState(false)
  const startX = useRef(null)
  const startOffset = useRef(0)
  const moved = useRef(false)

  const maxReveal = Math.min(actions.length, 2) * 80

  function onTouchStart(e) {
    if (disabled) return
    startX.current = e.touches[0].clientX
    startOffset.current = offset
    moved.current = false
    setDragging(true)
  }

  function onTouchMove(e) {
    if (startX.current == null) return
    const dx = e.touches[0].clientX - startX.current
    const next = Math.max(-maxReveal - 30, Math.min(0, startOffset.current + dx))
    if (Math.abs(dx) > 6) moved.current = true
    setOffset(next)
  }

  function onTouchEnd() {
    if (startX.current == null) return
    setDragging(false)
    if (offset < -maxReveal / 2) setOffset(-maxReveal)
    else setOffset(0)
    startX.current = null
  }

  function close() { setOffset(0) }

  function handleAction(e, action) {
    e.stopPropagation()
    close()
    action.onClick?.()
  }

  return (
    <div className="relative swipe-track overflow-hidden rounded-lg">
      {/* Action drawer */}
      {actions.length > 0 && (
        <div className="absolute inset-y-0 right-0 flex" style={{ width: maxReveal }}>
          {actions.slice(0, 2).map((a, i) => (
            <button
              key={i}
              onClick={(e) => handleAction(e, a)}
              className={`flex-1 flex flex-col items-center justify-center text-white text-[11px] font-semibold gap-1 ${a.color || 'bg-gray-800'}`}
            >
              {a.icon}
              {a.label}
            </button>
          ))}
        </div>
      )}

      <div
        className={`swipe-content ${dragging ? 'dragging' : ''} relative bg-white`}
        style={{ transform: `translateX(${offset}px)` }}
        onTouchStart={onTouchStart}
        onTouchMove={onTouchMove}
        onTouchEnd={onTouchEnd}
        onClick={(e) => {
          // If the user just swiped, swallow the click so we don't navigate
          if (moved.current) {
            e.stopPropagation()
            e.preventDefault()
            moved.current = false
          }
        }}
      >
        {children}
      </div>
    </div>
  )
}
