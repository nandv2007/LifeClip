// API types mirroring the backend contract.

export type Category =
  | 'event'
  | 'receipt'
  | 'ticket'
  | 'notes'
  | 'menu'
  | 'product'
  | 'document'
  | 'other'

export type ClipStatus = 'uploaded' | 'queued' | 'analyzing' | 'ready' | 'partial' | 'failed'

export interface HealthOut {
  status: string
  version: string
  database: string
  cloudinary_configured: boolean
  time: string
}

export interface UploadSignatureOut {
  upload_url: string
  cloud_name: string
  api_key: string
  timestamp: number
  folder: string
  public_id: string
  signature: string
  tags: string
  context: string
  max_upload_bytes: number
}

export interface FieldOut {
  id: string
  name: string
  label: string
  value: string
  confidence: number
  user_edited: boolean
}

export interface ActionOut {
  id: string
  action_type: string
  label: string
  reason: string
  primary: boolean
  status: string
  payload: Record<string, unknown>
}

export interface ClipListItem {
  id: string
  status: ClipStatus
  category: Category | null
  title: string | null
  original_filename: string
  mime_type: string
  subject: string | null
  topic: string | null
  tags: string[]
  extracted_text_status: string | null
  analysis_confidence: number | null
  thumbnail_url: string
  preview_url: string
  created_at: string
}

export interface ClipDetail extends ClipListItem {
  byte_size: number
  width: number
  height: number
  secure_url: string
  raw_text: string | null
  analysis_error: string | null
  ocr_used: boolean
  headings: string[]
  concepts: string[]
  analysis_warnings: string[]
  fields: FieldOut[]
  actions: ActionOut[]
  updated_at: string
}

export interface AnalysisStatusOut {
  clip_id: string
  status: ClipStatus
  run_id: string | null
  run_status: string | null
  phase: string | null
  phase_message: string | null
  error: string | null
}

export interface ActionConfirmOut {
  id: string
  status: string
  download_url: string | null
  content: string | null
  external_url: string | null
}

export interface StudyOut {
  mode: 'summary' | 'explain' | 'quiz' | 'flashcards'
  items: Array<Record<string, string>>
}

export interface SettingsOut {
  retention_days: number
  save_extracted_text: boolean
}

export const CATEGORY_LABELS: Record<Category, string> = {
  event: 'Event',
  receipt: 'Receipt',
  ticket: 'Ticket',
  notes: 'Notes',
  menu: 'Menu',
  product: 'Product',
  document: 'Document',
  other: 'Other',
}

export const PRIVACY_MESSAGE =
  'LifeClip only sees what you choose to capture or upload. We never scan your gallery.'
