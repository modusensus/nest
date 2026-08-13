import { StrictMode, useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import { getBaseUrl, setBaseUrl } from './api'
import './style.css'

function LoginGate() {
  const [ready, setReady] = useState(false)
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [serverUrl, setServerUrl] = useState(() => getBaseUrl() || '')

  useEffect(() => {
    const saved = localStorage.getItem('wb-theme') ||
      (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
    document.documentElement.dataset.theme = saved
    fetch(`${getBaseUrl()}/api/auth/me`).then(r => setReady(r.ok))
  }, [])

  if (ready) return <App />

  async function login(e) {
    e.preventDefault()
    setError('')
    setBaseUrl(serverUrl)
    const r = await fetch(`${serverUrl}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password }),
    })
    if (r.ok) setReady(true)
    else setError((await r.json()).detail || '登录失败')
  }

  return (
    <main style={{ minHeight: '100vh', display: 'grid', placeItems: 'center', padding: 20, background: 'var(--bg)' }}>
      <form onSubmit={login} className="wb-login-form" style={{
        width: 'min(100%, 400px)', padding: '40px 36px', background: 'var(--surface)',
        border: '1px solid var(--border)', borderRadius: 0, display: 'grid', gap: 6,
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 6 }}>
          <span className="brand">◈ 个人 AI 工作台</span>
          <span style={{ fontFamily: 'var(--mono)', fontSize: 10, letterSpacing: '.18em', color: 'var(--muted)', textTransform: 'uppercase' }}>Agent · Workbench</span>
        </div>
        <div style={{ borderTop: '2px solid var(--rule)', marginBottom: 14 }} />
        <h1 style={{ fontFamily: 'var(--serif)', fontWeight: 500, fontSize: 24, margin: 0, letterSpacing: '.02em' }}>欢迎回来</h1>
        <p style={{ margin: '0 0 18px', color: 'var(--muted)', fontSize: 13, fontFamily: 'var(--serif)', fontStyle: 'italic' }}>请输入服务器地址和访问密码，进入你的每日刊。</p>
        <input value={serverUrl} onChange={e => setServerUrl(e.target.value)}
          placeholder="服务器地址，如 http://192.168.1.100:8000"
          style={{ font: 'inherit', padding: 11, width: '100%' }} />
        <input autoFocus type="password" value={password} onChange={e => setPassword(e.target.value)}
          placeholder="访问密码" style={{ font: 'inherit', padding: 11, width: '100%' }} />
        <button className="primary" style={{ marginTop: 10, width: '100%' }}>进入工作台</button>
        {error && <p style={{ color: 'var(--accent)', margin: '8px 0 0', fontSize: 13 }}>{error}</p>}
      </form>
    </main>
  )
}

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => navigator.serviceWorker.register('/sw.js'))
}
createRoot(document.getElementById('root')).render(<StrictMode><LoginGate /></StrictMode>)
