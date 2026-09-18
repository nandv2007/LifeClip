// Direct browser -> Cloudinary upload using a one-time signature from our
// backend. The API secret never touches the browser — only its signature.
// Progress events come from the real XHR upload stream (no fake progress).

import type { UploadSignatureOut } from './types'

export class UploadError extends Error {
  constructor(message: string, readonly offline = false) {
    super(message)
  }
}

export interface CloudinaryUploadResult {
  public_id: string
  secure_url: string
  bytes: number
  format: string
  width: number
  height: number
}

export function uploadToCloudinary(
  sig: UploadSignatureOut,
  file: Blob,
  onProgress: (percent: number) => void,
): Promise<CloudinaryUploadResult> {
  return new Promise((resolve, reject) => {
    const form = new FormData()
    form.set('file', file)
    form.set('api_key', sig.api_key)
    form.set('timestamp', String(sig.timestamp))
    form.set('signature', sig.signature)
    form.set('folder', sig.folder)
    form.set('public_id', sig.public_id)
    form.set('tags', sig.tags)
    form.set('context', sig.context)

    const xhr = new XMLHttpRequest()
    xhr.open('POST', sig.upload_url)
    xhr.responseType = 'json'
    xhr.timeout = 90_000

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && e.total > 0) {
        onProgress(Math.round((e.loaded / e.total) * 100))
      }
    }

    xhr.onload = () => {
      const body = xhr.response as (CloudinaryUploadResult & { error?: { message?: string } }) | null
      if (xhr.status >= 200 && xhr.status < 300 && body?.public_id) {
        onProgress(100)
        resolve(body)
      } else {
        const msg = body?.error?.message
        reject(
          new UploadError(
            msg && xhr.status === 400
              ? 'This upload was rejected — the server signature may have expired. Please try again.'
              : 'The upload to Cloudinary failed. Please try again.',
          ),
        )
      }
    }
    xhr.onerror = () => reject(new UploadError('No connection during upload. Please try again.', true))
    xhr.ontimeout = () => reject(new UploadError('The upload timed out. Please try again.', true))
    xhr.send(form)
  })
}

export const MAX_FILE_BYTES = 10 * 1024 * 1024
export const ACCEPTED_MIME = ['image/jpeg', 'image/png', 'image/webp']

export function describeFile(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

// Convert a display date like "25 October 2026" or "14/09/2026" to ISO for
// <input type="date">. Returns '' when it can't be parsed — we never guess.
export function displayDateToIso(value?: string): string {
  if (!value) return ''
  const v = value.trim()
  const iso = /^(\d{4})-(\d{2})-(\d{2})$/.exec(v)
  if (iso) return v
  const numeric = /^(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})$/.exec(v)
  if (numeric) {
    const d = parseInt(numeric[1], 10)
    const m = parseInt(numeric[2], 10)
    let y = parseInt(numeric[3], 10)
    if (y < 100) y += 2000
    if (m >= 1 && m <= 12 && d >= 1 && d <= 31) {
      return `${y}-${String(m).padStart(2, '0')}-${String(d).padStart(2, '0')}`
    }
    return ''
  }
  const months: Record<string, number> = {
    january: 1, february: 2, march: 3, april: 4, may: 5, june: 6,
    july: 7, august: 8, september: 9, october: 10, november: 11, december: 12,
  }
  const words = /^(\d{1,2})\s+([A-Za-z]+)(?:\s+(\d{4}))?$/.exec(v)
  if (words) {
    const m = months[words[2].toLowerCase()]
    if (m && words[3]) {
      return `${words[3]}-${String(m).padStart(2, '0')}-${String(parseInt(words[1], 10)).padStart(2, '0')}`
    }
  }
  return ''
}

export function displayTimeTo24(value?: string): string {
  if (!value) return ''
  const m = /^(\d{1,2}):(\d{2})(?:\s*([AaPp])[Mm]?)?$/.exec(value.trim())
  if (!m) return ''
  let h = parseInt(m[1], 10)
  if (m[3]) {
    const pm = m[3].toLowerCase() === 'p'
    h = (h % 12) + (pm ? 12 : 0)
  }
  if (h > 23) return ''
  return `${String(h).padStart(2, '0')}:${m[2]}`
}
