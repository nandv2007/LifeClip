import { Icon } from '../components/Icon'

export default function NotFoundScreen({ onHome }: { onHome: () => void }) {
  return (
    <div className="stack" style={{ paddingTop: 70, textAlign: 'center' }}>
      <div style={{ color: 'var(--ink-3)', display: 'flex', justifyContent: 'center' }}>
        <Icon name="search" size={42} strokeWidth={1.4} />
      </div>
      <h1 className="h2">This page doesn’t exist</h1>
      <p className="micro">The link may be old, or the item was deleted.</p>
      <div>
        <button className="btn" onClick={onHome}>
          Back home
        </button>
      </div>
    </div>
  )
}
