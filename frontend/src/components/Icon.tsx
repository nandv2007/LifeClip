// Inline SVG icon set (stroke-based, consistent 24px grid, round caps).
// No external requests — renders offline inside the sandboxed preview.

import type { JSX } from 'react'

const paths: Record<string, JSX.Element> = {
  camera: (
    <>
      <path d="M4 8.5A2.5 2.5 0 0 1 6.5 6h1.2l1.4-1.9a1.5 1.5 0 0 1 1.2-.6h3.4a1.5 1.5 0 0 1 1.2.6L16.3 6h1.2A2.5 2.5 0 0 1 20 8.5v8A2.5 2.5 0 0 1 17.5 19h-11A2.5 2.5 0 0 1 4 16.5Z" />
      <circle cx="12" cy="12.4" r="3.2" />
    </>
  ),
  image: (
    <>
      <rect x="4" y="5" width="16" height="14" rx="2.5" />
      <circle cx="9" cy="10" r="1.6" />
      <path d="m5.5 17 4.4-4.4a1.5 1.5 0 0 1 2.1 0l6.4 6.4" />
    </>
  ),
  shield: <path d="M12 3.5 5.5 6v5.2c0 4.3 2.8 7.7 6.5 9.3 3.7-1.6 6.5-5 6.5-9.3V6Z" />,
  'shield-check': (
    <>
      <path d="M12 3.5 5.5 6v5.2c0 4.3 2.8 7.7 6.5 9.3 3.7-1.6 6.5-5 6.5-9.3V6Z" />
      <path d="m9.2 11.8 2 2 3.6-3.8" />
    </>
  ),
  home: <path d="M4.5 10.5 12 4l7.5 6.5V19a1.5 1.5 0 0 1-1.5 1.5H6A1.5 1.5 0 0 1 4.5 19Z" />,
  clock: (
    <>
      <circle cx="12" cy="12" r="8" />
      <path d="M12 7.5V12l3 2" />
    </>
  ),
  gear: (
    <>
      <circle cx="12" cy="12" r="2.6" />
      <path d="M12 4v2M12 18v2M4 12h2M18 12h2M6.3 6.3l1.4 1.4M16.3 16.3l1.4 1.4M6.3 17.7l1.4-1.4M16.3 7.7l1.4-1.4" />
    </>
  ),
  'arrow-left': <path d="M19 12H5m6-7-7 7 7 7" />,
  'arrow-right': <path d="M5 12h14m-6-7 7 7-7 7" />,
  check: <path d="m5 12.5 4.5 4.5L19 7.5" />,
  x: <path d="M6 6l12 12M18 6 6 18" />,
  plus: <path d="M12 5v14M5 12h14" />,
  pencil: <path d="M15.8 4.8a2.1 2.1 0 0 1 3 3L8.4 18.2 4.5 19.2l1-3.9Z" />,
  trash: (
    <>
      <path d="M5 7h14M10 7V5.5A1.5 1.5 0 0 1 11.5 4h1A1.5 1.5 0 0 1 14 5.5V7" />
      <path d="M7 7l.7 11a2 2 0 0 0 2 1.9h4.6a2 2 0 0 0 2-1.9L17 7" />
    </>
  ),
  calendar: (
    <>
      <rect x="4.5" y="5.5" width="15" height="14" rx="2" />
      <path d="M4.5 10h15M8.5 3.5v4M15.5 3.5v4" />
    </>
  ),
  bell: (
    <>
      <path d="M6 16v-5a6 6 0 0 1 12 0v5l1.5 2.5H4.5Z" />
      <path d="M10 20a2.2 2.2 0 0 0 4 0" />
    </>
  ),
  'map-pin': (
    <>
      <path d="M12 21s-6.5-5.6-6.5-10.4a6.5 6.5 0 0 1 13 0C18.5 15.4 12 21 12 21Z" />
      <circle cx="12" cy="10.3" r="2.2" />
    </>
  ),
  share: (
    <>
      <circle cx="6" cy="12" r="2.3" />
      <circle cx="17.5" cy="5.5" r="2.3" />
      <circle cx="17.5" cy="18.5" r="2.3" />
      <path d="m8.1 10.9 7.3-4.3M8.1 13.1l7.3 4.3" />
    </>
  ),
  copy: (
    <>
      <rect x="9" y="9" width="11" height="11" rx="2" />
      <path d="M5.5 15H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v.5" />
    </>
  ),
  translate: (
    <>
      <path d="M4 6.5h8M8 4.5v2c0 4.5-2.4 8-5 9.8M5.6 9.5c1.1 3 3.4 5.4 6.2 6.6" />
      <path d="m12.5 20 4.5-10 4.5 10M14.2 16.5h5.6" />
    </>
  ),
  list: <path d="M9 6.5h11M9 12h11M9 17.5h11M4.5 6.5h.5M4.5 12h.5M4.5 17.5h.5" />,
  'help-circle': (
    <>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M9.6 9.4a2.5 2.5 0 1 1 3.6 2.8c-.8.5-1.2 1-1.2 1.9" />
      <path d="M12 17h.01" />
    </>
  ),
  layers: (
    <>
      <path d="m12 3.5 8.5 4.5-8.5 4.5L3.5 8Z" />
      <path d="m4.5 12.5 7.5 4 7.5-4M4.5 16.5l7.5 4 7.5-4" />
    </>
  ),
  search: (
    <>
      <circle cx="11" cy="11" r="6.5" />
      <path d="m20 20-4.2-4.2" />
    </>
  ),
  'external-link': (
    <>
      <path d="M14 4.5h5.5V10" />
      <path d="M19 5 11 13" />
      <path d="M18.5 13.5V18a1.5 1.5 0 0 1-1.5 1.5H6A1.5 1.5 0 0 1 4.5 18V7A1.5 1.5 0 0 1 6 5.5h4.5" />
    </>
  ),
  alert: (
    <>
      <path d="M12 4.5 20.5 19h-17Z" />
      <path d="M12 10v4M12 16.8h.01" />
    </>
  ),
  refresh: <path d="M19.5 12a7.5 7.5 0 1 1-2.2-5.3M19.5 4v4h-4" />,
  'chevron-down': <path d="m6 9.5 6 6 6-6" />,
  'chevron-right': <path d="m9.5 6 6 6-6 6" />,
  eye: (
    <>
      <path d="M2.5 12S6 5.8 12 5.8 21.5 12 21.5 12 18 18.2 12 18.2 2.5 12 2.5 12Z" />
      <circle cx="12" cy="12" r="2.8" />
    </>
  ),
  download: <path d="M12 4v11m-5-4.5 5 5 5-5M4.5 19.5h15" />,
  save: (
    <>
      <path d="M6 4.5h9.5L19 8v11a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V5.5a1 1 0 0 1 1-1Z" />
      <path d="M8.5 4.5v4h7v-4M8.5 20v-6h7v6" />
    </>
  ),
  file: (
    <>
      <path d="M13.5 4H7a1.5 1.5 0 0 0-1.5 1.5v13A1.5 1.5 0 0 0 7 20h10a1.5 1.5 0 0 0 1.5-1.5V8.5Z" />
      <path d="M13.5 4v4.5h5" />
    </>
  ),
  expand: <path d="M14 4.5h5.5V10M10 19.5H4.5V14M19.5 4.5 13 11M4.5 19.5 11 13" />,
  sparkles: (
    <>
      <path d="M12 4.5 13.6 9 18 10.5l-4.4 1.6L12 16.5 10.4 12 6 10.5 10.4 9Z" />
      <path d="M18.5 15.5l.7 1.8 1.8.7-1.8.7-.7 1.8-.7-1.8-1.8-.7 1.8-.7ZM5.5 16.5l.6 1.4 1.4.6-1.4.6-.6 1.4-.6-1.4-1.4-.6 1.4-.6Z" />
    </>
  ),
  receipt: (
    <>
      <path d="M6 3.5h12V20.5l-2-1.3-2 1.3-2-1.3-2 1.3-2-1.3-2 1.3Z" />
      <path d="M9 8h6M9 11.5h6M9 15h3.5" />
    </>
  ),
  ticket: (
    <>
      <path d="M4 8.5a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v1.2a2.3 2.3 0 0 0 0 4.6v1.2a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-1.2a2.3 2.3 0 0 0 0-4.6Z" />
      <path d="M13.5 7v2M13.5 11v2M13.5 15v2" />
    </>
  ),
  menu: (
    <>
      <path d="M7 4v5a1.6 1.6 0 0 0 3.2 0V4M8.6 4v16M13.5 3.5c-1.5 1.5-2 3.8-2 6.5 0 2 .8 2.5 2 2.5V20M13.5 3.5V20" />
      <path d="M17.5 15.5V20M17.5 12h3v3.5" />
    </>
  ),
  notes: (
    <>
      <path d="M8 4.5H5.5v16H18.5v-16H16" />
      <path d="M9 2.8h6v3.4H9z" />
      <path d="M8.5 10h7M8.5 13.5h7M8.5 17h4.5" />
    </>
  ),
  product: (
    <>
      <path d="m12 3.5 8 3v11l-8 3-8-3v-11Z" />
      <path d="m4.2 6.7 7.8 3 7.8-3M12 20.5v-10.8" />
    </>
  ),
}

export type IconName = keyof typeof paths

export function categoryIcon(category: string | null): IconName {
  switch (category) {
    case 'event': return 'calendar'
    case 'receipt': return 'receipt'
    case 'ticket': return 'ticket'
    case 'notes': return 'notes'
    case 'menu': return 'menu'
    case 'product': return 'product'
    case 'document': return 'file'
    default: return 'image'
  }
}

export function actionIcon(actionType: string): IconName {
  switch (actionType) {
    case 'calendar': return 'calendar'
    case 'reminder': case 'warranty': return 'bell'
    case 'directions': return 'map-pin'
    case 'share': return 'share'
    case 'copy_text': return 'copy'
    case 'translate': return 'translate'
    case 'summarize': return 'list'
    case 'quiz': return 'help-circle'
    case 'flashcards': return 'layers'
    case 'explain': return 'sparkles'
    case 'search': case 'open_link': return 'external-link'
    case 'save': case 'expense': return 'save'
    case 'open_original': return 'eye'
    default: return 'sparkles'
  }
}

interface IconProps {
  name: IconName
  size?: number
  strokeWidth?: number
  className?: string
  label?: string
}

export function Icon({ name, size = 21, strokeWidth = 1.8, className, label }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden={label ? undefined : true}
      role={label ? 'img' : undefined}
      aria-label={label}
    >
      {paths[name]}
    </svg>
  )
}

export function Logo({ size = 30 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" aria-hidden="true">
      <rect width="64" height="64" rx="16" fill="#0e7c6b" />
      <path d="M20 46V24a6 6 0 0 1 6-6h18" stroke="#fff" strokeWidth="5" fill="none" strokeLinecap="round" />
      <rect x="26" y="30" width="22" height="22" rx="6" fill="#fff" />
      <circle cx="37" cy="41" r="4" fill="#0e7c6b" />
    </svg>
  )
}
