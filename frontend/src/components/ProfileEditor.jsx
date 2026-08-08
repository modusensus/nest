import { useState } from 'react'
import { api } from '../api'

export default function ProfileEditor({ profile, onClose, onSaved }) {
  const [name, setName] = useState(profile?.name || '')
  const [agentId, setAgentId] = useState(profile?.agent_id || '')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function save(e) {
    e.preventDefault()
    setBusy(true); setError('')
    try {
      const updated = await api('/profile', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, agent_id: agentId }),
      })
      onSaved(updated)
      onClose()
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  async function uploadAvatar(file) {
    if (!file) return
    setBusy(true); setError('')
    try {
      const response = await fetch('/api/profile/avatar', {
        method: 'POST',
        headers: { 'Content-Type': 'application/octet-stream' },
        body: file,
      })
      if (!response.ok) throw new Error((await response.json()).detail || '上传失败')
      onSaved(await response.json())
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  return (
    <div className="wb-modal-mask" onClick={onClose}>
      <form className="wb-modal" onClick={e => e.stopPropagation()} onSubmit={save}>
        <h3>个人信息</h3>
        <div className="wb-modal-avatar">
          {profile?.avatar_url
            ? <img className="wb-avatar large" src={profile.avatar_url} alt="头像" />
            : <span className="wb-avatar large wb-avatar-fallback">◈</span>}
          <label className="wb-upload">
            更换头像
            <input type="file" accept="image/*" hidden onChange={e => uploadAvatar(e.target.files[0])} />
          </label>
        </div>
        <label className="wb-field">
          <span>名称</span>
          <input value={name} onChange={e => setName(e.target.value)} placeholder="展示名称" />
        </label>
        <label className="wb-field">
          <span>Agent ID</span>
          <input value={agentId} onChange={e => setAgentId(e.target.value)} placeholder="你的 Agent 代号" />
        </label>
        {error && <p className="wb-modal-error">{error}</p>}
        <div className="wb-modal-actions">
          <button type="button" className="wb-ghost" onClick={onClose}>取消</button>
          <button type="submit" className="primary" disabled={busy}>{busy ? '保存中…' : '保存'}</button>
        </div>
      </form>
    </div>
  )
}
