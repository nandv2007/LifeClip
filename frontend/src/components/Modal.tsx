// Accessible modal: backdrop dismiss, Escape to close, focus moved inside,
// scroll locked while open.

import { useEffect, useRef } from 'react'
import type { ReactNode } from 'react'
import { createPortal } from 'react-dom'

interface ModalProps {
  title: string
  children: ReactNode
  onClose: () => void
  footer?: ReactNode
}

export function Modal({ title, children, onClose, footer }: ModalProps) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null
    document.body.style.overflow = 'hidden'
    ref.current?.focus()

    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
      if (e.key === 'Tab' && ref.current) {
        // Minimal focus trap
        const focusables = ref.current.querySelectorAll<HTMLElement>(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
        )
        if (focusables.length === 0) return
        const first = focusables[0]
        const last = focusables[focusables.length - 1]
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault()
          last.focus()
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault()
          first.focus()
        }
      }
    }
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = ''
      previous?.focus()
    }
  }, [onClose])

  return createPortal(
    <div
      className="modal-backdrop"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
        ref={ref}
        tabIndex={-1}
      >
        <h2 className="h2" id="modal-title" style={{ fontSize: 19 }}>
          {title}
        </h2>
        <div style={{ marginTop: 10, color: 'var(--ink-2)' }}>{children}</div>
        {footer && <div style={{ marginTop: 22, display: 'flex', gap: 10, flexDirection: 'column' }}>{footer}</div>}
      </div>
    </div>,
    document.body,
  )
}
