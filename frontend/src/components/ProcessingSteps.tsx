// Truthful processing visualization: steps light up only as the backend
// reports each phase. No fake percentages.

import { Icon } from './Icon'

export interface StepDef {
  key: string
  label: string
}

const PHASE_ORDER = ['fetching', 'understanding', 'extracting', 'actions', 'done']

export function ProcessingSteps({ phase, uploading }: { phase: string | null; uploading?: boolean }) {
  const steps: StepDef[] = [
    { key: 'fetching', label: uploading ? 'Uploading securely' : 'Fetching your image' },
    { key: 'understanding', label: 'Understanding' },
    { key: 'extracting', label: 'Finding useful information' },
    { key: 'actions', label: 'Preparing actions' },
  ]
  const currentIdx = PHASE_ORDER.indexOf(phase || 'fetching')

  return (
    <ol className="steps" aria-label="Progress">
      {steps.map((s, i) => {
        const done = currentIdx > i || phase === 'done'
        const active = currentIdx === i && phase !== 'done'
        return (
          <li
            key={s.key}
            className={`step${done ? ' step--done' : ''}${active ? ' step--active' : ''}`}
            aria-current={active ? 'step' : undefined}
          >
            <span className={`step__dot${active ? ' anim-pulse' : ''}`}>
              {done ? <Icon name="check" size={16} strokeWidth={2.4} /> : <Icon name={active ? 'sparkles' : 'clock'} size={15} />}
            </span>
            <span className="step__label">{s.label}</span>
          </li>
        )
      })}
    </ol>
  )
}
