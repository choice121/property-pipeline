import { useRef } from 'react'
import { selectHaptic } from './haptics'

/**
 * Returns handlers you can spread onto any element to detect long-press
 * (default 450ms hold). Calls onLongPress on release if held long enough.
 * Cancels on movement greater than 10px.
 */
export function useLongPress(onLongPress, { delay = 450 } = {}) {
  const timerRef = useRef(null)
  const startPos = useRef(null)
  const fired = useRef(false)

  function clear() {
    if (timerRef.current) {
      clearTimeout(timerRef.current)
      timerRef.current = null
    }
  }

  function start(e) {
    fired.current = false
    const t = e.touches?.[0] || e
    startPos.current = { x: t.clientX, y: t.clientY }
    timerRef.current = setTimeout(() => {
      fired.current = true
      selectHaptic()
      onLongPress(e)
    }, delay)
  }

  function move(e) {
    if (!startPos.current) return
    const t = e.touches?.[0] || e
    const dx = Math.abs(t.clientX - startPos.current.x)
    const dy = Math.abs(t.clientY - startPos.current.y)
    if (dx > 10 || dy > 10) clear()
  }

  function end() {
    clear()
    startPos.current = null
  }

  return {
    onTouchStart: start,
    onTouchMove: move,
    onTouchEnd: end,
    onTouchCancel: end,
    onMouseDown: start,
    onMouseMove: move,
    onMouseUp: end,
    onMouseLeave: end,
    didFire: () => fired.current,
  }
}
