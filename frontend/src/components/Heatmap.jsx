function fmt(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

function levelOf(count) {
  if (count <= 0) return 0
  if (count === 1) return 1
  if (count === 2) return 2
  if (count === 3) return 3
  return 4
}

/**
 * GitHub 风格热力图：7 行（周一到周日）× N 周。
 * showMonths 时在顶部渲染月份标签（一月处带年份），年视图传 weeks=53。
 * 颜色走 CSS 变量，自动跟随明暗主题。
 */
export default function Heatmap({ data, weeks = 26, showMonths = false }) {
  const today = new Date()
  const start = new Date(today)
  start.setDate(today.getDate() - (weeks * 7 - 1))
  start.setDate(start.getDate() - ((start.getDay() + 6) % 7)) // 对齐到周一

  const columns = []
  let current = []
  const cursor = new Date(start)
  while (cursor <= today) {
    const key = fmt(cursor)
    current.push({ date: key, count: data[key] || 0 })
    if (current.length === 7) { columns.push(current); current = [] }
    cursor.setDate(cursor.getDate() + 1)
  }
  if (current.length) columns.push(current)

  const months = []
  if (showMonths) {
    let lastMonth = null
    columns.forEach((col, i) => {
      const [year, month] = col[0].date.split('-')
      if (month !== lastMonth) {
        months.push({ index: i, label: month === '01' ? `${year}年1月` : `${Number(month)}月` })
        lastMonth = month
      }
    })
  }

  const gridStyle = { gridTemplateColumns: `repeat(${columns.length}, 12px)` }
  return (
    <div className="wb-heat-wrap">
      {showMonths && (
        <div className="wb-heat-months" style={gridStyle}>
          {months.map(m => <span key={m.index} style={{ gridColumnStart: m.index + 1 }}>{m.label}</span>)}
        </div>
      )}
      <div className="wb-heat" style={gridStyle} role="img" aria-label="打卡热力图">
        {columns.flat().map(c => (
          <span key={c.date} data-lv={levelOf(c.count)} title={`${c.date} · ${c.count} 次打卡`} />
        ))}
      </div>
    </div>
  )
}
