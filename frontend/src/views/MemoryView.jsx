import { useEffect, useState, useCallback } from 'react'
import { api, post } from '../api'

export default function MemoryView() {
  const [tab, setTab] = useState('files')
  const [memories, setMemories] = useState([])
  const [memory, setMemory] = useState(null)
  const [proposals, setProposals] = useState([])
  const [facts, setFacts] = useState([])
  const [busy, setBusy] = useState(null)

  const loadMemories = useCallback(() => api('/memories').then(setMemories).catch(() => {}), [])
  const loadProposals = useCallback(() => api('/memory-proposals').then(setProposals).catch(() => {}), [])
  const loadFacts = useCallback(() => api('/memory-facts').then(setFacts).catch(() => {}), [])

  useEffect(() => {
    loadMemories()
    loadProposals()
    loadFacts()
  }, [loadMemories, loadProposals, loadFacts])

  const pendingCount = proposals.filter(p => p.status === 'pending').length

  async function openMemory(path) {
    setMemory(await api(`/memories/${path}`))
  }

  async function approveProposal(id) {
    setBusy(id)
    try {
      await post(`/memory-proposals/${id}/approve`, {}, 'POST')
      await loadProposals()
      await loadMemories()
    } catch (e) { alert(e.message) }
    setBusy(null)
  }

  async function rejectProposal(id) {
    setBusy(id)
    try {
      await post(`/memory-proposals/${id}/reject`, {}, 'POST')
      await loadProposals()
    } catch (e) { alert(e.message) }
    setBusy(null)
  }

  async function deleteFact(id) {
    if (!confirm('确定删除这条跨聊天记忆吗？')) return
    await api(`/memory-facts/${id}`, { method: 'DELETE' })
    loadFacts()
  }

  const actionLabel = { create: '新建', update: '更新', delete: '删除' }

  return (
    <section className="wb-view wb-memory-view">
      <header className="wb-view-header">
        <h2>记忆库</h2>
        <p>Agent 可在对话中提议创建、更新或删除记忆文件，经你审批后生效。跨聊天记忆则在所有对话中自动生效。</p>
      </header>

      <div className="wb-memory-tabs">
        <button className={tab === 'files' ? 'active' : ''} onClick={() => setTab('files')}>文件 ({memories.length})</button>
        <button className={tab === 'proposals' ? 'active' : ''} onClick={() => setTab('proposals')}>
          待审批 {pendingCount > 0 && <span className="wb-badge">{pendingCount}</span>}
        </button>
        <button className={tab === 'facts' ? 'active' : ''} onClick={() => setTab('facts')}>跨聊天记忆 ({facts.length})</button>
      </div>

      {tab === 'files' && (
        <div className="wb-memory">
          <div className="wb-memory-list">
            {memories.length === 0 ? (
              <p className="wb-muted">还没有记忆文件。对 Agent 说「帮我写一个记忆文件」即可。</p>
            ) : memories.map(m => (
              <button key={m.path} onClick={() => openMemory(m.path)}>{m.path}</button>
            ))}
          </div>
          <article className="wb-memory-content">
            {memory ? (<><h3>{memory.path}</h3><pre>{memory.content}</pre></>) : <p className="wb-muted">选择一个文件阅读。记忆文件为只读，如需修改请与 Agent 对话。</p>}
          </article>
        </div>
      )}

      {tab === 'proposals' && (
        <div className="wb-proposals">
          {proposals.length === 0 ? (
            <p className="wb-muted">暂无提案。</p>
          ) : proposals.map(p => (
            <div key={p.id} className={`wb-proposal ${p.status}`}>
              <div className="wb-proposal-head">
                <span className="wb-proposal-action">{actionLabel[p.action] || p.action}</span>
                <code className="wb-proposal-path">{p.file_path}</code>
                <span className={`wb-proposal-status ${p.status}`}>{p.status === 'pending' ? '待审批' : p.status === 'approved' ? '已批准' : '已驳回'}</span>
              </div>
              {p.reason && <p className="wb-proposal-reason">理由：{p.reason}</p>}
              {p.action !== 'delete' && p.content && (
                <pre className="wb-proposal-content">{p.content}</pre>
              )}
              {p.status === 'pending' && (
                <div className="wb-proposal-actions">
                  <button className="primary" disabled={busy === p.id} onClick={() => approveProposal(p.id)}>批准</button>
                  <button disabled={busy === p.id} onClick={() => rejectProposal(p.id)}>驳回</button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {tab === 'facts' && (
        <div className="wb-facts">
          <p className="wb-muted">这些记忆会在所有对话中自动注入给 Agent，类似 ChatGPT 的跨聊天记忆。Agent 在对话中了解到你的长期信息时会自动保存。</p>
          {facts.length === 0 ? (
            <p className="wb-muted">还没有跨聊天记忆。和 Agent 聊聊你的偏好、计划或背景，它会自动记住。</p>
          ) : facts.map(f => (
            <div key={f.id} className="wb-fact">
              <span className="wb-fact-cat">{f.category}</span>
              <span className="wb-fact-content">{f.content}</span>
              <button onClick={() => deleteFact(f.id)}>×</button>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
