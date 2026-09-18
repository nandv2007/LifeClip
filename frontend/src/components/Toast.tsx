// Toast context — short-lived, friendly feedback, announced to screen readers.

import { createContext, useCallback, useContext, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { Icon } from './Icon'

interface ToastItem {
  id: number
  message: string
  kind: 'ok' | 'error'
}

const ToastContext = createContext<{
  toast: (message: string, kind?: 'ok' | 'error') => void
}>({ toast: () => {} })

export function useToast() {
  return useContext(ToastContext)
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([])
  const nextId = useRef(1)

  const toast = useCallback((message: string, kind: 'ok' | 'error' = 'ok') => {
    const id = nextId.current++
    setItems((prev) => [...prev.slice(-2), { id, message, kind }])
    window.setTimeout(() => {
      setItems((prev) => prev.filter((t) => t.id !== id))
    }, 3600)
  }, [])

  const value = useMemo(() => ({ toast }), [toast])

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="toast-region" role="status" aria-live="polite">
        {items.map((t) => (
          <div key={t.id} className={`toast${t.kind === 'error' ? ' toast--error' : ''}`}>
            <Icon name={t.kind === 'error' ? 'alert' : 'check'} size={19} />
            <span>{t.message}</span>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}
