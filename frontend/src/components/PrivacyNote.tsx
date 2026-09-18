import { Icon } from './Icon'
import { PRIVACY_MESSAGE } from '../lib/types'

export function PrivacyNote({ compact = false }: { compact?: boolean }) {
  return (
    <div className="privacy-note">
      <Icon name="shield-check" size={20} strokeWidth={1.9} />
      <div>
        {PRIVACY_MESSAGE}
        {!compact && (
          <div className="micro" style={{ marginTop: 4, color: 'inherit', opacity: 0.85 }}>
            Only the single photo you pick is analyzed. Nothing else on your device is touched.
          </div>
        )}
      </div>
    </div>
  )
}
