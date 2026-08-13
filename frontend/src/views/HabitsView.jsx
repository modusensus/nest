import { useRef, useEffect, useState } from 'react'
import { api, post } from '../api'
import Heatmap from '../components/Heatmap'

export default function HabitsView({ onDataChanged }) {
  const [habits, setHabits] = useState([])
  const [logs, setLogs] = useState({})
  const [name, setName] = useState('')
  const nameRef = useRef(null)

  const load = () => {
    api('/habits').then(setHabits)
    api('/habit-logs?days=371').then(rows =>
      setLogs(Object.fromEntries(rows.map(r => [r.date, r.count])))
    )
  }
  useEffect(() => { load() }, [])

  async function create(e) {
    e.preventDefault()
    if (!name.trim()) return
    await post('/habits', { name: name.trim() })
    setName('')
    load(); onDataChanged()
  }

  async function toggle(id) {
    await post(`/habits/${id}/checkin`)
    load(); onDataChanged()
  }

  async function remove(id) {
    if (!confirm('删除这个习惯及其全部打卡记录？')) return
    await api(`/habits/${id}`, { method: 'DELETE' })
    load(); onDataChanged()
  }

  const totalCheckins = Object.values(logs).reduce((a, b) => a + b, 0)

  return (
    <section className="wb-view">
      <header className="wb-view-header">
        <h2>打卡</h2>
        <p>每天点一下，或者对 Agent 说「今天健身打卡」。</p>
      </header>
      <form className="wb-form" onSubmit={create}>
        <input ref={nameRef} autoFocus value={name} onChange={e => setName(e.target.value)} placeholder="新习惯，如：健身、阅读、早起" />
        <button className="primary" type="submit">添加习惯</button>
      </form>
      <div className="wb-cards wb-cards-wide">
        <div className="wb-card wb-heat-card">
          <div className="wb-card-head">
            <strong>全部习惯 · 近一年</strong>
            <span className="wb-muted">共 {totalCheckins} 次打卡</span>
          </div>
          <Heatmap data={logs} weeks={53} showMonths />
          <div className="wb-heat-legend">
            <span className="wb-muted">少</span>
            {[0, 1, 2, 3, 4].map(lv => <i key={lv} data-lv={lv} />)}
            <span className="wb-muted">多</span>
          </div>
        </div>
      </div>
      <div className="wb-cards">
        {habits.map(h => (
          <div key={h.id} className="wb-card">
            <div className="wb-card-head">
              <strong>{h.name}</strong>
              <span className="wb-card-actions">
                <button onClick={() => remove(h.id)}>删除</button>
              </span>
            </div>
            <div className="wb-habit-stats">
              <span>连续 <b>{h.streak}</b> 天</span>
              <span>累计 <b>{h.total_days}</b> 天</span>
              <button
                className={h.checked_today ? 'wb-checkin done' : 'wb-checkin'}
                onClick={() => toggle(h.id)}
              >
                {h.checked_today ? '✓ 今日已打卡' : '今日打卡'}
              </button>
            </div>
            <Heatmap data={Object.fromEntries(h.recent.map(d => [d, 1]))} weeks={5} />
          </div>
        ))}
        {habits.length === 0 && (
          <div className="wb-empty-inline">
            <p className="wb-muted">还没有打卡习惯。添加一个，开始积累连续天数。</p>
            <button className="wb-ghost" onClick={() => nameRef.current?.focus()}>添加第一个习惯</button>
          </div>
        )}
      </div>
    </section>
  )
}
