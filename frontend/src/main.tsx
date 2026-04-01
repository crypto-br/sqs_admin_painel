import React, { useState, useEffect } from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import Login from './Login'
import { authEnabled, getCurrentSession, logout } from './auth'
import './App.css'

function Root() {
  const [authenticated, setAuthenticated] = useState(!authEnabled)
  const [checking, setChecking] = useState(authEnabled)

  useEffect(() => {
    if (!authEnabled) return
    getCurrentSession().then(s => { setAuthenticated(!!s); setChecking(false) })
    const handler = () => { setAuthenticated(false) }
    window.addEventListener('auth:expired', handler)
    return () => window.removeEventListener('auth:expired', handler)
  }, [])

  const handleLogout = () => { logout(); setAuthenticated(false) }

  if (checking) return <div className="login-container"><p>Loading...</p></div>
  if (!authenticated) return <Login onLogin={() => setAuthenticated(true)} />
  return <App onLogout={authEnabled ? handleLogout : undefined} />
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode><Root /></React.StrictMode>
)
