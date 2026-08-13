import { useEffect, useState } from 'react'
import { api, post } from '../api'
import Heatmap from '../components/Heatmap'

const WEEKDAYS = ['日', '一', '二', '三', '四', '五', '六']

function daysLeft(targetDate) {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const target = new Date(`${targetDate}T00:00:00`)
  return Math.round((target - today) / 86400000)
}

export default function HomeView({ profile, onNavigate, onDataChanged }) {
  const [overview, setOverview] = useState(null)
  const [logs, setLogs] = useState({})
  const [articles, setArticles] = useState([])
  const [countdowns, setCountdowns] = useState([])
  const [cdTitle, setCdTitle] = useState('')
  const [cdDate, setCdDate] = useState('')
  const [, setTick] = useState(0)

  const load = () => {
    api('/overview').then(setOverview)
    api('/habit-logs?days=154').then(rows => setLogs(Object.fromEntries(rows.map(r => [r.date, r.count]))))
    api('/articles').then(setArticles)
    api('/countdowns').then(setCountdowns)
  }
  useEffect(() => { load() }, [])
  // 每小时自动刷新一次，跨天后倒计时数字自动更新
  useEffect(() => {
    const timer = setInterval(() => setTick(t => t + 1), 60 * 60 * 1000)
    return () => clearInterval(timer)
  }, [])

  async function toggleHabit(id) {
    await post(`/habits/${id}/checkin`)
    load(); onDataChanged()
  }

  async function addCountdown(e) {
    e.preventDefault()
    if (!cdTitle.trim() || !cdDate) return
    await post('/countdowns', { title: cdTitle.trim(), target_date: cdDate })
    setCdTitle(''); setCdDate('')
    load()
  }

  async function removeCountdown(id) {
    await api(`/countdowns/${id}`, { method: 'DELETE' })
    load()
  }

  const now = new Date()
  const hour = now.getHours()
  const greeting = hour < 6 ? '夜深了' : hour < 12 ? '早上好' : hour < 18 ? '下午好' : '晚上好'
  const dateLine = `${now.getMonth() + 1} 月 ${now.getDate()} 日 · 星期${WEEKDAYS[now.getDay()]}`
  const yearStart = new Date(now.getFullYear(), 0, 0)
  const dayOfYear = Math.floor((now - yearStart) / 86400000)
  const edition = `Vol. ${now.getFullYear()} · No. ${String(dayOfYear).padStart(3, '0')}`
  const habits = overview?.habits || []
  const checkedCount = habits.filter(h => h.checked_today).length
  const userName = profile?.name?.replace(/['’]s Home$/i, '') || '朋友'

  // 本周概览：从本周一累计打卡次数
  const monday = new Date(now)
  monday.setHours(0, 0, 0, 0)
  monday.setDate(monday.getDate() - ((monday.getDay() + 6) % 7))
  const weekKey = `${monday.getFullYear()}-${String(monday.getMonth() + 1).padStart(2, '0')}-${String(monday.getDate()).padStart(2, '0')}`
  const weekCheckins = Object.entries(logs)
    .filter(([d]) => d >= weekKey)
    .reduce((sum, [, c]) => sum + c, 0)
  const doingTasks = overview?.tasks_doing.length ?? 0
  const doneTasks = overview?.tasks_done_count ?? 0
  const todoTasks = overview?.tasks_todo_count ?? 0
  const projTotal = (overview?.projects || []).reduce((s, p) => s + (p.task_total || 0), 0)
  const projDone = (overview?.projects || []).reduce((s, p) => s + (p.task_done || 0), 0)
  const projPercent = projTotal ? Math.round((projDone / projTotal) * 100) : 0

  // 当月日历单元格（含前置空位，共 42 格）
  const year = now.getFullYear()
  const month = now.getMonth()
  const daysInMonth = new Date(year, month + 1, 0).getDate()
  const firstDay = new Date(year, month, 1).getDay()
  const calendarCells = Array.from({ length: 42 }, (_, i) => {
    const day = i - firstDay + 1
    if (day < 1 || day > daysInMonth) return null
    const isToday = day === now.getDate()
    return { day, isToday }
  })

  return (
    <section className="wb-view wb-home">
      <header className="wb-masthead">
        <div className="wb-masthead-top">
          <span className="wb-masthead-edition">{edition}</span>
          <span className="wb-masthead-date">{dateLine}</span>
        </div>
        <h1 className="wb-masthead-title">{greeting}，<em>{userName}</em></h1>
        <p className="wb-masthead-standfirst">
          今日打卡 <b>{checkedCount}/{habits.length}</b> · 进行中任务 <b>{overview?.tasks_doing.length ?? 0}</b> · 文章 <b>{articles.length}</b> 篇 —— 这是你的个人工作台每日刊。
        </p>
      </header>

      {/* 本周概览：编辑带式统计条 */}
      <div className="wb-weekstrip">
        <span className="wb-weekstrip-label">本周概览</span>
        <div className="wb-weekstat"><b>{weekCheckins}</b><span>次打卡</span></div>
        <div className="wb-weekstat"><b>{doingTasks}</b><span>进行中</span></div>
        <div className="wb-weekstat"><b>{doneTasks}</b><span>已完成</span></div>
        <div className="wb-weekstat"><b>{todoTasks}</b><span>待办</span></div>
        <div className="wb-weekstat"><b>{articles.length}</b><span>文章</span></div>
        <div className="wb-weekstat"><b>{projPercent}%</b><span>项目进度</span></div>
      </div>

      <div className="wb-home-wide">
        <div className="wb-home-top-row">
          {/* 倒计时卡片 —— 始终显示，表单常驻 */}
          <div className="wb-card wb-home-countdowns">
            <div className="wb-card-head">
              <strong>目标倒计时</strong>
              <span className="eyebrow">Deadlines</span>
            </div>
            {countdowns.length === 0 && <p className="wb-muted">还没有倒计时，添加一个目标日吧。</p>}
            {countdowns.map(cd => {
              const left = daysLeft(cd.target_date)
              return (
                <div key={cd.id} className="wb-countdown">
                  <div className="wb-countdown-info">
                    <strong>{cd.title}</strong>
                    <span className="wb-muted">{cd.target_date}</span>
                  </div>
                  <div className="wb-countdown-days">
                    {left > 0 ? (<><b>{left}</b><span>天后</span></>)
                      : left === 0 ? (<><b>今天</b></>)
                      : (<><b>{-left}</b><span>天前已过</span></>)}
                  </div>
                  <button className="wb-countdown-del" onClick={() => removeCountdown(cd.id)} title="删除">×</button>
                </div>
              )
            })}
            <form className="wb-countdown-form" onSubmit={addCountdown}>
              <input value={cdTitle} onChange={e => setCdTitle(e.target.value)} placeholder="目标名称" />
              <input type="date" value={cdDate} onChange={e => setCdDate(e.target.value)} />
              <button className="primary" type="submit">添加</button>
            </form>
          </div>

          {/* 日历卡片 —— 与倒计时左右对齐 */}
          <div className="wb-card wb-home-calendar">
            <div className="wb-card-head">
              <strong>{now.getFullYear()} 年 {now.getMonth() + 1} 月</strong>
              <span className="eyebrow">Calendar</span>
            </div>
            <div className="wb-cal-grid">
              {WEEKDAYS.map(d => <span key={d} className="wb-cal-dow">{d}</span>)}
              {calendarCells.map((cell, i) => (
                <span key={i} className={`wb-cal-day ${cell?.isToday ? 'today' : ''} ${cell ? '' : 'empty'}`}>
                  {cell?.day || ''}
                </span>
              ))}
            </div>
          </div>
        </div>

        <div className="wb-card">
          <div className="wb-card-head">
            <strong>坚持热力图</strong>
            <button className="wb-link" onClick={() => onNavigate('habits')}>进入打卡 →</button>
          </div>
          <Heatmap data={logs} weeks={22} showMonths />
        </div>
      </div>

      <div className="wb-masonry">
        <div className="wb-card">
          <div className="wb-card-photo" style={{ backgroundImage: 'url(/photos/p2.jpg)' }} />
          <div className="wb-kicker">Nº 01 — 习惯</div>
          <div className="wb-card-head">
            <strong>今日打卡</strong>
            <button className="wb-link" onClick={() => onNavigate('habits')}>管理习惯 →</button>
          </div>
          <div className="wb-home-habits">
            {habits.length === 0 && <p className="wb-muted">还没有习惯，去打卡页添加一个吧。</p>}
            {habits.map(h => (
              <button key={h.id} className={h.checked_today ? 'wb-home-habit on' : 'wb-home-habit'} onClick={() => toggleHabit(h.id)}>
                <span className="wb-home-habit-check">{h.checked_today ? '✓' : ''}</span>
                <span>{h.name}</span>
                {h.streak > 0 && <small>{h.streak} 天</small>}
              </button>
            ))}
          </div>
        </div>

        <div className="wb-card">
          <div className="wb-card-photo tall" style={{ backgroundImage: 'url(/photos/p3.jpg)' }} />
          <div className="wb-kicker">Nº 02 — 项目</div>
          <div className="wb-card-head">
            <strong>项目进度</strong>
            <button className="wb-link" onClick={() => onNavigate('projects')}>全部项目 →</button>
          </div>
          {(overview?.projects || []).length === 0 && <p className="wb-muted">暂无项目。</p>}
          {(overview?.projects || []).map(p => {
            const percent = p.task_total ? Math.round((p.task_done / p.task_total) * 100) : 0
            return (
              <div key={p.id} className="wb-ov-project">
                <div className="wb-ov-line"><span>{p.name}</span><span className="wb-muted">{p.task_done}/{p.task_total}</span></div>
                <div className="wb-progress small"><div style={{ width: `${percent}%` }} /></div>
              </div>
            )
          })}
        </div>

        <div className="wb-card">
          <div className="wb-card-photo tall" style={{ backgroundImage: 'url(/photos/p4.jpg)' }} />
          <div className="wb-kicker">Nº 03 — 任务</div>
          <div className="wb-card-head">
            <strong>进行中的任务</strong>
            <button className="wb-link" onClick={() => onNavigate('tasks')}>任务看板 →</button>
          </div>
          {(overview?.tasks_doing || []).length === 0 && <p className="wb-muted">没有进行中的任务。</p>}
          {(overview?.tasks_doing || []).map(t => <div key={t.id} className="wb-ov-task">{t.title}</div>)}
        </div>

        <div className="wb-card">
          <div className="wb-card-photo" style={{ backgroundImage: 'url(/photos/p1.jpg)' }} />
          <div className="wb-kicker">Nº 04 — 写作</div>
          <div className="wb-card-head">
            <strong>最近文章</strong>
            <button className="wb-link" onClick={() => onNavigate('writing')}>去写作 →</button>
          </div>
          {articles.length === 0 && <p className="wb-muted">还没有文章，开始写第一篇吧。</p>}
          {articles.slice(0, 4).map(a => (
            <div key={a.id} className="wb-home-article" onClick={() => onNavigate('writing', a.id)}>
              <span className={a.status === 'published' ? 'wb-status published' : 'wb-status'}>{a.status === 'published' ? '已发布' : '草稿'}</span>
              <span className="wb-home-article-title">{a.title}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
