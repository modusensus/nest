import { useRef, useEffect, useState } from 'react'
import { api, post } from '../api'

export default function ProjectsView({ onDataChanged }) {
  const [projects, setProjects] = useState([])
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const nameRef = useRef(null)

  const load = () => api('/projects').then(setProjects)
  useEffect(() => { load() }, [])

  async function create(e) {
    e.preventDefault()
    if (!name.trim()) return
    await post('/projects', { name: name.trim(), description: description.trim() })
    setName(''); setDescription('')
    load(); onDataChanged()
  }

  async function archive(id) {
    await post(`/projects/${id}`, { status: 'archived' }, 'PATCH')
    load(); onDataChanged()
  }

  async function remove(id) {
    if (!confirm('删除项目？其任务会保留但不再归属该项目。')) return
    await api(`/projects/${id}`, { method: 'DELETE' })
    load(); onDataChanged()
  }

  return (
    <section className="wb-view">
      <header className="wb-view-header">
        <h2>项目</h2>
        <p>跟踪每个项目的任务完成情况。</p>
      </header>
      <form className="wb-form" onSubmit={create}>
        <input ref={nameRef} autoFocus value={name} onChange={e => setName(e.target.value)} placeholder="项目名称" />
        <input value={description} onChange={e => setDescription(e.target.value)} placeholder="描述（可选）" />
        <button className="primary" type="submit">创建项目</button>
      </form>
      <div className="wb-cards">
        {projects.map(p => {
          const percent = p.task_total ? Math.round((p.task_done / p.task_total) * 100) : 0
          return (
            <div key={p.id} className="wb-card">
              <div className="wb-card-head">
                <strong>{p.name}</strong>
                <span className="wb-card-actions">
                  <button onClick={() => archive(p.id)}>归档</button>
                  <button onClick={() => remove(p.id)}>删除</button>
                </span>
              </div>
              {p.description && <p className="wb-muted">{p.description}</p>}
              <div className="wb-progress"><div style={{ width: `${percent}%` }} /></div>
              <p className="wb-muted">完成 {p.task_done} / {p.task_total} 个任务（{percent}%）</p>
            </div>
          )
        })}
        {projects.length === 0 && (
          <div className="wb-empty-inline">
            <p className="wb-muted">还没有项目。可以在这里创建，或直接对 Agent 说「帮我建一个项目」。</p>
            <button className="wb-ghost" onClick={() => nameRef.current?.focus()}>创建第一个项目</button>
          </div>
        )}
      </div>
    </section>
  )
}
