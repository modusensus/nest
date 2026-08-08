import { StrictMode, useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import './style.css'

function LoginGate() {
  const [ready, setReady] = useState(false)
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    const saved = localStorage.getItem('wb-theme') ||
      (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
    document.documentElement.dataset.theme = saved
    fetch('/api/auth/me').then(r => setReady(r.ok))
  }, [])

  if (ready) return <App />

  async function login(e) {
    e.preventDefault()
    setError('')
    const r = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password }),
    })
    if (r.ok) setReady(true)
    else setError((await r.json()).detail || '登录失败')
  }

  return (
    <main style={{ minHeight: '100vh', display: 'grid', placeItems: 'center', padding: 20, background: 'var(--bg)' }}>
      <form onSubmit={login} style={{
        width: 'min(100%, 380px)', padding: '36px 32px', background: 'var(--surface)',
        border: '1px solid var(--border)', borderRadius: 2, display: 'grid', gap: 16,
      }}>
        <div className="brand">◈ 个人 AI 工作台</div>
        <h1 style={{ fontFamily: 'var(--serif)', fontWeight: 500, fontSize: 20, margin: 0, letterSpacing: '.03em' }}>欢迎回来</h1>
        <p style={{ margin: 0, color: 'var(--muted)', fontSize: 13 }}>请输入访问密码。</p>
        <input autoFocus type="password" value={password} onChange={e => setPassword(e.target.value)}
          placeholder="访问密码" style={{ font: 'inherit', padding: 10 }} />
        <button className="primary">进入工作台</button>
        {error && <p style={{ color: 'var(--accent)', margin: 0, fontSize: 13 }}>{error}</p>}
      </form>
    </main>
  )
}

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => navigator.serviceWorker.register('/sw.js'))
}
createRoot(document.getElementById('root')).render(<StrictMode><LoginGate /></StrictMode>)
