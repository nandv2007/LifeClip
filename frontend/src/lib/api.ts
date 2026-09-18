// Typed API client. Every backend error arrives in the consistent envelope
// {"error": {"code", "message"}} — surfaced here as ApiError with a
// human-readable message (never raw technical noise).

import { getSessionToken, resetSessionToken } from './session'
import type {
  ActionConfirmOut,
  AnalysisStatusOut,
  ClipDetail,
  ClipListItem,
  HealthOut,
  SettingsOut,
  StudyOut,
  UploadSignatureOut,
} from './types'

const API_URL = import.meta.env.VITE_API_URL || ''

export class ApiError extends Error {
  code: string
  status: number

  constructor(status: number, code: string, message: string) {
    super(message)
    this.status = status
    this.code = code
  }
}

async function request<T>(
  path: string,
  init: RequestInit = {},
  retry401 = true,
): Promise<T> {
  let resp: Response

  try {
    resp = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: {
        'Content-Type': 'application/json',
        'X-Lifeclip-Session': getSessionToken(),
        ...(init.headers || {}),
      },
    })
  } catch {
    throw new ApiError(
      0,
      'offline',
      'No connection. Check your network and try again.',
    )
  }

  if (resp.status === 401 && retry401) {
    resetSessionToken()
    return request<T>(path, init, false)
  }

  let body: unknown = null

  try {
    body = await resp.json()
  } catch {
    /* empty body */
  }

  if (!resp.ok) {
    const err = (body as {
      error?: {
        code?: string
        message?: string
      }
    })?.error

    throw new ApiError(
      resp.status,
      err?.code || 'error',
      err?.message || 'Something went wrong. Please try again.',
    )
  }

  return body as T
}

export const api = {
  health: () =>
    request<HealthOut>('/api/health'),

  uploadSignature: (
    filename: string,
    mimeType: string,
    byteSize: number,
  ) =>
    request<UploadSignatureOut>('/api/upload-signature', {
      method: 'POST',
      body: JSON.stringify({
        filename,
        mime_type: mimeType,
        byte_size: byteSize,
      }),
    }),

  createClip: (
    publicId: string,
    originalFilename: string,
    mimeType: string,
  ) =>
    request<ClipDetail>('/api/clips', {
      method: 'POST',
      body: JSON.stringify({
        public_id: publicId,
        original_filename: originalFilename,
        mime_type: mimeType,
      }),
    }),

  listClips: (
    params: {
      q?: string
      category?: string
    } = {},
  ) => {
    const sp = new URLSearchParams()

    if (params.q) {
      sp.set('q', params.q)
    }

    if (params.category) {
      sp.set('category', params.category)
    }

    const suffix = sp.toString() ? `?${sp}` : ''

    return request<ClipListItem[]>(
      `/api/clips${suffix}`,
    )
  },

  getClip: (id: string) =>
    request<ClipDetail>(`/api/clips/${id}`),

  patchClip: (
    id: string,
    patch: {
      title?: string
      category?: string
    },
  ) =>
    request<ClipDetail>(
      `/api/clips/${id}`,
      {
        method: 'PATCH',
        body: JSON.stringify(patch),
      },
    ),

  patchFields: (
    id: string,
    fields: Array<{
      id?: string
      name: string
      label: string
      value: string
    }>,
  ) =>
    request<ClipDetail>(
      `/api/clips/${id}/fields`,
      {
        method: 'PATCH',
        body: JSON.stringify({ fields }),
      },
    ),

  analyze: (
    id: string,
    force = false,
  ) =>
    request<AnalysisStatusOut>(
      `/api/clips/${id}/analyze`,
      {
        method: 'POST',
        body: JSON.stringify({ force }),
      },
    ),

  analysisStatus: (id: string) =>
    request<AnalysisStatusOut>(
      `/api/clips/${id}/analysis`,
    ),

  deleteClip: (id: string) =>
    request<{
      deleted: boolean
      cloudinary_asset_deleted: boolean
      message: string
    }>(
      `/api/clips/${id}`,
      {
        method: 'DELETE',
      },
    ),

  confirmAction: (
    actionId: string,
    payload: Record<string, unknown>,
  ) =>
    request<ActionConfirmOut>(
      `/api/actions/${actionId}/confirm`,
      {
        method: 'POST',
        body: JSON.stringify({ payload }),
      },
    ),

  study: (
    clipId: string,
    mode: StudyOut['mode'],
  ) =>
    request<StudyOut>(
      `/api/clips/${clipId}/study`,
      {
        method: 'POST',
        body: JSON.stringify({ mode }),
      },
    ),

  getSettings: () =>
    request<SettingsOut>('/api/settings'),

  patchSettings: (
    patch: Partial<{
      retention_days: number
      save_extracted_text: boolean
    }>,
  ) =>
    request<SettingsOut>(
      '/api/settings',
      {
        method: 'PATCH',
        body: JSON.stringify(patch),
      },
    ),

  deleteAccount: () =>
    request<{
      deleted: boolean
      clips_removed: number
      message: string
    }>(
      '/api/account',
      {
        method: 'DELETE',
      },
    ),
}