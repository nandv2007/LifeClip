// Settings: privacy, retention, data deletion, accessibility, about.

import { useCallback, useEffect, useState } from 'react'
import { api } from '../lib/api'
import type { HealthOut, SettingsOut } from '../lib/types'
import { PRIVACY_MESSAGE } from '../lib/types'
import { Icon } from '../components/Icon'
import { useToast } from '../components/Toast'
import { Modal } from '../components/Modal'
import { resetSessionToken } from '../lib/session'

const RETENTION_OPTIONS = [
  { days: 30, label: '30 days' },
  { days: 90, label: '90 days' },
  { days: 365, label: '1 year' },
  { days: 0, label: 'Until I delete' },
]

export default function SettingsScreen() {
  const { toast } = useToast()
  const [settings, setSettings] = useState<SettingsOut | null>(null)
  const [health, setHealth] = useState<HealthOut | null>(null)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [reduceMotion, setReduceMotion] = useState(
    () => localStorage.getItem('lifeclip.pref.reduceMotion') === '1',
  )
  const [largeText, setLargeText] = useState(
    () => localStorage.getItem('lifeclip.pref.largeText') === '1',
  )

  useEffect(() => {
    let alive = true
    api.getSettings().then((s) => alive && setSettings(s)).catch(() => {})
    api.health().then((h) => alive && setHealth(h)).catch(() => {})
    return () => {
      alive = false
    }
  }, [])

  const update = useCallback(
    async (patch: Parameters<typeof api.patchSettings>[0]) => {
      try {
        const s = await api.patchSettings(patch)
        setSettings(s)
        toast('Settings saved')
      } catch (err) {
        toast((err as Error).message, 'error')
      }
    },
    [toast],
  )

  const setA11y = useCallback((key: string, value: boolean, setter: (v: boolean) => void) => {
    setter(value)
    localStorage.setItem(key, value ? '1' : '0')
    window.dispatchEvent(new Event('lifeclip:a11y'))
  }, [])

  const deleteAll = useCallback(async () => {
    setDeleting(true)
    try {
      const res = await api.deleteAccount()
      resetSessionToken()
      toast(res.message || 'All data deleted')
      setDeleteOpen(false)
      window.location.href = '/'
    } catch (err) {
      setDeleting(false)
      toast((err as Error).message, 'error')
    }
  }, [toast])

  return (
    <div className="stack-lg" style={{ paddingTop: 26 }}>
      <header>
        <h1 className="h1" style={{ fontSize: 'clamp(24px, 5.6vw, 30px)' }}>Settings</h1>
      </header>

      {/* ---------------------------- privacy ---------------------------- */}
      <section className="card stack" aria-labelledby="settings-privacy">
        <h2 className="h3" id="settings-privacy">
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 9 }}>
            <Icon name="shield-check" size={19} /> Privacy
          </span>
        </h2>
        <p style={{ margin: 0, color: 'var(--ink-2)', fontSize: 15 }}>{PRIVACY_MESSAGE}</p>
        <div className="micro" style={{ display: 'grid', gap: 6 }}>
          <div>• Only photos you explicitly capture or pick are uploaded — one at a time.</div>
          <div>• Your photos are stored securely in Cloudinary under the “lifeclip” folder.</div>
          <div>• Extracted text is stored so History and study tools work. You can turn that off below.</div>
          <div>• No account is needed; everything is tied to an anonymous on-device session.</div>
        </div>
        <div className="switch-row" style={{ borderTop: '1px solid var(--line)' }}>
          <div>
            <div style={{ fontWeight: 650, fontSize: 15 }}>Keep extracted text</div>
            <div className="micro">Turning this off deletes stored text from existing clips too.</div>
          </div>
          <button
            className="switch"
            role="switch"
            aria-checked={settings?.save_extracted_text ?? true}
            aria-label="Keep extracted text"
            disabled={!settings}
            onClick={() => settings && void update({ save_extracted_text: !settings.save_extracted_text })}
          />
        </div>
      </section>

      {/* ---------------------------- retention ---------------------------- */}
      <section className="card stack" aria-labelledby="settings-retention">
        <h2 className="h3" id="settings-retention">
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 9 }}>
            <Icon name="clock" size={19} /> Retention
          </span>
        </h2>
        <p className="micro" style={{ margin: 0 }}>
          Choose how long LifeClip keeps your photos before deleting them automatically. When the
          time comes, the Cloudinary copy and all extracted data are permanently removed.
        </p>
        <div className="seg" role="group" aria-label="Retention period">
          {RETENTION_OPTIONS.map((o) => (
            <button
              key={o.days}
              aria-pressed={settings?.retention_days === o.days}
              disabled={!settings}
              onClick={() => void update({ retention_days: o.days })}
            >
              {o.label}
            </button>
          ))}
        </div>
      </section>

      {/* ----------------------------- data ------------------------------ */}
      <section className="card stack" aria-labelledby="settings-data">
        <h2 className="h3" id="settings-data">
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 9 }}>
            <Icon name="trash" size={18} /> Delete data
          </span>
        </h2>
        <p className="micro" style={{ margin: 0 }}>
          Permanently delete every photo from Cloudinary, all extracted information, and your
          session. Nothing is kept.
        </p>
        <button className="btn btn--danger-ghost" style={{ alignSelf: 'flex-start' }} onClick={() => setDeleteOpen(true)}>
          <Icon name="trash" size={17} />
          Delete all my data
        </button>
      </section>

      {/* -------------------------- accessibility -------------------------- */}
      <section className="card" aria-labelledby="settings-a11y" style={{ paddingBottom: 8 }}>
        <h2 className="h3" id="settings-a11y" style={{ marginBottom: 4 }}>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 9 }}>
            <Icon name="eye" size={19} /> Accessibility
          </span>
        </h2>
        <div className="switch-row">
          <div>
            <div style={{ fontWeight: 650, fontSize: 15 }}>Reduce motion</div>
            <div className="micro">Minimize animations throughout the app.</div>
          </div>
          <button
            className="switch"
            role="switch"
            aria-checked={reduceMotion}
            aria-label="Reduce motion"
            onClick={() => setA11y('lifeclip.pref.reduceMotion', !reduceMotion, setReduceMotion)}
          />
        </div>
        <div className="switch-row">
          <div>
            <div style={{ fontWeight: 650, fontSize: 15 }}>Larger text</div>
            <div className="micro">Increase font size slightly across the app.</div>
          </div>
          <button
            className="switch"
            role="switch"
            aria-checked={largeText}
            aria-label="Larger text"
            onClick={() => setA11y('lifeclip.pref.largeText', !largeText, setLargeText)}
          />
        </div>
      </section>

      {/* ------------------------------ about ------------------------------ */}
      <section className="card card--flat" aria-labelledby="settings-about">
        <h2 className="h3" id="settings-about" style={{ marginBottom: 10 }}>
          About LifeClip
        </h2>
        <div className="micro" style={{ display: 'grid', gap: 6 }}>
          <div>Every photo should be actionable.</div>
          <div>Version {health?.version ?? '1.0.0'} · Server: {health ? health.status : 'unreachable'}</div>
          <div>
            Cloudinary: {health ? (health.cloudinary_configured ? 'connected' : 'not configured on the server') : '…'}
          </div>
        </div>
      </section>

      {deleteOpen && (
        <Modal
          title="Delete all your data?"
          onClose={() => !deleting && setDeleteOpen(false)}
          footer={
            <>
              <button className="btn btn--danger btn--block" onClick={() => void deleteAll()} disabled={deleting}>
                {deleting ? 'Deleting…' : 'Yes, delete everything'}
              </button>
              <button className="btn btn--ghost btn--block" onClick={() => setDeleteOpen(false)} disabled={deleting}>
                Cancel
              </button>
            </>
          }
        >
          Every LifeClip, its Cloudinary photo, all extracted information and your session will be
          permanently deleted. This cannot be undone.
        </Modal>
      )}
    </div>
  )
}
