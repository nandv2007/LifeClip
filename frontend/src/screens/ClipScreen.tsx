// Clip detail: truthful processing view while analysis runs (resume-safe on
// refresh), then the full result — editable fields, ranked actions, extracted
// text, deletion.

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api, ApiError } from '../lib/api'
import type { ClipDetail, FieldOut } from '../lib/types'
import { CATEGORY_LABELS } from '../lib/types'
import { Icon, actionIcon, categoryIcon } from '../components/Icon'
import { ProcessingSteps } from '../components/ProcessingSteps'
import { FieldRow } from '../components/Fields'
import { useToast } from '../components/Toast'
import { Modal } from '../components/Modal'
import { copyText } from '../lib/clipboard'
import { describeFile } from '../lib/upload'

const POLL_MS = 1600

// Graceful media preview: if the Cloudinary URL can't load (asset still
// propagating, offline, etc.) we show a calm placeholder instead of the
// browser's broken-image glyph.
function MediaPreview({
  src,
  alt,
  originalHref,
}: {
  src: string
  alt: string
  originalHref?: string
}) {
  const [failed, setFailed] = useState(false)
  return (
    <div className="result-media">
      {failed ? (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8, padding: '56px 20px', color: 'var(--ink-3)' }}>
          <Icon name="image" size={38} strokeWidth={1.4} />
          <span className="micro">The preview couldn’t be loaded.</span>
        </div>
      ) : (
        <img src={src} alt={alt} onError={() => setFailed(true)} />
      )}
      {originalHref && (
        <a
          className="result-media__expand"
          href={originalHref}
          target="_blank"
          rel="noreferrer noopener"
          aria-label="Open full-resolution original"
          title="Open original"
        >
          <Icon name="expand" size={19} />
        </a>
      )}
    </div>
  )
}

export default function ClipScreen() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { toast } = useToast()

  const [clip, setClip] = useState<ClipDetail | null>(null)
  const [phase, setPhase] = useState<string | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [editingTitle, setEditingTitle] = useState(false)
  const [titleDraft, setTitleDraft] = useState('')
  const [pollTick, setPollTick] = useState(0)
  const pollRef = useRef<number | null>(null)

  const stopPolling = useCallback(() => {
    if (pollRef.current !== null) {
      window.clearTimeout(pollRef.current)
      pollRef.current = null
    }
  }, [])

  const refresh = useCallback(async (): Promise<ClipDetail | null> => {
    if (!id) return null
    const detail = await api.getClip(id)
    setClip(detail)
    return detail
  }, [id])

  // Initial load + resume-safe polling while processing.
  useEffect(() => {
    let alive = true
    setLoadError(null)

    const tick = async () => {
      try {
        const status = await api.analysisStatus(id!)
        if (!alive) return
        if (status.status === 'ready' || status.status === 'partial' || status.status === 'failed') {
          await refresh()
          stopPolling()
          return
        }
        setPhase(status.phase || 'queued')
        pollRef.current = window.setTimeout(tick, POLL_MS)
      } catch (err) {
        if (!alive) return
        if (err instanceof ApiError && err.status === 0) {
          // Offline: keep polling — the analysis continues server-side.
          pollRef.current = window.setTimeout(tick, POLL_MS * 2)
          return
        }
        setLoadError((err as Error).message)
        stopPolling()
      }
    }

    api
      .getClip(id!)
      .then(async (detail) => {
        if (!alive) return
        setClip(detail)
        setTitleDraft(detail.title || '')
        if (detail.status === 'uploaded') {
          // Upload registered but analysis never started (e.g. closed early):
          // start it now — idempotent on the server.
          try {
            await api.analyze(detail.id)
          } catch {
            /* surfaced by polling */
          }
          if (alive) pollRef.current = window.setTimeout(tick, 400)
        } else if (
          detail.status === 'queued' ||
          detail.status === 'analyzing'
        ) {
          tick()
        }
      })
      .catch((err) => alive && setLoadError((err as Error).message))

    return () => {
      alive = false
      stopPolling()
    }
  }, [id, refresh, stopPolling, pollTick])

  const retry = useCallback(async () => {
    if (!id) return
    try {
      setClip((prev) => (prev ? { ...prev, status: 'queued', analysis_error: null } : prev))
      await api.analyze(id, true)
      setPollTick((t) => t + 1) // re-enter the polling effect, no page reload
    } catch (err) {
      setClip((prev) => (prev ? { ...prev, status: 'failed' } : prev))
      toast((err as Error).message, 'error')
    }
  }, [id, toast])

  const saveField = useCallback(
    async (field: FieldOut, value: string) => {
      if (!clip) return
      const fields = clip.fields.map((f) =>
        f.id === field.id ? { id: f.id, name: f.name, label: f.label, value } : { id: f.id, name: f.name, label: f.label, value: f.value },
      )
      try {
        const updated = await api.patchFields(clip.id, fields)
        setClip(updated)
        toast('Updated')
      } catch (err) {
        toast((err as Error).message, 'error')
      }
    },
    [clip, toast],
  )

  const saveTitle = useCallback(async () => {
    if (!clip) return
    try {
      const updated = await api.patchClip(clip.id, { title: titleDraft.trim() })
      setClip(updated)
      setEditingTitle(false)
      toast('Title updated')
    } catch (err) {
      toast((err as Error).message, 'error')
    }
  }, [clip, titleDraft, toast])

  const doDelete = useCallback(async () => {
    if (!clip) return
    setDeleting(true)
    try {
      const res = await api.deleteClip(clip.id)
      toast(res.cloudinary_asset_deleted ? 'Deleted from LifeClip and Cloudinary' : res.message)
      navigate('/', { replace: true })
    } catch (err) {
      setDeleting(false)
      setDeleteOpen(false)
      toast((err as Error).message, 'error')
    }
  }, [clip, navigate, toast])

  const fields = useMemo(() => clip?.fields ?? [], [clip])

  if (loadError) {
    return (
      <div className="stack" style={{ paddingTop: 60 }}>
        <div className="card stack" style={{ textAlign: 'center' }}>
          <div style={{ color: 'var(--warning)', display: 'flex', justifyContent: 'center' }}>
            <Icon name="alert" size={36} />
          </div>
          <h1 className="h3">We couldn’t open this item</h1>
          <p className="micro" style={{ margin: 0 }}>{loadError}</p>
          <div className="btn-row" style={{ marginTop: 8 }}>
            <Link to="/" className="btn">Back home</Link>
            <button className="btn btn--secondary" onClick={() => window.location.reload()}>Try again</button>
          </div>
        </div>
      </div>
    )
  }

  if (!clip) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', paddingTop: 120 }}>
        <span className="spinner" aria-label="Loading" />
      </div>
    )
  }

  /* --------------------------- processing states --------------------------- */
  if (clip.status === 'uploaded' || clip.status === 'queued' || clip.status === 'analyzing') {
    return (
      <div className="stack-lg" style={{ paddingTop: 40 }}>
        <div style={{ textAlign: 'center' }}>
          <h1 className="h2">Looking at your photo…</h1>
          <p className="lede" style={{ fontSize: 15 }}>
            This usually takes a few seconds. You can leave and come back — we’ll keep it safe.
          </p>
        </div>
        <div className="card">
          <ProcessingSteps phase={phase || 'queued'} />
        </div>
        <div style={{ opacity: 0.85 }}>
          <MediaPreview src={clip.preview_url} alt="Your upload being analyzed" />
        </div>
      </div>
    )
  }

  if (clip.status === 'failed') {
    return (
      <div className="stack-lg" style={{ paddingTop: 40 }}>
        <div className="card stack" style={{ textAlign: 'center' }}>
          <div style={{ color: 'var(--danger)', display: 'flex', justifyContent: 'center' }}>
            <Icon name="alert" size={38} strokeWidth={1.6} />
          </div>
          <h1 className="h2">We couldn’t understand this image</h1>
          <p className="lede" style={{ fontSize: 15 }}>
            {clip.analysis_error || 'You can try again, or use a clearer, sharper photo.'}
          </p>
          <div className="btn-row" style={{ marginTop: 8 }}>
            <button className="btn" onClick={() => void retry()}>
              <Icon name="refresh" size={18} />
              Try again
            </button>
            <button className="btn btn--danger-ghost" onClick={() => setDeleteOpen(true)}>
              <Icon name="trash" size={17} />
              Delete this item
            </button>
          </div>
        </div>
        <MediaPreview src={clip.preview_url} alt="The upload that could not be analyzed" />
        {deleteOpen && (
          <DeleteModal
            deleting={deleting}
            onCancel={() => setDeleteOpen(false)}
            onConfirm={() => void doDelete()}
          />
        )}
      </div>
    )
  }

  /* ------------------------------- result -------------------------------- */
  const primaries = clip.actions.filter((a) => a.primary)
  const others = clip.actions.filter((a) => !a.primary)
  const partial = clip.status === 'partial'

  return (
    <div className="stack-lg" style={{ paddingTop: 26 }}>
      {/* media */}
      <MediaPreview
        src={clip.preview_url}
        alt={`Original: ${clip.title || 'uploaded item'}`}
        originalHref={clip.secure_url}
      />

      {/* category + title */}
      <section>
        <div className="chip-row" style={{ marginBottom: 12 }}>
          <span className="chip chip--accent">
            <Icon name={categoryIcon(clip.category)} size={14} />
            {(clip.category && CATEGORY_LABELS[clip.category]) || 'Item'}
          </span>
          {partial && <span className="chip chip--warn">Some details uncertain</span>}
        </div>

        {editingTitle ? (
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <input
              className="input"
              value={titleDraft}
              onChange={(e) => setTitleDraft(e.target.value)}
              aria-label="Title"
              autoFocus
              onKeyDown={(e) => {
                if (e.key === 'Enter') void saveTitle()
                if (e.key === 'Escape') setEditingTitle(false)
              }}
              style={{ minHeight: 48 }}
            />
            <button className="btn btn--sm" onClick={() => void saveTitle()}>Save</button>
          </div>
        ) : (
          <h1 className="h1" style={{ fontSize: 'clamp(22px, 5.4vw, 28px)', display: 'flex', alignItems: 'flex-start', gap: 10 }}>
            <span style={{ minWidth: 0 }}>{clip.title || 'Untitled'}</span>
            <button
              className="field-row__edit"
              style={{ flex: 'none', marginTop: 2 }}
              onClick={() => { setTitleDraft(clip.title || ''); setEditingTitle(true) }}
              aria-label="Edit title"
              title="Edit title"
            >
              <Icon name="pencil" size={17} />
            </button>
          </h1>
        )}
      </section>

      {/* uncertainty / warnings */}
      {clip.analysis_error === null && partial && (
        <div className="banner banner--warn">
          <Icon name="alert" size={18} />
          <span>
            A few details were hard to read — please double-check the highlighted values before
            acting on them.
          </span>
        </div>
      )}

      {/* key fields */}
      {fields.length > 0 && (
        <section className="card" style={{ padding: '8px 22px' }} aria-label="Extracted information">
          {fields.map((f) => (
            <FieldRow key={f.id} field={f} onSave={saveField} />
          ))}
        </section>
      )}

      {/* actions */}
      <section aria-label="Suggested actions">
        <h2 className="h3" style={{ marginBottom: 4 }}>What you can do</h2>
        <p className="micro" style={{ marginTop: 0 }}>
          Suggested from what we found — you review before anything happens.
        </p>
        <div className="stack">
          {primaries.map((a) => (
            <ActionButton key={a.id} clipId={clip.id} action={a} primary />
          ))}
          {others.length > 0 && (
            <details className="disclosure">
              <summary>
                More actions
                <Icon name="chevron-down" size={18} />
              </summary>
              <div className="disclosure__body stack">
                {others.map((a) => (
                  <ActionButton key={a.id} clipId={clip.id} action={a} />
                ))}
              </div>
            </details>
          )}
        </div>
      </section>

      {/* extracted text & details */}
      <section className="stack">
        {clip.raw_text && (
          <details className="disclosure">
            <summary>
              Extracted text
              <span style={{ display: 'flex', gap: 8 }}>
                <CopyButton text={clip.raw_text} />
                <Icon name="chevron-down" size={18} />
              </span>
            </summary>
            <div className="disclosure__body">
              <div className="mono-box">{clip.raw_text}</div>
            </div>
          </details>
        )}
        <details className="disclosure">
          <summary>
            Details
            <Icon name="chevron-down" size={18} />
          </summary>
          <div className="disclosure__body micro" style={{ display: 'grid', gap: 6 }}>
            <div>File: {clip.original_filename || 'camera capture'} ({describeFile(clip.byte_size)})</div>
            <div>Dimensions: {clip.width} × {clip.height}px</div>
            <div>
              Captured:{' '}
              <time dateTime={clip.created_at}>
                {new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(clip.created_at))}
              </time>
            </div>
            <div>Stored securely in Cloudinary under the “lifeclip” folder.</div>
          </div>
        </details>
      </section>

      <hr className="divider" />
      <button className="btn btn--danger-ghost btn--block" onClick={() => setDeleteOpen(true)}>
        <Icon name="trash" size={17} />
        Delete this LifeClip
      </button>

      {deleteOpen && (
        <DeleteModal
          deleting={deleting}
          onCancel={() => setDeleteOpen(false)}
          onConfirm={() => void doDelete()}
        />
      )}
    </div>
  )

  function ActionButton({ clipId, action, primary = false }: { clipId: string; action: ClipDetail['actions'][number]; primary?: boolean }) {
    return (
      <Link
        to={`/clip/${clipId}/action/${action.id}`}
        className={`action-btn${primary ? ' action-btn--primary' : ''}`}
      >
        <span className="action-btn__icon">
          <Icon name={actionIcon(action.action_type)} size={20} />
        </span>
        <span className="action-btn__text">
          <span className="action-btn__label">{action.label}</span>
          {action.reason && <span className="action-btn__reason" style={{ display: 'block' }}>{action.reason}</span>}
        </span>
        <Icon name="chevron-right" size={18} className="action-btn__chev" />
      </Link>
    )
  }
}

function CopyButton({ text }: { text: string }) {
  const { toast } = useToast()
  return (
    <button
      className="btn btn--sm btn--ghost"
      style={{ minHeight: 30, padding: '0 10px', fontSize: 13 }}
      onClick={(e) => {
        e.preventDefault()
        e.stopPropagation()
        void copyText(text).then((ok) => toast(ok ? 'Text copied' : 'Copy failed — select the text instead', ok ? 'ok' : 'error'))
      }}
    >
      <Icon name="copy" size={14} /> Copy
    </button>
  )
}

function DeleteModal({
  deleting,
  onCancel,
  onConfirm,
}: {
  deleting: boolean
  onCancel: () => void
  onConfirm: () => void
}) {
  return (
    <Modal
      title="Delete this LifeClip?"
      onClose={onCancel}
      footer={
        <>
          <button className="btn btn--danger btn--block" onClick={onConfirm} disabled={deleting}>
            {deleting ? 'Deleting…' : 'Yes, delete it'}
          </button>
          <button className="btn btn--ghost btn--block" onClick={onCancel} disabled={deleting}>
            Keep it
          </button>
        </>
      }
    >
      The photo will be removed from Cloudinary and all extracted information will be permanently
      deleted. This cannot be undone.
    </Modal>
  )
}
