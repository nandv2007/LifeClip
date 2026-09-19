// Action confirmation: the user reviews and edits extracted values BEFORE any
// external action happens — calendar files, reminders, maps, shares.

import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../lib/api'
import type { ActionOut, ClipDetail, StudyOut } from '../lib/types'
import { Icon, actionIcon } from '../components/Icon'
import { useToast } from '../components/Toast'
import { displayDateToIso, displayTimeTo24 } from '../lib/upload'
import { copyText } from '../lib/clipboard'

const REMINDER_OPTIONS = [
  { value: 0, label: 'At the time' },
  { value: 15, label: '15 minutes before' },
  { value: 60, label: '1 hour before' },
  { value: 1440, label: '1 day before' },
  { value: 10080, label: '1 week before' },
]

const STUDY_MODES = new Set(['summarize', 'quiz', 'flashcards', 'explain'])
const STUDY_MODE_MAP: Record<string, StudyOut['mode']> = {
  summarize: 'summary',
  quiz: 'quiz',
  flashcards: 'flashcards',
  explain: 'explain',
}

export default function ActionScreen() {
  const { id, actionId } = useParams()
  const navigate = useNavigate()
  const { toast } = useToast()
  const [clip, setClip] = useState<ClipDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [working, setWorking] = useState(false)

  useEffect(() => {
    let alive = true
    api
      .getClip(id!)
      .then((c) => alive && setClip(c))
      .catch((e) => alive && setError((e as Error).message))
    return () => {
      alive = false
    }
  }, [id])

  const action = useMemo<ActionOut | null>(
    () => clip?.actions.find((a) => a.id === actionId) ?? null,
    [clip, actionId],
  )

  if (error) {
    return (
      <div className="card stack" style={{ marginTop: 40, textAlign: 'center' }}>
        <h1 className="h3">We couldn’t open this action</h1>
        <p className="micro">{error}</p>
        <Link to={`/clip/${id}`} className="btn">Back to result</Link>
      </div>
    )
  }

  if (!clip || !action) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', paddingTop: 120 }}>
        <span className="spinner" aria-label="Loading" />
      </div>
    )
  }

  const common = {
    clip,
    action,
    working,
    setWorking,
    toast,
    onDone: () => navigate(`/clip/${clip.id}`),
  }

  return (
    <div className="stack-lg" style={{ paddingTop: 26 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <Link to={`/clip/${clip.id}`} className="btn btn--ghost btn--sm" aria-label="Back to result" style={{ padding: 0, width: 40 }}>
          <Icon name="arrow-left" size={20} />
        </Link>
        <h1 className="h2">{action.label}</h1>
      </div>

      {action.action_type === 'calendar' || action.action_type === 'reminder' || action.action_type === 'warranty' ? (
        <CalendarConfirm {...common} kind={action.action_type} />
      ) : action.action_type === 'directions' ? (
        <DirectionsConfirm {...common} />
      ) : action.action_type === 'search' ? (
        <SearchConfirm {...common} />
      ) : action.action_type === 'open_link' ? (
        <OpenLinkConfirm {...common} />
      ) : action.action_type === 'translate' ? (
        <TranslateConfirm {...common} />
      ) : action.action_type === 'copy_text' ? (
        <CopyConfirm {...common} />
      ) : action.action_type === 'share' ? (
        <ShareConfirm {...common} />
      ) : action.action_type === 'open_original' ? (
        <OpenOriginalConfirm {...common} />
      ) : STUDY_MODES.has(action.action_type) ? (
        <StudyView {...common} mode={STUDY_MODE_MAP[action.action_type]} />
      ) : (
        <SaveConfirm {...common} />
      )}
    </div>
  )
}

interface CommonProps {
  clip: ClipDetail
  action: ActionOut
  working: boolean
  setWorking: (v: boolean) => void
  toast: (msg: string, kind?: 'ok' | 'error') => void
  onDone: () => void
}

/* ------------------------------ calendar/reminder ------------------------------ */

function CalendarConfirm(props: CommonProps & { kind: string }) {
  const { action, toast, working, setWorking } = props
  const p = action.payload as Record<string, string | number | null>
  const [title, setTitle] = useState(String(p.title || props.clip.title || ''))
  const [date, setDate] = useState(displayDateToIso(String(p.date || '')))
  const [time, setTime] = useState(displayTimeTo24(String(p.time || '')))
  const [location, setLocation] = useState(String(p.location || ''))
  const remindDefault = p.reminder_minutes === null || p.reminder_minutes === undefined ? 60 : Number(p.reminder_minutes)
  const [remind, setRemind] = useState<number>(props.kind === 'calendar' ? -1 : remindDefault)
  const [doneUrl, setDoneUrl] = useState<string | null>(null)

  // Fetch the .ics with our session header, then download the blob —
  // a bare anchor href can't send custom headers and would 401.
  const icsBlobRef = useRef<{ url: string; filename: string } | null>(null)

  const triggerDownload = async (apiPath: string) => {
    if (!icsBlobRef.current || icsBlobRef.current.url.startsWith('blob:') === false) {
      const { getSessionToken } = await import('../lib/session')
      const resp = await fetch(apiPath, { headers: { 'X-Lifeclip-Session': getSessionToken() } })
      if (!resp.ok) throw new Error('Could not prepare the calendar file. Please try again.')
      const blob = await resp.blob()
      const cd = resp.headers.get('content-disposition') || ''
      const m = /filename="([^"]+)"/.exec(cd)
      const filename = m?.[1] || 'lifeclip-event.ics'
      if (icsBlobRef.current) URL.revokeObjectURL(icsBlobRef.current.url)
      icsBlobRef.current = { url: URL.createObjectURL(blob), filename }
    }
    const { url, filename } = icsBlobRef.current
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.style.display = 'none'
    document.body.appendChild(a)
    a.click()
    window.setTimeout(() => a.remove(), 5000)
    return filename
  }

  const confirm = async () => {
    setWorking(true)
    try {
      const out = await api.confirmAction(action.id, {
        title,
        date,
        time,
        location,
        reminder_minutes: remind >= 0 ? remind : null,
      })
      if (out.download_url) {
        await triggerDownload(out.download_url)
        setDoneUrl(out.download_url)
      } else {
        toast('Confirmed')
        props.onDone()
      }
    } catch (err) {
      toast((err as Error).message, 'error')
    } finally {
      setWorking(false)
    }
  }

  if (doneUrl) {
    return (
      <div className="stack-lg">
        <div className="card stack" style={{ textAlign: 'center' }}>
          <div style={{ color: 'var(--success)', display: 'flex', justifyContent: 'center' }}>
            <Icon name="check" size={40} strokeWidth={2} />
          </div>
          <h2 className="h2">Calendar file downloaded</h2>
          <p className="micro" style={{ margin: 0 }}>
            Open the <strong>.ics</strong> file from your downloads to add “{title || 'this event'}” to
            Google Calendar, Apple Calendar or Outlook.
          </p>
          <div className="btn-row" style={{ marginTop: 8 }}>
            <button className="btn btn--secondary" onClick={() => void triggerDownload(doneUrl)}>
              <Icon name="download" size={18} />
              Download again
            </button>
            <button className="btn" onClick={props.onDone}>Back to result</button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="stack-lg">
      <div className="banner banner--info">
        <Icon name="check" size={18} />
        <span>
          Check the details first — only what you confirm below gets added. Nothing has been
          created yet.
        </span>
      </div>
      <div className="card stack">
        <div className="field">
          <label htmlFor="ev-title">Name</label>
          <input id="ev-title" className="input" value={title} onChange={(e) => setTitle(e.target.value)} />
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <div className="field">
            <label htmlFor="ev-date">Date</label>
            <input id="ev-date" className="input" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
            {!date && <span className="micro" style={{ color: 'var(--warning)' }}>Not detected — please pick a date.</span>}
          </div>
          <div className="field">
            <label htmlFor="ev-time">Time</label>
            <input id="ev-time" className="input" type="time" value={time} onChange={(e) => setTime(e.target.value)} />
          </div>
        </div>
        <div className="field">
          <label htmlFor="ev-loc">Location</label>
          <input id="ev-loc" className="input" value={location} onChange={(e) => setLocation(e.target.value)} placeholder="Optional" />
        </div>
        <div className="field">
          <label htmlFor="ev-remind">Reminder</label>
          <select id="ev-remind" className="select" value={remind} onChange={(e) => setRemind(Number(e.target.value))}>
            <option value={-1}>No reminder</option>
            {REMINDER_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>
      </div>
      <div className="btn-row">
        <button className="btn" disabled={working || !date || !title.trim()} onClick={() => void confirm()}>
          <Icon name="calendar" size={19} />
          {working ? 'Preparing…' : props.kind === 'warranty' ? 'Add warranty reminder' : 'Add to Calendar'}
        </button>
        <Link to={`/clip/${props.clip.id}`} className="btn btn--secondary">Cancel</Link>
      </div>
      <p className="micro" style={{ textAlign: 'center', margin: 0 }}>
        Downloads an .ics file your calendar app can open — Google Calendar, Apple Calendar,
        Outlook all support it.
      </p>
    </div>
  )
}

/* --------------------------------- directions --------------------------------- */

function DirectionsConfirm({ clip, action, working, setWorking, toast, onDone }: CommonProps) {
  const p = action.payload as Record<string, string>
  const [location, setLocation] = useState(p.query || '')

  const confirm = async () => {
    setWorking(true)
    try {
      const out = await api.confirmAction(action.id, { location })
      if (out.external_url) {
        window.open(out.external_url, '_blank', 'noopener,noreferrer')
        toast('Opening maps…')
      }
      onDone()
    } catch (err) {
      toast((err as Error).message, 'error')
    } finally {
      setWorking(false)
    }
  }

  return (
    <div className="stack-lg">
      <div className="card stack">
        <div className="field">
          <label htmlFor="dir-loc">Location</label>
          <input id="dir-loc" className="input" value={location} onChange={(e) => setLocation(e.target.value)} placeholder="Where to?" />
          {!location && <span className="micro" style={{ color: 'var(--warning)' }}>Not detected — type the venue or address.</span>}
        </div>
      </div>
      <div className="btn-row">
        <button className="btn" disabled={working || !location.trim()} onClick={() => void confirm()}>
          <Icon name="map-pin" size={19} />
          Open in Google Maps
        </button>
        <Link to={`/clip/${clip.id}`} className="btn btn--secondary">Cancel</Link>
      </div>
    </div>
  )
}

/* ----------------------------------- search ----------------------------------- */

function SearchConfirm({ clip, action, working, setWorking, toast, onDone }: CommonProps) {
  const p = action.payload as Record<string, string>
  const [query, setQuery] = useState(p.query || clip.title || '')
  return (
    <div className="stack-lg">
      <div className="card stack">
        <div className="field">
          <label htmlFor="q">Search for</label>
          <input id="q" className="input" value={query} onChange={(e) => setQuery(e.target.value)} />
        </div>
      </div>
      <div className="btn-row">
        <button
          className="btn"
          disabled={working || !query.trim()}
          onClick={() => {
            setWorking(true)
            api
              .confirmAction(action.id, { query })
              .then((out) => {
                if (out.external_url) window.open(out.external_url, '_blank', 'noopener,noreferrer')
                onDone()
              })
              .catch((e) => toast((e as Error).message, 'error'))
              .finally(() => setWorking(false))
          }}
        >
          <Icon name="search" size={19} />
          Search the web
        </button>
        <Link to={`/clip/${clip.id}`} className="btn btn--secondary">Cancel</Link>
      </div>
    </div>
  )
}

/* ---------------------------------- open link ---------------------------------- */

function OpenLinkConfirm({ clip, action, working, setWorking, toast, onDone }: CommonProps) {
  const p = action.payload as Record<string, string>
  const url = p.url || ''
  return (
    <div className="stack-lg">
      <div className="banner banner--info">
        <Icon name="external-link" size={18} />
        <span>This opens a link found on the image in a new tab.</span>
      </div>
      <div className="card">
        <div className="mono-box" style={{ maxHeight: 90 }}>{url}</div>
      </div>
      <div className="btn-row">
        <button
          className="btn"
          disabled={working || !url}
          onClick={() => {
            setWorking(true)
            api
              .confirmAction(action.id, { url })
              .then((out) => {
                if (out.external_url) window.open(out.external_url, '_blank', 'noopener,noreferrer')
                onDone()
              })
              .catch((e) => toast((e as Error).message, 'error'))
              .finally(() => setWorking(false))
          }}
        >
          <Icon name="external-link" size={19} />
          Open link
        </button>
        <Link to={`/clip/${clip.id}`} className="btn btn--secondary">Cancel</Link>
      </div>
    </div>
  )
}

/* ---------------------------------- translate ---------------------------------- */

function TranslateConfirm({ clip, action, working, setWorking, toast, onDone }: CommonProps) {
  const [text, setText] = useState(clip.raw_text || '')
  return (
    <div className="stack-lg">
      <div className="banner banner--info">
        <Icon name="translate" size={18} />
        <span>
          Opens Google Translate in a new tab with this text. Nothing is sent until you confirm.
        </span>
      </div>
      <div className="card stack">
        <div className="field">
          <label htmlFor="tr-text">Text to translate</label>
          <textarea id="tr-text" className="textarea" value={text} onChange={(e) => setText(e.target.value)} />
        </div>
      </div>
      <div className="btn-row">
        <button
          className="btn"
          disabled={working || !text.trim()}
          onClick={() => {
            setWorking(true)
            api
              .confirmAction(action.id, { text })
              .then((out) => {
                if (out.external_url) window.open(out.external_url, '_blank', 'noopener,noreferrer')
                onDone()
              })
              .catch((e) => toast((e as Error).message, 'error'))
              .finally(() => setWorking(false))
          }}
        >
          <Icon name="translate" size={19} />
          Open in Google Translate
        </button>
        <Link to={`/clip/${clip.id}`} className="btn btn--secondary">Cancel</Link>
      </div>
    </div>
  )
}

/* ------------------------------------ copy ------------------------------------ */

function CopyConfirm({ clip, action, toast, onDone }: CommonProps) {
  useEffect(() => {
    let alive = true
    api
      .confirmAction(action.id, {})
      .then(async (out) => {
        const ok = await copyText(out.content || '')
        if (alive) {
          toast(ok ? 'Text copied to your clipboard' : 'Copy failed — long-press the text instead', ok ? 'ok' : 'error')
          onDone()
        }
      })
      .catch((e) => alive && toast((e as Error).message, 'error'))
    return () => {
      alive = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div className="card" style={{ textAlign: 'center', padding: 32 }}>
      <span className="spinner" aria-label="Copying" />
      <p className="micro" style={{ marginTop: 12 }}>Copying the extracted text…</p>
    </div>
  )
}

/* ------------------------------------ share ----------------------------------- */

function ShareConfirm({ clip, action, working, setWorking, toast, onDone }: CommonProps) {
  const [content, setContent] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    api
      .confirmAction(action.id, {})
      .then((out) => alive && setContent(out.content || ''))
      .catch((e) => alive && setErr((e as Error).message))
    return () => {
      alive = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const share = async () => {
    if (!content) return
    setWorking(true)
    try {
      if (navigator.share) {
        await navigator.share({ title: clip.title || 'LifeClip', text: content })
        toast('Shared')
        onDone()
      } else {
        const ok = await copyText(content)
        toast(ok ? 'Sharing isn’t supported here — details copied instead' : 'Sharing unavailable', ok ? 'ok' : 'error')
        if (ok) onDone()
      }
    } catch (e) {
      if ((e as DOMException).name !== 'AbortError') toast('Share was cancelled or failed', 'error')
    } finally {
      setWorking(false)
    }
  }

  if (err) {
    return <div className="banner banner--error"><Icon name="alert" size={18} /><span>{err}</span></div>
  }

  return (
    <div className="stack-lg">
      <div className="banner banner--info">
        <Icon name="share" size={18} />
        <span>Review what will be shared — nothing leaves until you tap Share.</span>
      </div>
      <div className="card">
        {content === null ? (
          <span className="spinner" aria-label="Preparing" />
        ) : (
          <div className="mono-box" style={{ maxHeight: 220 }}>{content}</div>
        )}
      </div>
      <div className="btn-row">
        <button className="btn" disabled={working || !content} onClick={() => void share()}>
          <Icon name="share" size={19} />
          Share…
        </button>
        <Link to={`/clip/${clip.id}`} className="btn btn--secondary">Cancel</Link>
      </div>
    </div>
  )
}

/* -------------------------------- view original -------------------------------- */

function OpenOriginalConfirm({ clip, action, toast, onDone }: CommonProps) {
  useEffect(() => {
    api
      .confirmAction(action.id, {})
      .then((out) => {
        if (out.external_url) window.open(out.external_url, '_blank', 'noopener,noreferrer')
        onDone()
      })
      .catch((e) => {
        toast((e as Error).message, 'error')
        onDone()
      })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  return (
    <div className="card" style={{ textAlign: 'center', padding: 32 }}>
      <span className="spinner" aria-label="Opening" />
      <p className="micro" style={{ marginTop: 12 }}>Opening the full-resolution original…</p>
    </div>
  )
}

/* ------------------------------ save / expense -------------------------------- */

function SaveConfirm({ clip, action, working, setWorking, toast, onDone }: CommonProps) {
  return (
    <div className="stack-lg">
      <div className="banner banner--info">
        <Icon name={actionIcon(action.action_type)} size={18} />
        <span>
          {action.action_type === 'expense'
            ? 'Save this purchase to your records inside LifeClip.'
            : 'Mark this item as saved so it stays in your LifeClips.'}
        </span>
      </div>
      <div className="btn-row">
        <button
          className="btn"
          disabled={working}
          onClick={() => {
            setWorking(true)
            api
              .confirmAction(action.id, {})
              .then(() => {
                toast(action.action_type === 'expense' ? 'Expense saved' : 'Saved')
                onDone()
              })
              .catch((e) => toast((e as Error).message, 'error'))
              .finally(() => setWorking(false))
          }}
        >
          <Icon name="save" size={19} />
          {working ? 'Saving…' : 'Confirm'}
        </button>
        <Link to={`/clip/${clip.id}`} className="btn btn--secondary">Cancel</Link>
      </div>
    </div>
  )
}

/* --------------------------------- study tools --------------------------------- */

function StudyView({ clip, mode, toast, onDone }: CommonProps & { mode: StudyOut['mode'] }) {
  const [data, setData] = useState<StudyOut | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [revealed, setRevealed] = useState<Set<number>>(new Set())

  useEffect(() => {
    let alive = true
    api
      .study(clip.id, mode)
      .then((d) => alive && setData(d))
      .catch((e) => alive && setErr((e as Error).message))
    return () => {
      alive = false
    }
  }, [clip.id, mode])

  const toggle = (i: number) => {
    setRevealed((prev) => {
      const next = new Set(prev)
      if (next.has(i)) next.delete(i)
      else next.add(i)
      return next
    })
  }

  if (err) {
    return (
      <div className="stack">
        <div className="banner banner--warn">
          <Icon name="alert" size={18} />
          <span>{err}</span>
        </div>
        <Link to={`/clip/${clip.id}`} className="btn btn--secondary" style={{ alignSelf: 'center' }}>
          Back to result
        </Link>
      </div>
    )
  }

  if (!data) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', paddingTop: 60 }}>
        <span className="spinner" aria-label="Working" />
      </div>
    )
  }

  const asText = data.items
    .map((it) => it.point || `${it.question ?? it.front ?? ''}${it.answer ? ` — ${it.answer}` : ''}${it.back ? ` — ${it.back}` : ''}`)
    .join('\n\n')

  return (
    <div className="stack-lg">
      <p className="micro" style={{ margin: 0 }}>
        Made only from the text extracted from your file — check it against the original when it
        matters.
      </p>
      <div role="list">
        {data.items.map((item, i) => {
          if (mode === 'quiz') {
            const open = revealed.has(i)
            return (
              <button
                key={i}
                role="listitem"
                className="study-card flashcard"
                style={{ width: '100%', textAlign: 'left', border: 'none' }}
                onClick={() => toggle(i)}
                aria-expanded={open}
              >
                <div style={{ fontWeight: 600 }}>{item.question}</div>
                <div className="flashcard__back">{open ? <strong>{item.answer}</strong> : <em className="micro">Tap to reveal the answer</em>}</div>
              </button>
            )
          }
          if (mode === 'flashcards') {
            const open = revealed.has(i)
            return (
              <button
                key={i}
                role="listitem"
                className="study-card flashcard"
                style={{ width: '100%', textAlign: 'left', border: 'none' }}
                onClick={() => toggle(i)}
                aria-expanded={open}
              >
                <div style={{ fontWeight: 700, color: 'var(--accent-ink)' }}>{item.front}</div>
                <div className="flashcard__back">{open ? item.back : <em className="micro">Tap to flip</em>}</div>
              </button>
            )
          }
          return (
            <div key={i} role="listitem" className="study-card" style={{ marginBottom: 0 }}>
              {item.point}
            </div>
          )
        })}
      </div>
      <div className="btn-row">
        <button
          className="btn btn--secondary"
          onClick={() => void copyText(asText).then((ok) => toast(ok ? 'Copied' : 'Copy failed', ok ? 'ok' : 'error'))}
        >
          <Icon name="copy" size={18} />
          Copy all
        </button>
        <button className="btn btn--ghost" onClick={onDone}>Done</button>
      </div>
    </div>
  )
}
