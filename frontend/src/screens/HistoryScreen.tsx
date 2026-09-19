// Smart document library: only files the user explicitly chose or captured.

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../lib/api'
import type { Category, ClipListItem } from '../lib/types'
import { Icon } from '../components/Icon'
import { ClipCard, EmptyState } from '../components/Clips'

const FILTERS: Array<{ key: string; label: string; category?: Category }> = [
  { key: 'all', label: 'All' },
  { key: 'notes', label: 'Notes', category: 'notes' },
  { key: 'receipts', label: 'Receipts', category: 'receipt' },
  { key: 'tickets', label: 'Tickets', category: 'ticket' },
  { key: 'events', label: 'Events', category: 'event' },
  { key: 'menus', label: 'Menus', category: 'menu' },
  { key: 'products', label: 'Products', category: 'product' },
  { key: 'documents', label: 'Documents', category: 'document' },
  { key: 'other', label: 'Other', category: 'other' },
]

export default function HistoryScreen() {
  const [clips, setClips] = useState<ClipListItem[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [q, setQ] = useState('')
  const [filter, setFilter] = useState('all')
  const debounceRef = useRef<number | null>(null)
  const selected = useMemo(() => FILTERS.find((item) => item.key === filter) ?? FILTERS[0], [filter])

  const load = useCallback(async (query: string, current: typeof selected) => {
    try {
      const data = await api.listClips({
        q: query || undefined,
        category: current.category,
      })
      setClips(data)
      setError(null)
    } catch (err) {
      setError((err as Error).message)
      setClips([])
    }
  }, [])

  useEffect(() => {
    if (debounceRef.current) window.clearTimeout(debounceRef.current)
    debounceRef.current = window.setTimeout(() => void load(q, selected), 220)
    return () => {
      if (debounceRef.current) window.clearTimeout(debounceRef.current)
    }
  }, [q, selected, load])

  const readyCount = clips?.filter((clip) => clip.status === 'ready').length ?? 0
  const reviewCount = clips?.filter((clip) => clip.status === 'partial' || clip.status === 'failed').length ?? 0

  return (
    <div className="library-page" style={{ paddingTop: 30 }}>
      <header className="library-hero">
        <div>
          <span className="eyebrow">SMART LIBRARY</span>
          <h1 className="h1">Everything you captured,<br />ready when you need it.</h1>
          <p className="lede">Search the filename, notes, OCR text, tags, subjects, topics and extracted details.</p>
        </div>
        <Link to="/capture?mode=file" className="btn library-add">
          <Icon name="plus" size={19} /> Add document
        </Link>
      </header>

      <div className="library-stats" aria-label="Library summary">
        <div><strong>{clips?.length ?? '—'}</strong><span>Shown</span></div>
        <div><strong>{readyCount}</strong><span>Ready</span></div>
        <div><strong>{reviewCount}</strong><span>Needs review</span></div>
      </div>

      <div className="library-controls">
        <div className="search-input library-search">
          <Icon name="search" size={19} />
          <input
            className="input"
            type="search"
            placeholder="Search every document…"
            value={q}
            onChange={(event) => setQ(event.target.value)}
            aria-label="Search filenames, text, tags, subjects and details"
          />
        </div>
        <div className="library-tabs" role="tablist" aria-label="Document collections">
          {FILTERS.map((item) => (
            <button
              key={item.key}
              role="tab"
              className="collection-tab"
              aria-selected={filter === item.key}
              onClick={() => setFilter(item.key)}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      {error && <div className="banner banner--error"><Icon name="alert" size={18} /><span>{error}</span></div>}

      {clips === null ? (
        <div className="library-loading"><span className="spinner" aria-label="Loading library" /></div>
      ) : clips.length === 0 ? (
        <div className="card">
          <EmptyState
            title={q || filter !== 'all' ? 'No matches here' : 'Your smart library is empty'}
            body={q || filter !== 'all' ? 'Try another search or collection.' : 'Choose or capture a photo. LifeClip only processes what you intentionally select.'}
          >
            {!q && filter === 'all' && <Link to="/capture?mode=file" className="btn"><Icon name="plus" size={18} />Add your first file</Link>}
          </EmptyState>
        </div>
      ) : (
        <section aria-label={`${selected.label} documents`}>
          <div className="library-results-head">
            <h2>{selected.label}</h2>
            <span>{clips.length} {clips.length === 1 ? 'item' : 'items'}</span>
          </div>
          <div className="clips-grid clips-grid--library" role="list">
            {clips.map((clip) => <ClipCard key={clip.id} clip={clip} />)}
          </div>
        </section>
      )}

      <p className="library-privacy"><Icon name="shield" size={15} /> Only selected files are processed. LifeClip never scans your gallery.</p>
    </div>
  )
}
