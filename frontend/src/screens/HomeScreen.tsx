import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../lib/api'
import type { ClipListItem } from '../lib/types'
import { Icon } from '../components/Icon'
import { PrivacyNote } from '../components/PrivacyNote'
import { RecentCard, EmptyState } from '../components/Clips'

export default function HomeScreen() {
  const [recent, setRecent] = useState<ClipListItem[] | null>(null)
  const [cloudinaryReady, setCloudinaryReady] = useState<boolean | null>(null)

  useEffect(() => {
    let alive = true
    api
      .listClips()
      .then((clips) => alive && setRecent(clips.slice(0, 8)))
      .catch(() => alive && setRecent([]))
    api
      .health()
      .then((h) => alive && setCloudinaryReady(h.cloudinary_configured))
      .catch(() => alive && setCloudinaryReady(null))
    return () => {
      alive = false
    }
  }, [])

  return (
    <div className="stack-lg" style={{ paddingTop: 34 }}>
      <section aria-labelledby="hero-heading">
        <h1 className="h1" id="hero-heading">
          Every photo should be&nbsp;actionable.
        </h1>
        <p className="lede">
          Capture a poster, receipt, ticket or note. LifeClip reads it, pulls out what matters, and
          suggests what to do next.
        </p>
        <div className="btn-row" style={{ marginTop: 26 }}>
          <Link to="/capture?mode=camera" className="btn">
            <Icon name="camera" size={20} strokeWidth={2} />
            Capture something
          </Link>
          <Link to="/capture?mode=file" className="btn btn--secondary">
            <Icon name="image" size={20} />
            Choose a file
          </Link>
        </div>
        {cloudinaryReady === false && (
          <div className="banner banner--warn" style={{ marginTop: 18 }} role="note">
            <Icon name="alert" size={18} />
            <span>
              Cloudinary isn’t configured on the server yet, so uploads are paused. Add your API key
              and secret to <code>backend/.env</code> and restart the backend.
            </span>
          </div>
        )}
      </section>

      <PrivacyNote />

      <section aria-labelledby="recent-heading">
        <div className="section-title">
          <h2 id="recent-heading">Your recent LifeClips</h2>
          {recent && recent.length > 0 && (
            <Link to="/history" className="micro" style={{ fontWeight: 650, color: 'var(--accent)' }}>
              View all
            </Link>
          )}
        </div>
        {recent === null ? (
          <div className="card" style={{ display: 'flex', justifyContent: 'center', padding: 32 }}>
            <span className="spinner" aria-label="Loading" />
          </div>
        ) : recent.length === 0 ? (
          <div className="card">
            <EmptyState
              title="Nothing here yet"
              body="Capture a poster, receipt, ticket, menu or note — it will show up here after you analyze it."
            />
          </div>
        ) : (
          <div className="recent-row" role="list">
            {recent.map((clip) => (
              <RecentCard key={clip.id} clip={clip} />
            ))}
          </div>
        )}
      </section>

      <section className="card card--flat" aria-label="What LifeClip understands" style={{ background: 'var(--surface)' }}>
        <h2 className="h3" style={{ marginBottom: 12 }}>
          Great for everyday things
        </h2>
        <div className="chip-row">
          {[
            ['calendar', 'Event posters'],
            ['receipt', 'Receipts'],
            ['ticket', 'Tickets'],
            ['notes', 'Study notes'],
            ['menu', 'Menus'],
            ['product', 'Product labels'],
            ['file', 'Notices'],
          ].map(([icon, label]) => (
            <span key={label} className="chip">
              <Icon name={icon as never} size={14} />
              {label}
            </span>
          ))}
        </div>
      </section>
    </div>
  )
}
