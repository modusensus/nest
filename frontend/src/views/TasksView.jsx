import { useEffect, useState } from 'react'
import { api, post } from '../api'

const COLUMNS = [
  { id: 'todo', label: '待办' },
  { id: 'doing', label: '进行中' },
  { id: 'done', label: '已完成' },
]
const NEXT = { todo: 'doing', doing: 'done' }
const PREV = { doing: 'todo', done: 'doing' }

export default function TasksView({ onDataChanged }) {
  const [tasks, setTasks] = useState([])
  const [projects, setProjects] = useState([])
  const [title, setTitle] = useState('')
  const [projectId, setProjectId] = useState('')
  const [dueDate, setDueDate] = useState('')

  const load = () => {
    api('/tasks').then(setTasks)
    api('/projects').then(setProjects)
  }
  useEffect(() => { load() }, [])

  async function create(e) {
    e.preventDefault()
    if (!title.trim()) return
    await post('/tasks', { title: title.trim(), project_id: projectId || null, due_date: dueDate })
    setTitle(''); setDueDate('')
    load(); onDataChanged()
  }

  async function move(id, status) {
    await post(`/tasks/${id}`, { status }, 'PATCH')
    load(); onDataChanged()
  }

  async function remove(id) {
    await api(`/tasks/${id}`, { method: 'DELETE' })
    load(); onDataChanged()
  }

  return (
    <section className="wb-view">
      <header className="wb-view-header">
        <h2>任务看板</h2>
        <p>拖动不了就点箭头：任务在待办 → 进行中 → 已完成之间流转。</p>
      </header>
      <form className="wb-form" onSubmit={create}>
        <input value={title} onChange={e => setTitle(e.target.value)} placeholder="任务标题" />
        <select value={projectId} onChange={e => setProjectId(e.target.value)}>
          <option value="">不归属项目</option>
          {projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
        <input type="date" value={dueDate} onChange={e => setDueDate(e.target.value)} />
        <button className="primary" type="submit">添加任务</button>
      </form>
      <div className="wb-kanban">
        {COLUMNS.map(col => (
          <div key={col.id} className="wb-kanban-col">
            <h3>{col.label} · {tasks.filter(t => t.status === col.id).length}</h3>
            {tasks.filter(t => t.status === col.id).map(t => (
              <div key={t.id} className={`wb-task ${t.status}`}>
                <div className="wb-task-title">{t.title}</div>
                <div className="wb-task-meta">
                  {t.project_name && <span className="wb-tag">{t.project_name}</span>}
                  {t.due_date && <span className="wb-muted">截止 {t.due_date}</span>}
                </div>
                <div className="wb-task-actions">
                  {PREV[t.status] && <button onClick={() => move(t.id, PREV[t.status])}>← 退回</button>}
                  {NEXT[t.status] && <button onClick={() => move(t.id, NEXT[t.status])}>{NEXT[t.status] === 'doing' ? '开始 →' : '完成 ✓'}</button>}
                  <button onClick={() => remove(t.id)}>删除</button>
                </div>
              </div>
            ))}
          </div>
        ))}
      </div>
    </section>
  )
}
