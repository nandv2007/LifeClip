// Smart-library cards and empty states.

import { Link } from 'react-router-dom'
import { Icon, categoryIcon } from './Icon'
import type { ClipListItem } from '../lib/types'
import { CATEGORY_LABELS } from '../lib/types'

function formatDate(iso: string): string {
  try {
    return new Intl.DateTimeFormat(undefined, { day: 'numeric', month: 'short', year: 'numeric' }).format(new Date(iso))
  } catch {
    return ''
  }
}

const STATUS_TEXT: Record<string, string> = {
  uploaded: 'Ready to process',
  queued: 'Processing',
  analyzing: 'Processing',
  ready: 'Ready',
  partial: 'Needs review',
  failed: 'Failed',
}

export function ClipCard({ clip }: { clip: ClipListItem }) {
  const done = clip.status === 'ready' || clip.status === 'partial'
  const statusKind = clip.status === 'ready' ? 'ok' : clip.status === 'partial' ? 'review' : clip.status === 'failed' ? 'failed' : 'working'
  return (
    <Link to={`/clip/${clip.id}`} className="clip-card" role="listitem">
      <div className="clip-card__media">
        <img
          className="clip-card__thumb"
          src={clip.thumbnail_url}
          alt=""
          loading="lazy"
          width={92}
          height={92}
          onError={(event) => { event.currentTarget.style.opacity = '0' }}
        />
      </div>
      <div className="clip-card__body">
        <div className="clip-card__topline">
          <div className="clip-card__title">{done ? clip.title || 'Untitled' : clip.original_filename || 'Processing document'}</div>
          <Icon name="chevron-right" size={18} className="clip-card__chevron" />
        </div>
        <div className="clip-card__filename">{clip.original_filename || 'Captured image'}</div>
        <div className="clip-card__meta">
          {done && clip.category && <span className="mini-category"><Icon name={categoryIcon(clip.category)} size={13} />{CATEGORY_LABELS[clip.category]}</span>}
          {clip.subject && <span>{clip.subject}</span>}
          <time dateTime={clip.created_at}>{formatDate(clip.created_at)}</time>
        </div>
        <div className={`status-line status-line--${statusKind}`}><i />{STATUS_TEXT[clip.status] || 'Processing'}</div>
      </div>
    </Link>
  )
}

export function RecentCard({ clip }: { clip: ClipListItem }) {
  const done = clip.status === 'ready' || clip.status === 'partial'
  return (
    <Link to={`/clip/${clip.id}`} className="recent-card">
      <div style={{ position: 'relative' }}>
        <img src={clip.thumbnail_url} alt="" loading="lazy" width={132} height={132} />
      </div>
      <div className="recent-card__label">{done ? clip.title || 'Untitled' : STATUS_TEXT[clip.status] || 'Processing'}</div>
      <div className="micro" style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{clip.original_filename}</div>
    </Link>
  )
}

export function EmptyState({ title, body, children }: { title: string; body?: string; children?: React.ReactNode }) {
  return (
    <div className="empty">
      <Icon name="file" size={44} strokeWidth={1.4} />
      <h3 className="h3">{title}</h3>
      {body && <p className="micro" style={{ marginTop: 6, maxWidth: 380, marginInline: 'auto' }}>{body}</p>}
      {children && <div style={{ marginTop: 18 }}>{children}</div>}
    </div>
  )
}
