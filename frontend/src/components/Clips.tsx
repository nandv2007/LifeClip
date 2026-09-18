// Clip cards for history + home recents, and the empty state.

import { Link } from 'react-router-dom'
import { Icon, categoryIcon } from './Icon'
import type { ClipListItem } from '../lib/types'
import { CATEGORY_LABELS } from '../lib/types'

function formatDate(iso: string): string {
  try {
    return new Intl.DateTimeFormat(undefined, {
      day: 'numeric',
      month: 'short',
    }).format(new Date(iso))
  } catch {
    return ''
  }
}

const STATUS_TEXT: Record<string, string> = {
  uploaded: 'Ready to analyze',
  queued: 'Queued…',
  analyzing: 'Analyzing…',
  partial: 'Check details',
  failed: 'Needs a retry',
}

export function ClipCard({ clip }: { clip: ClipListItem }) {
  const done = clip.status === 'ready' || clip.status === 'partial'
  return (
    <Link to={`/clip/${clip.id}`} className="clip-card">
      <img
        className="clip-card__thumb"
        src={clip.thumbnail_url}
        alt=""
        loading="lazy"
        width={76}
        height={76}
        onError={(e) => {
          e.currentTarget.style.visibility = 'hidden'
        }}
      />
      <div className="clip-card__body">
        <div className="clip-card__title">
          {done ? clip.title || 'Untitled' : STATUS_TEXT[clip.status] || 'Processing…'}
        </div>
        <div className="clip-card__meta">
          {done && clip.category && (
            <span className="chip" style={{ height: 24, padding: '0 9px', fontSize: 12.5 }}>
              <Icon name={categoryIcon(clip.category)} size={13} />
              {CATEGORY_LABELS[clip.category]}
            </span>
          )}
          <time dateTime={clip.created_at}>{formatDate(clip.created_at)}</time>
        </div>
      </div>
      <Icon name="chevron-right" size={19} className="clip-card__chevron" />
    </Link>
  )
}

export function RecentCard({ clip }: { clip: ClipListItem }) {
  const done = clip.status === 'ready' || clip.status === 'partial'
  return (
    <Link to={`/clip/${clip.id}`} className="recent-card">
      <img
        src={clip.thumbnail_url}
        alt=""
        loading="lazy"
        width={132}
        height={132}
        onError={(e) => {
          e.currentTarget.style.visibility = 'hidden'
        }}
      />
      <div className="recent-card__label">
        {done ? clip.title || 'Untitled' : STATUS_TEXT[clip.status] || 'Processing…'}
      </div>
    </Link>
  )
}

export function EmptyState({
  title,
  body,
  children,
}: {
  title: string
  body?: string
  children?: React.ReactNode
}) {
  return (
    <div className="empty">
      <Icon name="camera" size={44} strokeWidth={1.4} />
      <h3 className="h3">{title}</h3>
      {body && <p className="micro" style={{ marginTop: 6, maxWidth: 340, marginInline: 'auto' }}>{body}</p>}
      {children && <div style={{ marginTop: 18 }}>{children}</div>}
    </div>
  )
}
