// Consumer document detail: original preview, grounded metadata, extracted text,
// study/actions, organization controls and resource-safe deletion.

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api, ApiError } from '../lib/api'
import type { Category, ClipDetail, FieldOut } from '../lib/types'
import { CATEGORY_LABELS } from '../lib/types'
import { Icon, actionIcon, categoryIcon } from '../components/Icon'
import { ProcessingSteps } from '../components/ProcessingSteps'
import { FieldRow } from '../components/Fields'
import { useToast } from '../components/Toast'
import { Modal } from '../components/Modal'
import { copyText } from '../lib/clipboard'
import { describeFile } from '../lib/upload'

const POLL_MS = 1400
const CATEGORIES = Object.keys(CATEGORY_LABELS) as Category[]

function MediaPreview({ clip, subdued = false }: { clip: ClipDetail; subdued?: boolean }) {
  const [failed, setFailed] = useState(false)

  return (
    <div className={`document-preview${subdued ? ' document-preview--subdued' : ''}`}>
      <div className="document-preview__canvas">
        {failed ? (
          <div className="preview-placeholder"><Icon name="image" size={40} /><strong>Preview unavailable</strong><span className="micro">The original is still available below.</span></div>
        ) : (
          <img src={clip.preview_url} alt={`Original ${clip.title || clip.original_filename}`} onError={() => setFailed(true)} />
        )}
      </div>
      <div className="preview-actions">
        <a href={clip.secure_url} target="_blank" rel="noreferrer noopener"><Icon name="external-link" size={16} />Open original</a>
        <a href={clip.secure_url} download={clip.original_filename || undefined}><Icon name="download" size={16} />Download</a>
      </div>
    </div>
  )
}

function HighlightedText({ text, query }: { text: string; query: string }) {
  const needle = query.trim()
  if (!needle) return <>{text}</>
  const escaped = needle.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const parts = text.split(new RegExp(`(${escaped})`, 'gi'))
  return <>{parts.map((part, index) => part.toLocaleLowerCase() === needle.toLocaleLowerCase() ? <mark key={index}>{part}</mark> : part)}</>
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
  const [subjectDraft, setSubjectDraft] = useState('')
  const [topicDraft, setTopicDraft] = useState('')
  const [tagsDraft, setTagsDraft] = useState('')
  const [categoryDraft, setCategoryDraft] = useState<Category>('other')
  const [savingMeta, setSavingMeta] = useState(false)
  const [textQuery, setTextQuery] = useState('')
  const [pollTick, setPollTick] = useState(0)
  const pollRef = useRef<number | null>(null)

  const stopPolling = useCallback(() => {
    if (pollRef.current !== null) window.clearTimeout(pollRef.current)
    pollRef.current = null
  }, [])

  const refresh = useCallback(async () => {
    if (!id) return null
    const detail = await api.getClip(id)
    setClip(detail)
    return detail
  }, [id])

  useEffect(() => {
    let alive = true
    const tick = async () => {
      try {
        const status = await api.analysisStatus(id!)
        if (!alive) return
        setPhase(status.phase || 'queued')
        if (['ready', 'partial', 'failed'].includes(status.status)) {
          await refresh()
          stopPolling()
        } else {
          pollRef.current = window.setTimeout(tick, POLL_MS)
        }
      } catch (error) {
        if (!alive) return
        if (error instanceof ApiError && error.status === 0) pollRef.current = window.setTimeout(tick, POLL_MS * 2)
        else { setLoadError((error as Error).message); stopPolling() }
      }
    }
    setLoadError(null)
    api.getClip(id!).then(async (detail) => {
      if (!alive) return
      setClip(detail)
      if (detail.status === 'uploaded') {
        try { await api.analyze(detail.id) } catch { /* polling surfaces it */ }
        if (alive) pollRef.current = window.setTimeout(tick, 300)
      } else if (detail.status === 'queued' || detail.status === 'analyzing') {
        void tick()
      }
    }).catch((error) => alive && setLoadError((error as Error).message))
    return () => { alive = false; stopPolling() }
  }, [id, pollTick, refresh, stopPolling])

  useEffect(() => {
    if (!clip) return
    setTitleDraft(clip.title || '')
    setSubjectDraft(clip.subject || '')
    setTopicDraft(clip.topic || '')
    setTagsDraft(clip.tags.join(', '))
    setCategoryDraft(clip.category || 'other')
  }, [clip?.id])

  const retry = useCallback(async () => {
    if (!id) return
    try {
      setClip((current) => current ? { ...current, status: 'queued', analysis_error: null } : current)
      await api.analyze(id, true)
      setPollTick((value) => value + 1)
    } catch (error) { toast((error as Error).message, 'error') }
  }, [id, toast])

  const saveField = useCallback(async (field: FieldOut, value: string) => {
    if (!clip) return
    try {
      const updated = await api.patchFields(clip.id, clip.fields.map((item) => ({ id: item.id, name: item.name, label: item.label, value: item.id === field.id ? value : item.value })))
      setClip(updated); toast('Detail updated')
    } catch (error) { toast((error as Error).message, 'error') }
  }, [clip, toast])

  const saveTitle = useCallback(async () => {
    if (!clip) return
    try {
      const updated = await api.patchClip(clip.id, { title: titleDraft.trim() })
      setClip(updated); setEditingTitle(false); toast('Title updated')
    } catch (error) { toast((error as Error).message, 'error') }
  }, [clip, titleDraft, toast])

  const saveOrganization = useCallback(async () => {
    if (!clip) return
    setSavingMeta(true)
    try {
      const updated = await api.patchClip(clip.id, {
        category: categoryDraft,
        subject: subjectDraft.trim(),
        topic: topicDraft.trim(),
        tags: tagsDraft.split(',').map((tag) => tag.trim()).filter(Boolean),
      })
      setClip(updated); toast('Organization updated')
    } catch (error) { toast((error as Error).message, 'error') }
    finally { setSavingMeta(false) }
  }, [categoryDraft, clip, subjectDraft, tagsDraft, topicDraft, toast])

  const doDelete = useCallback(async () => {
    if (!clip) return
    setDeleting(true)
    try {
      const response = await api.deleteClip(clip.id)
      toast(response.cloudinary_asset_deleted ? 'Deleted from LifeClip and Cloudinary' : response.message)
      navigate('/library', { replace: true })
    } catch (error) { setDeleting(false); setDeleteOpen(false); toast((error as Error).message, 'error') }
  }, [clip, navigate, toast])

  const fields = useMemo(() => clip?.fields ?? [], [clip])

  if (loadError) return <CenteredError message={loadError} />
  if (!clip) return <div className="library-loading"><span className="spinner" aria-label="Loading document" /></div>

  if (['uploaded', 'queued', 'analyzing'].includes(clip.status)) {
    return (
      <div className="processing-page">
        <Link to="/library" className="detail-back"><Icon name="arrow-left" size={17} />Library</Link>
        <div className="processing-heading"><span className="eyebrow">SECURE PROCESSING</span><h1>Understanding your capture</h1><p>You can leave this page. The real extraction continues safely on the server.</p></div>
        <div className="detail-grid"><div><MediaPreview clip={clip} subdued /></div><div className="card"><ProcessingSteps phase={phase || 'fetching'} /><p className="micro" style={{ marginTop: 22 }}>No estimated percentages: each step advances only when the backend actually starts it.</p></div></div>
      </div>
    )
  }

  if (clip.status === 'failed') {
    return (
      <div className="processing-page">
        <Link to="/library" className="detail-back"><Icon name="arrow-left" size={17} />Library</Link>
        <div className="card failure-card"><Icon name="alert" size={40} /><h1>Processing failed</h1><p>{clip.analysis_error || 'The file could not be analyzed. The original has been kept.'}</p><div className="btn-row"><button className="btn" onClick={() => void retry()}><Icon name="refresh" size={18} />Try again</button><button className="btn btn--danger-ghost" onClick={() => setDeleteOpen(true)}><Icon name="trash" size={17} />Delete</button></div></div>
        <MediaPreview clip={clip} />
        {deleteOpen && <DeleteModal deleting={deleting} onCancel={() => setDeleteOpen(false)} onConfirm={() => void doDelete()} />}
      </div>
    )
  }

  const primaryActions = clip.actions.filter((action) => action.primary)
  const otherActions = clip.actions.filter((action) => !action.primary)
  const confidence = clip.analysis_confidence == null ? null : Math.round(clip.analysis_confidence * 100)

  return (
    <div className="document-detail">
      <Link to="/library" className="detail-back"><Icon name="arrow-left" size={17} />Smart library</Link>
      <div className="detail-grid">
        <aside className="detail-sidebar">
          <MediaPreview clip={clip} />
          <div className="source-card">
            <div><span>Source</span><strong>Image capture</strong></div>
            <div><span>Text</span><strong>{textStatusLabel(clip.extracted_text_status)}</strong></div>
            <div><span>OCR</span><strong>{clip.ocr_used ? 'Used' : 'Not needed'}</strong></div>
            <div><span>Size</span><strong>{describeFile(clip.byte_size)}</strong></div>
          </div>
        </aside>

        <main className="detail-main">
          <div className="document-heading">
            <div className="chip-row">
              <span className="chip chip--accent"><Icon name={categoryIcon(clip.category)} size={14} />{clip.category ? CATEGORY_LABELS[clip.category] : 'Needs review'}</span>
              <span className={`chip ${clip.status === 'partial' ? 'chip--warn' : 'chip--ok'}`}>{clip.status === 'partial' ? 'Needs review' : 'Ready'}</span>
              {confidence !== null && <span className="confidence-label">{confidence}% classification confidence</span>}
            </div>
            {editingTitle ? (
              <div className="inline-editor"><input className="input" value={titleDraft} onChange={(event) => setTitleDraft(event.target.value)} autoFocus onKeyDown={(event) => { if (event.key === 'Enter') void saveTitle(); if (event.key === 'Escape') setEditingTitle(false) }} /><button className="btn btn--sm" onClick={() => void saveTitle()}>Save</button></div>
            ) : (
              <h1>{clip.title || 'Untitled'}<button onClick={() => setEditingTitle(true)} aria-label="Rename document"><Icon name="pencil" size={17} /></button></h1>
            )}
            <p className="document-filename">{clip.original_filename || 'Original filename not available'}</p>
            {(clip.subject || clip.topic) && <div className="document-context">{clip.subject && <span>{clip.subject}</span>}{clip.topic && <span>{clip.topic}</span>}</div>}
          </div>

          {clip.analysis_warnings.map((warning, index) => <div className="banner banner--warn" key={index}><Icon name="alert" size={17} /><span>{warning}</span></div>)}

          {(fields.length > 0 || clip.headings.length > 0 || clip.concepts.length > 0) && (
            <section className="detail-section"><div className="detail-section__head"><div><span className="eyebrow">UNDERSTOOD</span><h2>Key details</h2></div></div>
              {fields.length > 0 && <div className="card extracted-fields">{fields.map((field) => <FieldRow key={field.id} field={field} onSave={saveField} />)}</div>}
              {(clip.headings.length > 0 || clip.concepts.length > 0) && <div className="insight-grid">{clip.headings.length > 0 && <div className="insight-card"><span>Headings found</span><div className="chip-row">{clip.headings.map((item) => <i key={item}>{item}</i>)}</div></div>}{clip.concepts.length > 0 && <div className="insight-card"><span>Key concepts</span><div className="chip-row">{clip.concepts.map((item) => <i key={item}>{item}</i>)}</div></div>}</div>}
            </section>
          )}

          <section className="detail-section"><div className="detail-section__head"><div><span className="eyebrow">ACT</span><h2>Tools grounded in this file</h2></div><p>Review before any external action.</p></div>
            <div className="action-grid">{primaryActions.map((action) => <ActionButton key={action.id} clipId={clip.id} action={action} primary />)}</div>
            {otherActions.length > 0 && <details className="disclosure" style={{ marginTop: 12 }}><summary>More tools <Icon name="chevron-down" size={18} /></summary><div className="disclosure__body action-grid">{otherActions.map((action) => <ActionButton key={action.id} clipId={clip.id} action={action} />)}</div></details>}
          </section>

          <section className="detail-section"><div className="detail-section__head"><div><span className="eyebrow">SOURCE TEXT</span><h2>Extracted text</h2></div>{clip.raw_text && <CopyButton text={clip.raw_text} />}</div>
            {clip.raw_text ? <div className="text-workspace"><div className="search-input"><Icon name="search" size={18} /><input className="input" type="search" value={textQuery} onChange={(event) => setTextQuery(event.target.value)} placeholder="Find in extracted text…" /></div><pre><HighlightedText text={clip.raw_text} query={textQuery} /></pre></div> : <div className="empty-text">No readable text was detected. LifeClip has not invented any.</div>}
          </section>

          <section className="detail-section"><div className="detail-section__head"><div><span className="eyebrow">ORGANIZE</span><h2>Library details</h2></div></div>
            <div className="card organization-form">
              <div className="field"><label htmlFor="doc-category">Collection</label><select id="doc-category" className="select" value={categoryDraft} onChange={(event) => setCategoryDraft(event.target.value as Category)}>{CATEGORIES.map((category) => <option key={category} value={category}>{CATEGORY_LABELS[category]}</option>)}</select></div>
              <div className="field"><label htmlFor="doc-subject">Subject</label><input id="doc-subject" className="input" value={subjectDraft} onChange={(event) => setSubjectDraft(event.target.value)} placeholder="Not detected" /></div>
              <div className="field"><label htmlFor="doc-topic">Topic</label><input id="doc-topic" className="input" value={topicDraft} onChange={(event) => setTopicDraft(event.target.value)} placeholder="Not detected" /></div>
              <div className="field organization-form__wide"><label htmlFor="doc-tags">Tags</label><input id="doc-tags" className="input" value={tagsDraft} onChange={(event) => setTagsDraft(event.target.value)} placeholder="Add comma-separated tags" /></div>
              <button className="btn btn--sm organization-form__save" disabled={savingMeta} onClick={() => void saveOrganization()}>{savingMeta ? 'Saving…' : 'Save organization'}</button>
            </div>
          </section>

          <section className="file-provenance"><div><strong>{clip.original_filename || 'Captured file'}</strong><span>{describeFile(clip.byte_size)} · {clip.mime_type} · {new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(clip.created_at))}</span></div><button className="btn btn--danger-ghost btn--sm" onClick={() => setDeleteOpen(true)}><Icon name="trash" size={16} />Delete</button></section>
        </main>
      </div>
      {deleteOpen && <DeleteModal deleting={deleting} onCancel={() => setDeleteOpen(false)} onConfirm={() => void doDelete()} />}
    </div>
  )
}

function textStatusLabel(status: string | null): string {
  return ({ selectable: 'Selectable text', ocr: 'OCR extracted', low_confidence: 'Needs review', unreadable: 'Not readable', readable: 'Readable' } as Record<string, string>)[status || ''] || 'Not detected'
}

function ActionButton({ clipId, action, primary = false }: { clipId: string; action: ClipDetail['actions'][number]; primary?: boolean }) {
  return <Link to={`/clip/${clipId}/action/${action.id}`} className={`action-btn${primary ? ' action-btn--primary' : ''}`}><span className="action-btn__icon"><Icon name={actionIcon(action.action_type)} size={20} /></span><span className="action-btn__text"><span className="action-btn__label">{action.label}</span>{action.reason && <span className="action-btn__reason">{action.reason}</span>}</span><Icon name="chevron-right" size={18} className="action-btn__chev" /></Link>
}

function CopyButton({ text }: { text: string }) {
  const { toast } = useToast()
  return <button className="btn btn--sm btn--secondary" onClick={() => void copyText(text).then((ok) => toast(ok ? 'Text copied' : 'Copy failed — select it instead', ok ? 'ok' : 'error'))}><Icon name="copy" size={15} />Copy text</button>
}

function CenteredError({ message }: { message: string }) {
  return <div className="card failure-card" style={{ marginTop: 50 }}><Icon name="alert" size={38} /><h1>We couldn’t open this document</h1><p>{message}</p><Link to="/library" className="btn">Back to library</Link></div>
}

function DeleteModal({ deleting, onCancel, onConfirm }: { deleting: boolean; onCancel: () => void; onConfirm: () => void }) {
  return <Modal title="Delete this document?" onClose={onCancel} footer={<><button className="btn btn--danger btn--block" onClick={onConfirm} disabled={deleting}>{deleting ? 'Deleting…' : 'Delete permanently'}</button><button className="btn btn--ghost btn--block" onClick={onCancel} disabled={deleting}>Keep it</button></>}>The original image, its Cloudinary asset, extracted text and organization data will be deleted. This cannot be undone.</Modal>
}
