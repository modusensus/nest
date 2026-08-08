/** 轻量 Markdown 渲染：标题、列表、粗斜体、行内代码、链接、图片。仅用于本地预览。 */
export function renderMarkdown(md) {
  const esc = s => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
  const inline = s => esc(s)
    .replace(/!\[([^\]]*)\]\(([^)\s]+)\)/g, '<img alt="$1" src="$2" loading="lazy"/>')
    .replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/\*([^*\n]+)\*/g, '<em>$1</em>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')

  let html = ''
  let inList = false
  for (const line of (md || '').split('\n')) {
    const heading = line.match(/^(#{1,4})\s+(.*)/)
    if (heading) {
      if (inList) { html += '</ul>'; inList = false }
      const level = heading[1].length
      html += `<h${level}>${inline(heading[2])}</h${level}>`
      continue
    }
    if (/^\s*[-*]\s+/.test(line)) {
      if (!inList) { html += '<ul>'; inList = true }
      html += `<li>${inline(line.replace(/^\s*[-*]\s+/, ''))}</li>`
      continue
    }
    if (inList) { html += '</ul>'; inList = false }
    if (/^>\s?/.test(line)) { html += `<blockquote>${inline(line.replace(/^>\s?/, ''))}</blockquote>`; continue }
    if (line.trim() === '') continue
    html += `<p>${inline(line)}</p>`
  }
  if (inList) html += '</ul>'
  return html
}
