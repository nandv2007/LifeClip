// Truthful progress: only backend-reported phases advance. Upload progress is
// supplied separately by the real XHR stream; no timer-driven fake progress.

import { Icon } from './Icon'

const PHASE_ORDER = ['fetching', 'extracting_text', 'classifying', 'organizing', 'done']

export function ProcessingSteps({ phase, uploading }: { phase: string | null; uploading?: boolean }) {
  const steps = uploading
    ? [{ key: 'fetching', label: 'Uploading' }]
    : [
        { key: 'fetching', label: 'Processing original' },
        { key: 'extracting_text', label: 'Extracting text' },
        { key: 'classifying', label: 'Classifying content' },
        { key: 'organizing', label: 'Organizing details' },
      ]
  const normalized = phase === 'understanding' ? 'extracting_text' : phase === 'extracting' || phase === 'actions' ? 'organizing' : phase
  const currentIdx = PHASE_ORDER.indexOf(normalized || 'fetching')

  return (
    <ol className="steps" aria-label="Document processing progress">
      {steps.map((step, index) => {
        const done = currentIdx > index || normalized === 'done'
        const active = currentIdx === index && normalized !== 'done'
        return (
          <li
            key={step.key}
            className={`step${done ? ' step--done' : ''}${active ? ' step--active' : ''}`}
            aria-current={active ? 'step' : undefined}
          >
            <span className={`step__dot${active ? ' anim-pulse' : ''}`}>
              {done ? <Icon name="check" size={16} strokeWidth={2.4} /> : <Icon name={active ? 'sparkles' : 'clock'} size={15} />}
            </span>
            <span className="step__label">{step.label}</span>
          </li>
        )
      })}
    </ol>
  )
}
