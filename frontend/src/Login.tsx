import { useState } from 'react'
import { login, completeNewPassword } from './auth'

export default function Login({ onLogin }: { onLogin: () => void }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [error, setError] = useState('')
  const [pendingUser, setPendingUser] = useState<any>(null)

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault(); setError('')
    try {
      const result = await login(email, password)
      if (result.newPasswordRequired && result.userObj) {
        setPendingUser(result.userObj)
      } else {
        onLogin()
      }
    } catch (err: any) { setError(err.message || 'Login failed') }
  }

  const handleNewPassword = async (e: React.FormEvent) => {
    e.preventDefault(); setError('')
    try {
      await completeNewPassword(pendingUser, newPassword)
      onLogin()
    } catch (err: any) { setError(err.message || 'Failed to set password') }
  }

  if (pendingUser) {
    return (
      <div className="login-container">
        <form className="login-form" onSubmit={handleNewPassword}>
          <h2>Set New Password</h2>
          <p>You must set a new password on first login.</p>
          {error && <div className="error">{error}</div>}
          <input type="password" value={newPassword} onChange={e => setNewPassword(e.target.value)}
            placeholder="New password" required autoFocus />
          <button className="btn primary" type="submit">Set Password & Login</button>
        </form>
      </div>
    )
  }

  return (
    <div className="login-container">
      <form className="login-form" onSubmit={handleLogin}>
        <h2>🔐 SQS Admin Panel</h2>
        {error && <div className="error">{error}</div>}
        <input type="email" value={email} onChange={e => setEmail(e.target.value)}
          placeholder="Email" required autoFocus />
        <input type="password" value={password} onChange={e => setPassword(e.target.value)}
          placeholder="Password" required />
        <button className="btn primary" type="submit">Sign In</button>
      </form>
    </div>
  )
}
