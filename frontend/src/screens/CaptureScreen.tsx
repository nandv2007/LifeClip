// Capture flow: camera (where supported) OR explicit file choice -> preview ->
// confirm -> signed Cloudinary upload -> analyze. Nothing uploads until the
// user taps "Analyze this".

import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { api, ApiError } from '../lib/api'
import {
  ACCEPTED_MIME,
  MAX_FILE_BYTES,
  describeFile,
  uploadToCloudinary,
} from '../lib/upload'
import { Icon } from '../components/Icon'
import { PrivacyNote } from '../components/PrivacyNote'
import { useToast } from '../components/Toast'

type Stage =
  | { kind: 'picking' }
  | { kind: 'camera-starting' }
  | { kind: 'camera-live' }
  | { kind: 'camera-unavailable'; reason: string }
  | { kind: 'preview'; file: File; url: string; fromCamera: boolean }
  | { kind: 'invalid'; message: string }
  | { kind: 'uploading'; file: File; url: string; percent: number }
  | { kind: 'upload-failed'; file: File; url: string; message: string }

const CAMERA_ERROR_TEXT: Record<string, string> = {
  NotAllowedError:
    'Camera access was denied. You can allow it in your browser settings, or simply choose a file instead.',
  NotFoundError: 'No camera was found on this device. Choosing a file works just as well.',
  NotReadableError: 'The camera is busy in another app. Close it, or choose a file instead.',
  default: 'The camera is unavailable here — choose a file instead.',
}

export default function CaptureScreen() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const { toast } = useToast()
  const [stage, setStage] = useState<Stage>({ kind: 'picking' })
  const videoRef = useRef<HTMLVideoElement>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [dragOver, setDragOver] = useState(false)

  const stopCamera = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null
  }, [])

  useEffect(() => stopCamera, [stopCamera])

  const startCamera = useCallback(async () => {
    if (!navigator.mediaDevices?.getUserMedia) {
      setStage({ kind: 'camera-unavailable', reason: CAMERA_ERROR_TEXT.default })
      return
    }
    stopCamera()
    setStage({ kind: 'camera-starting' })
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment', width: { ideal: 1920 } },
        audio: false,
      })
      streamRef.current = stream
      if (videoRef.current) {
        videoRef.current.srcObject = stream
        await videoRef.current.play().catch(() => {})
      }
      setStage({ kind: 'camera-live' })
    } catch (err) {
      const name = (err as DOMException)?.name || 'default'
      setStage({
        kind: 'camera-unavailable',
        reason: CAMERA_ERROR_TEXT[name] || CAMERA_ERROR_TEXT.default,
      })
    }
  }, [stopCamera])

  // Camera mode requested from the home CTA.
  useEffect(() => {
    if (params.get('mode') === 'camera') void startCamera()
    if (params.get('mode') === 'file') {
      // Open the picker once on arrival.
      const t = window.setTimeout(() => fileInputRef.current?.click(), 250)
      return () => window.clearTimeout(t)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const acceptFile = useCallback((file: File) => {
    if (!ACCEPTED_MIME.includes(file.type)) {
      setStage({
        kind: 'invalid',
        message: `“${file.name}” isn’t a supported photo type. LifeClip works with JPEG, PNG or WebP images.`,
      })
      return
    }
    if (file.size > MAX_FILE_BYTES) {
      setStage({
        kind: 'invalid',
        message: `“${file.name}” is ${describeFile(file.size)} — too large. Choose an image under ${describeFile(MAX_FILE_BYTES)}.`,
      })
      return
    }
    const url = URL.createObjectURL(file)
    setStage((prev) => {
      if (prev.kind === 'preview' || prev.kind === 'uploading' || prev.kind === 'upload-failed') {
        URL.revokeObjectURL(prev.url)
      }
      return { kind: 'preview', file, url, fromCamera: false }
    })
  }, [])

  const capturePhoto = useCallback(() => {
    const video = videoRef.current
    if (!video || video.readyState < 2) return
    const w = video.videoWidth || 1280
    const h = video.videoHeight || 960
    const canvas = document.createElement('canvas')
    canvas.width = w
    canvas.height = h
    canvas.getContext('2d')?.drawImage(video, 0, 0, w, h)
    canvas.toBlob(
      (blob) => {
        if (!blob) {
          toast('Could not capture the photo. Please try again.', 'error')
          return
        }
        stopCamera()
        const file = new File([blob], `capture-${Date.now()}.jpg`, { type: 'image/jpeg' })
        const url = URL.createObjectURL(blob)
        setStage({ kind: 'preview', file, url, fromCamera: true })
      },
      'image/jpeg',
      0.9,
    )
  }, [stopCamera, toast])

  const analyze = useCallback(
    async (file: File, previewUrl: string) => {
      setStage({ kind: 'uploading', file, url: previewUrl, percent: 0 })
      try {
        // 1) One-time signature from our backend (secret stays server-side).
        const sig = await api.uploadSignature(file.name || 'capture.jpg', file.type, file.size)
        // 2) Direct browser -> Cloudinary upload with real progress.
        const asset = await uploadToCloudinary(sig, file, (percent) => {
          setStage((prev) => (prev.kind === 'uploading' ? { ...prev, percent } : prev))
        })
        // 3) Register + analyze.
        const clip = await api.createClip(asset.public_id, file.name || 'camera capture', file.type)
        await api.analyze(clip.id)
        URL.revokeObjectURL(previewUrl)
        navigate(`/clip/${clip.id}`, { replace: true })
      } catch (err) {
        const message =
          err instanceof ApiError && err.status === 0
            ? 'No connection. Check your network and try again.'
            : (err as Error).message || 'The upload failed. Please try again.'
        setStage({ kind: 'upload-failed', file, url: previewUrl, message })
      }
    },
    [navigate],
  )

  const chooseAnother = useCallback(() => {
    stopCamera()
    setStage((prev) => {
      if (prev.kind === 'preview' || prev.kind === 'upload-failed') URL.revokeObjectURL(prev.url)
      return { kind: 'picking' }
    })
  }, [stopCamera])

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      setDragOver(false)
      const file = e.dataTransfer.files?.[0]
      if (file) acceptFile(file)
    },
    [acceptFile],
  )

  return (
    <div className="stack-lg" style={{ paddingTop: 26 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <Link to="/" className="header-nav" style={{ display: 'inline-flex' }}>
          <span className="header-nav" style={{ display: 'inline-flex' }}>
            <button className="btn btn--ghost btn--sm" aria-label="Back home" style={{ padding: 0, width: 40 }}>
              <Icon name="arrow-left" size={20} />
            </button>
          </span>
        </Link>
        <h1 className="h2">Capture something</h1>
      </div>

      {/* ------------------------------ picking ------------------------------ */}
      {stage.kind === 'picking' && (
        <>
          <div
            className={`dropzone${dragOver ? ' dropzone--over' : ''}`}
            onDragOver={(e) => {
              e.preventDefault()
              setDragOver(true)
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={onDrop}
          >
            <Icon name="image" size={38} strokeWidth={1.5} />
            <p style={{ margin: '12px 0 4px', fontWeight: 650, color: 'var(--ink)' }}>
              Drop a photo here
            </p>
            <p className="micro" style={{ margin: 0 }}>
              A poster, receipt, ticket, note, menu, label or notice. JPEG, PNG or WebP, up to 10
              MB.
            </p>
            <div className="btn-row" style={{ marginTop: 22 }}>
              <button className="btn" onClick={() => fileInputRef.current?.click()}>
                <Icon name="image" size={19} />
                Choose one file
              </button>
              {'mediaDevices' in navigator && typeof navigator.mediaDevices?.getUserMedia === 'function' && (
                <button className="btn btn--secondary" onClick={() => void startCamera()}>
                  <Icon name="camera" size={19} />
                  Use camera
                </button>
              )}
            </div>
          </div>
          <PrivacyNote compact />
        </>
      )}

      {/* ------------------------------ camera ------------------------------ */}
      {(stage.kind === 'camera-starting' || stage.kind === 'camera-live') && (
        <div className="stack">
          <div className="camera-frame">
            <video
              ref={videoRef}
              playsInline
              muted
              autoPlay
              aria-label="Live camera preview"
              style={{ visibility: stage.kind === 'camera-live' ? 'visible' : 'hidden' }}
            />
            {stage.kind === 'camera-starting' && (
              <span className="spinner" aria-label="Starting camera" />
            )}
          </div>
          <div className="shutter-row">
            <button
              className="shutter"
              onClick={capturePhoto}
              disabled={stage.kind !== 'camera-live'}
              aria-label="Take photo"
            />
          </div>
          <p className="micro" style={{ textAlign: 'center', margin: 0 }}>
            Frame the poster, receipt or note clearly, then tap the button.
          </p>
          <button className="btn btn--ghost btn--block" onClick={chooseAnother}>
            Cancel
          </button>
        </div>
      )}

      {stage.kind === 'camera-unavailable' && (
        <div className="stack">
          <div className="card stack" style={{ textAlign: 'center' }}>
            <div style={{ color: 'var(--ink-3)', display: 'flex', justifyContent: 'center' }}>
              <Icon name="camera" size={40} strokeWidth={1.4} />
            </div>
            <h2 className="h3">Camera isn’t available</h2>
            <p className="micro" style={{ margin: 0 }}>{stage.reason}</p>
            <div className="btn-row" style={{ marginTop: 8 }}>
              <button className="btn" onClick={() => fileInputRef.current?.click()}>
                <Icon name="image" size={19} />
                Choose a file
              </button>
              <button className="btn btn--secondary" onClick={() => void startCamera()}>
                <Icon name="refresh" size={18} />
                Try camera again
              </button>
            </div>
          </div>
          <PrivacyNote compact />
        </div>
      )}

      {/* ------------------------------ invalid ------------------------------ */}
      {stage.kind === 'invalid' && (
        <div className="card stack" style={{ textAlign: 'center' }}>
          <div style={{ color: 'var(--warning)', display: 'flex', justifyContent: 'center' }}>
            <Icon name="alert" size={36} strokeWidth={1.6} />
          </div>
          <h2 className="h3">That file won’t work</h2>
          <p className="micro" style={{ margin: 0 }}>{stage.message}</p>
          <div className="btn-row" style={{ marginTop: 8 }}>
            <button className="btn" onClick={() => fileInputRef.current?.click()}>
              Choose another
            </button>
            <button className="btn btn--ghost" onClick={chooseAnother}>Back</button>
          </div>
        </div>
      )}

      {/* ------------------------------ preview ------------------------------ */}
      {(stage.kind === 'preview' || stage.kind === 'uploading' || stage.kind === 'upload-failed') && (
        <div className="stack">
          <div className="result-media">
            <img src={stage.url} alt="Preview of the selected item" />
          </div>
          <div className="file-meta">
            <span className="file-meta__icon">
              <Icon name="image" size={20} />
            </span>
            <div style={{ minWidth: 0 }}>
              <div style={{ fontWeight: 650, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {stage.file.name || 'Camera capture'}
              </div>
              <div className="micro">{describeFile(stage.file.size)} · {stage.file.type}</div>
            </div>
          </div>

          {stage.kind === 'preview' && (
            <>
              <div className="btn-row">
                <button className="btn" onClick={() => void analyze(stage.file, stage.url)}>
                  <Icon name="sparkles" size={19} />
                  Analyze this
                </button>
                <button className="btn btn--secondary" onClick={chooseAnother}>
                  Choose another
                </button>
              </div>
              {stage.fromCamera ? (
                <button className="btn btn--ghost btn--block" onClick={() => void startCamera()}>
                  <Icon name="refresh" size={17} /> Retake photo
                </button>
              ) : null}
              <PrivacyNote compact />
            </>
          )}

          {stage.kind === 'uploading' && (
            <div aria-live="polite">
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                <strong>Uploading securely…</strong>
                <span className="micro">{stage.percent}%</span>
              </div>
              <div className="progress-track" role="progressbar" aria-valuenow={stage.percent} aria-valuemin={0} aria-valuemax={100}>
                <div className="progress-fill" style={{ width: `${stage.percent}%` }} />
              </div>
            </div>
          )}

          {stage.kind === 'upload-failed' && (
            <div className="stack">
              <div className="banner banner--error">
                <Icon name="alert" size={18} />
                <span>{stage.message}</span>
              </div>
              <div className="btn-row">
                <button className="btn" onClick={() => void analyze(stage.file, stage.url)}>
                  <Icon name="refresh" size={18} />
                  Try again
                </button>
                <button className="btn btn--secondary" onClick={chooseAnother}>
                  Choose another
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      <input
        ref={fileInputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        className="sr-only"
        aria-label="Choose a photo"
        onChange={(e) => {
          const file = e.target.files?.[0]
          if (file) acceptFile(file)
          e.target.value = ''
        }}
      />
    </div>
  )
}
