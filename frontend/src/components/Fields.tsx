// Confidence indicator + editable extracted-field row.

import { useState } from 'react'
import { Icon } from './Icon'
import type { FieldOut } from '../lib/types'

export function Confidence({ value, edited }: { value: number; edited?: boolean }) {
  if (edited) {
    return <span className="chip chip--ok" style={{ height: 22, padding: '0 8px', fontSize: 12 }}>Confirmed by you</span>
  }
  const dots = value >= 0.75 ? 3 : value >= 0.5 ? 2 : 1
  return (
    <span className="conf-dots" role="img" aria-label={`Confidence ${dots} of 3`}>
      <i className={dots >= 1 ? 'on' : ''} />
      <i className={dots >= 2 ? 'on' : ''} />
      <i className={dots >= 3 ? 'on' : ''} />
      {value < 0.55 && <span className="conf-low">Please confirm</span>}
    </span>
  )
}

interface FieldRowProps {
  field: FieldOut
  onSave: (field: FieldOut, value: string) => Promise<void>
}

export function FieldRow({ field, onSave }: FieldRowProps) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(field.value)
  const [saving, setSaving] = useState(false)
  const multiline = field.value.includes('\n') || field.value.length > 60

  const save = async () => {
    setSaving(true)
    try {
      await onSave(field, draft)
      setEditing(false)
    } finally {
      setSaving(false)
    }
  }

  if (editing) {
    return (
      <div className="field-row" style={{ alignItems: 'stretch' }}>
        <span className="field-row__label">{field.label || field.name}</span>
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 8 }}>
          {multiline ? (
            <textarea
              className="textarea"
              style={{ minHeight: 90 }}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              aria-label={`Edit ${field.label || field.name}`}
            />
          ) : (
            <input
              className="input"
              style={{ minHeight: 46 }}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              aria-label={`Edit ${field.label || field.name}`}
              autoFocus
              onKeyDown={(e) => {
                if (e.key === 'Enter') void save()
                if (e.key === 'Escape') setEditing(false)
              }}
            />
          )}
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="btn btn--sm" onClick={() => void save()} disabled={saving}>
              {saving ? 'Saving…' : 'Save'}
            </button>
            <button className="btn btn--sm btn--ghost" onClick={() => { setEditing(false); setDraft(field.value) }} disabled={saving}>
              Cancel
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="field-row">
      <span className="field-row__label">{field.label || field.name}</span>
      <div className="field-row__value">
        {field.value || <em className="micro">Not detected</em>}
        <div className="field-row__conf">
          <Confidence value={field.confidence} edited={field.user_edited} />
        </div>
      </div>
      <button
        className="field-row__edit"
        onClick={() => { setDraft(field.value); setEditing(true) }}
        aria-label={`Edit ${field.label || field.name}`}
        title="Edit this value"
      >
        <Icon name="pencil" size={16} />
      </button>
    </div>
  )
}
