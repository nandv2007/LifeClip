import { useEffect } from 'react'
import { BrowserRouter, Link, NavLink, Route, Routes, useNavigate } from 'react-router-dom'
import { ToastProvider } from './components/Toast'
import { Icon, Logo } from './components/Icon'
import HomeScreen from './screens/HomeScreen'
import CaptureScreen from './screens/CaptureScreen'
import ClipScreen from './screens/ClipScreen'
import ActionScreen from './screens/ActionScreen'
import HistoryScreen from './screens/HistoryScreen'
import SettingsScreen from './screens/SettingsScreen'
import NotFoundScreen from './screens/NotFoundScreen'

function applyA11yPrefs() {
  const motion = localStorage.getItem('lifeclip.pref.reduceMotion') === '1'
  const text = localStorage.getItem('lifeclip.pref.largeText') === '1'
  document.documentElement.dataset.motion = motion ? 'reduce' : ''
  document.documentElement.dataset.text = text ? 'large' : ''
}

function Shell() {
  const navigate = useNavigate()
  return (
    <>
      <a href="#main" className="skip-link">
        Skip to content
      </a>
      <header className="app-header">
        <div className="app-header__inner">
          <Link to="/" className="brand" aria-label="LifeClip home">
            <Logo size={28} />
            LifeClip
          </Link>
          <nav className="header-nav" aria-label="Primary">
            <NavLink to="/" end aria-label="Home" title="Home">
              <Icon name="home" />
            </NavLink>
            <NavLink to="/history" aria-label="History" title="History">
              <Icon name="clock" />
            </NavLink>
            <NavLink to="/settings" aria-label="Settings" title="Settings">
              <Icon name="gear" />
            </NavLink>
          </nav>
        </div>
      </header>
      <main id="main" className="shell">
        <Routes>
          <Route path="/" element={<HomeScreen />} />
          <Route path="/capture" element={<CaptureScreen />} />
          <Route path="/clip/:id" element={<ClipScreen />} />
          <Route path="/clip/:id/action/:actionId" element={<ActionScreen />} />
          <Route path="/history" element={<HistoryScreen />} />
          <Route path="/settings" element={<SettingsScreen />} />
          <Route path="/404" element={<NotFoundScreen onHome={() => navigate('/')} />} />
          <Route path="*" element={<NotFoundScreen onHome={() => navigate('/')} />} />
        </Routes>
      </main>
    </>
  )
}

export default function App() {
  useEffect(() => {
    applyA11yPrefs()
    const onStorage = () => applyA11yPrefs()
    window.addEventListener('storage', onStorage)
    window.addEventListener('lifeclip:a11y', onStorage)
    return () => {
      window.removeEventListener('storage', onStorage)
      window.removeEventListener('lifeclip:a11y', onStorage)
    }
  }, [])

  // Set motion attributes on first paint too.
  if (!document.documentElement.dataset.motion) applyA11yPrefs()

  return (
    <ToastProvider>
      <BrowserRouter>
        <Shell />
      </BrowserRouter>
    </ToastProvider>
  )
}
