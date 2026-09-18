// History: only media the user explicitly submitted. Search + category filter.

import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../lib/api'
import type { Category, ClipListItem } from '../lib/types'
import { CATEGORY_LABELS } from '../lib/types'
import { Icon } from '../components/Icon'
import { ClipCard, EmptyState } from '../components/Clips'

const FILTERS: Array<{ key: Category | ''; label: string }> = [
  { key: '', label: 'All' },
  { key: 'event', label: 'Events' },
  { key: 'receipt', label: 'Receipts' },
  { key: 'ticket', label: 'Tickets' },
  { key: 'notes', label: 'Notes' },
  { key: 'menu', label: 'Menus' },
  { key: 'product', label: 'Products' },
  { key: 'document', label: 'Documents' },
  { key: 'other', label: 'Other' },
]

export default function HistoryScreen() {
  const [clips, setClips] = useState<ClipListItem[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [q, setQ] = useState('')
  const [category, setCategory] = useState<Category | ''>('')
  const debounceRef = useRef<number | null>(null)

  const load = useCallback(async (query: string, cat: string) => {
    try {
      const data = await api.listClips({ q: query || undefined, category: cat || undefined })
      setClips(data)
      setError(null)
    } catch (err) {
      setError((err as Error).message)
      setClips([])
    }
  }, [])

  useEffect(() => {
    if (debounceRef.current) window.clearTimeout(debounceRef.current)
    debounceRef.current = window.setTimeout(() => void load(q, category), 220)
    return () => {
      if (debounceRef.current) window.clearTimeout(debounceRef.current)
    }
  }, [q, category, load])

  return (
    <div className="stack-lg" style={{ paddingTop: 26 }}>
      <header>
        <h1 className="h1" style={{ fontSize: 'clamp(24px, 5.6vw, 30px)' }}>History</h1>
        <p className="lede" style={{ fontSize: 15 }}>
          Only photos you intentionally analyzed — never anything else from your device.
        </p>
      </header>

      <div className="stack">
        <div className="search-input">
          <Icon name="search" size={19} />
          <input
            className="input"
            type="search"
            placeholder="Search your LifeClips…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            aria-label="Search your LifeClips"
          />
        </div>
        <div className="chip-row" role="group" aria-label="Filter by category">
          {FILTERS.map((f) => (
            <button
              key={f.label}
              className="filter-chip"
              aria-pressed={category === f.key}
              onClick={() => setCategory(f.key)}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="banner banner--error">
          <Icon name="alert" size={18} />
          <span>{error}</span>
        </div>
      )}

      {clips === null ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: 40 }}>
          <span className="spinner" aria-label="Loading history" />
        </div>
      ) : clips.length === 0 ? (
        <div className="card">
          <EmptyState
            title={q || category ? 'No matches' : 'No LifeClips yet'}
            body={
              q || category
                ? 'Try a different search or filter.'
                : 'Capture a poster, receipt or note to get started — it will appear here.'
            }
          >
            {!q && !category && (
              <Link to="/capture?mode=camera" className="btn">
                <Icon name="camera" size={19} />
                Capture something
              </Link>
            )}
          </EmptyState>
        </div>
      ) : (
        <div className="clips-grid" role="list">
          {clips.map((clip) => (
            <ClipCard key={clip.id} clip={clip} />
          ))}
        </div>
      )}
    </div>
  )
}
