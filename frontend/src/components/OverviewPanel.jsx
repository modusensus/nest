export default function OverviewPanel({ overview }) {
  if (!overview) return <aside className="wb-overview" />
  return (
    <aside className="wb-overview">
      <h3>工作台概况</h3>
      <div className="wb-ov-section">
        <h4>项目进度</h4>
        {overview.projects.length === 0 && <p className="wb-muted">暂无项目</p>}
        {overview.projects.map(p => {
          const percent = p.task_total ? Math.round((p.task_done / p.task_total) * 100) : 0
          return (
            <div key={p.id} className="wb-ov-project">
              <div className="wb-ov-line"><span>{p.name}</span><span className="wb-muted">{p.task_done}/{p.task_total}</span></div>
              <div className="wb-progress small"><div style={{ width: `${percent}%` }} /></div>
            </div>
          )
        })}
      </div>
      <div className="wb-ov-section">
        <h4>进行中 · {overview.tasks_doing.length}</h4>
        {overview.tasks_doing.length === 0 && <p className="wb-muted">没有进行中的任务</p>}
        {overview.tasks_doing.map(t => <div key={t.id} className="wb-ov-task">{t.title}</div>)}
        <p className="wb-muted">待办 {overview.tasks_todo_count} · 已完成 {overview.tasks_done_count}</p>
      </div>
      <div className="wb-ov-section">
        <h4>今日打卡</h4>
        {overview.habits.length === 0 && <p className="wb-muted">暂无习惯</p>}
        <div className="wb-ov-habits">
          {overview.habits.map(h => (
            <span key={h.id} className={h.checked_today ? 'wb-habit-chip on' : 'wb-habit-chip'}>
              {h.name}{h.checked_today ? ` · ${h.streak} 天` : ''}
            </span>
          ))}
        </div>
      </div>
    </aside>
  )
}
