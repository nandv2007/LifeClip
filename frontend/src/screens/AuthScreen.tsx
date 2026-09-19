import { useState, type FormEvent } from 'react'
import { Icon, Logo } from '../components/Icon'
import { useAuth } from '../auth/AuthContext'

export default function AuthScreen() {
  const { signIn, signUp, startupError } = useAuth()
  const [mode, setMode] = useState<'signin' | 'signup'>('signin')
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [identifier, setIdentifier] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const switchMode = (next: 'signin' | 'signup') => {
    setMode(next)
    setError('')
    setPassword('')
    setConfirmPassword('')
  }

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setError('')

    if (mode === 'signup') {
      if (!/^[A-Za-z0-9][A-Za-z0-9_]{2,29}$/.test(username.trim())) {
        setError('Use 3–30 letters, numbers or underscores for your username.')
        return
      }
      if (password.length < 8) {
        setError('Use at least 8 characters for your password.')
        return
      }
      if (password !== confirmPassword) {
        setError('The passwords do not match.')
        return
      }
    }

    setSubmitting(true)
    try {
      if (mode === 'signin') {
        await signIn(identifier.trim(), password)
      } else {
        await signUp(username.trim(), email.trim(), password)
      }
    } catch (err) {
      setError((err as Error).message || 'Unable to continue. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-intro" aria-label="About LifeClip">
        <div className="auth-brand"><Logo size={36} /> LifeClip</div>
        <div>
          <p className="eyebrow">Capture → understand → organize → act</p>
          <h1>Your important images, finally useful.</h1>
          <p>
            Save only the images you choose. LifeClip reads their real content,
            organizes them privately, and helps you act on what matters.
          </p>
        </div>
        <div className="auth-trust">
          <span><Icon name="shield-check" size={18} /> Private account library</span>
          <span><Icon name="image" size={18} /> Only images you explicitly choose</span>
        </div>
      </section>

      <section className="auth-panel" aria-labelledby="auth-title">
        <div className="auth-mobile-brand"><Logo size={31} /> LifeClip</div>
        <div className="auth-tabs" role="tablist" aria-label="Account access">
          <button
            type="button"
            role="tab"
            aria-selected={mode === 'signin'}
            onClick={() => switchMode('signin')}
          >
            Sign in
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={mode === 'signup'}
            onClick={() => switchMode('signup')}
          >
            Create account
          </button>
        </div>

        <div className="auth-heading">
          <h2 id="auth-title">{mode === 'signin' ? 'Welcome back' : 'Create your LifeClip account'}</h2>
          <p>
            {mode === 'signin'
              ? 'Sign in with your username or email.'
              : 'Choose a username and use your email to register.'}
          </p>
        </div>

        <form className="auth-form" onSubmit={submit}>
          {mode === 'signin' ? (
            <label>
              Username or email
              <input
                value={identifier}
                onChange={(event) => setIdentifier(event.target.value)}
                autoComplete="username"
                required
                minLength={3}
                maxLength={254}
                autoFocus
              />
            </label>
          ) : (
            <>
              <label>
                Username
                <input
                  value={username}
                  onChange={(event) => setUsername(event.target.value)}
                  autoComplete="username"
                  required
                  minLength={3}
                  maxLength={30}
                  pattern="[A-Za-z0-9][A-Za-z0-9_]{2,29}"
                  placeholder="e.g. nandhini_07"
                  autoFocus
                />
              </label>
              <label>
                Email address
                <input
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  autoComplete="email"
                  required
                  maxLength={254}
                  placeholder="you@example.com"
                />
              </label>
            </>
          )}

          <label>
            Password
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete={mode === 'signin' ? 'current-password' : 'new-password'}
              required
              minLength={mode === 'signup' ? 8 : 1}
              maxLength={128}
            />
          </label>

          {mode === 'signup' && (
            <label>
              Confirm password
              <input
                type="password"
                value={confirmPassword}
                onChange={(event) => setConfirmPassword(event.target.value)}
                autoComplete="new-password"
                required
                minLength={8}
                maxLength={128}
              />
            </label>
          )}

          {(error || startupError) && (
            <div className="auth-error" role="alert">
              <Icon name="alert" size={17} /> {error || startupError}
            </div>
          )}

          <button className="btn btn--primary btn--block auth-submit" disabled={submitting}>
            {submitting
              ? (mode === 'signin' ? 'Signing in…' : 'Creating account…')
              : (mode === 'signin' ? 'Sign in' : 'Create account')}
          </button>
        </form>

        <p className="auth-footnote">
          Your password is securely hashed. LifeClip never stores the original password.
        </p>
      </section>
    </main>
  )
}
