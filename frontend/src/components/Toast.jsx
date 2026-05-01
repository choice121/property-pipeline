import { useState, useEffect, useCallback, createContext, useContext, useRef } from 'react'

const ToastContext = createContext(null)

let _addToast = null

export function useToast() {
  const ctx = useContext(ToastContext)
  if (ctx) return ctx
  return {
    toast: (msg, type) => {
      if (_addToast) _addToast(msg, type)
      else console.warn('[Toast]', type, msg)
    }
  }
}

function ToastItem({ id, message, type, onRemove }) {
  useEffect(() => {
    const t = setTimeout(() => onRemove(id), type === 'error' ? 6000 : 3500)
    return () => clearTimeout(t)
  }, [id, type, onRemove])

  const colors = {
    error:   'bg-red-600 text-white',
    warning: 'bg-amber-500 text-white',
    success: 'bg-green-600 text-white',
    info:    'bg-gray-800 text-white',
  }
  const icons = {
    error:   '✕',
    warning: '⚠',
    success: '✓',
    info:    'ℹ',
  }

  return (
    <div
      className={`flex items-start gap-2 px-4 py-3 rounded-lg shadow-lg text-sm max-w-xs pointer-events-auto ${colors[type] || colors.info}`}
      role="alert"
    >
      <span className="font-bold mt-0.5 shrink-0">{icons[type] || icons.info}</span>
      <span className="flex-1 leading-snug">{message}</span>
      <button
        className="ml-1 opacity-70 hover:opacity-100 shrink-0 touch-target"
        onClick={() => onRemove(id)}
        aria-label="Dismiss"
      >✕</button>
    </div>
  )
}

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])
  const counterRef = useRef(0)

  const addToast = useCallback((message, type = 'info') => {
    const id = ++counterRef.current
    setToasts(prev => [...prev.slice(-4), { id, message, type }])
  }, [])

  const removeToast = useCallback((id) => {
    setToasts(prev => prev.filter(t => t.id !== id))
  }, [])

  useEffect(() => {
    _addToast = addToast
    return () => { _addToast = null }
  }, [addToast])

  const ctx = {
    toast: addToast,
    success: (msg) => addToast(msg, 'success'),
    error: (msg) => addToast(msg, 'error'),
    warning: (msg) => addToast(msg, 'warning'),
    info: (msg) => addToast(msg, 'info'),
  }

  return (
    <ToastContext.Provider value={ctx}>
      {children}
      <div
        className="fixed bottom-20 left-1/2 -translate-x-1/2 z-50 flex flex-col gap-2 items-center pointer-events-none w-screen px-4"
        style={{ maxWidth: '100vw' }}
        aria-live="polite"
        aria-atomic="false"
      >
        {toasts.map(t => (
          <ToastItem key={t.id} {...t} onRemove={removeToast} />
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function showToast(message, type = 'info') {
  if (_addToast) _addToast(message, type)
}
