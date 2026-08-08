import { useEffect, useRef, useState } from 'react'
import { api, post, getBaseUrl } from '../api'
import { renderMarkdown } from '../lib/markdown'

const PLATFORMS = [
  { id: 'blog', label: '个人博客' },
  { id: 'substack', label: 'Substack' },
  { id: 'medium', label: 'Medium' },
]

export default function WritingView({ focusArticleId, onDataChanged }) {
  const [articles, setArticles] = useState([])
  const [active, setActive] = useState(null)
  const [saving, setSaving] = useState(false)
  const [dirty, setDirty] = useState(false)
  const [showPreview, setShowPreview] = useState(true)
  const dirtyRef = useRef(false)

  const loadList = () => api('/articles').then(setArticles)
  useEffect(() => { loadList() }, [])
  useEffect(() => { if (focusArticleId) open(focusArticleId) }, [focusArticleId]) // eslint-disable-line

  async function open(id) {
    if (dirtyRef.current && !confirm('当前文章有未保存的修改，确定离开吗？')) return
    const article = await api(`/articles/${id}`)
    setActive(article)
    setDirty(false); dirtyRef.current = false
  }

  async function create() {
    const article = await post('/articles', { title: '未命名文章' })
    await loadList()
    open(article.id)
  }

  function patch(changes) {
    setActive(a => ({ ...a, ...changes }))
    setDirty(true); dirtyRef.current = true
  }

  async function save() {
    if (!active || saving) return
    setSaving(true)
    try {
      const updated = await post(`/articles/${active.id}`, {
        title: active.title, content: active.content, status: active.status, platforms: active.platforms,
      }, 'PATCH')
      setActive(updated)
      setDirty(false); dirtyRef.current = false
      loadList(); onDataChanged()
    } finally { setSaving(false) }
  }

  async function remove() {
    if (!active || !confirm(`删除文章「${active.title}」？`)) return
    await api(`/articles/${active.id}`, { method: 'DELETE' })
    setActive(null)
    loadList(); onDataChanged()
  }

  async function uploadImage(file, textarea) {
    if (!file) return
    const response = await fetch(`${getBaseUrl()}/api/articles/images`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/octet-stream' },
      body: file,
    })
    if (!response.ok) { alert((await response.json()).detail || '上传失败'); return }
    const { url } = await response.json()
    const tag = `![配图](${url})`
    const el = textarea
    const content = active.content
    const at = el ? el.selectionStart : content.length
    patch({ content: content.slice(0, at) + tag + content.slice(at) })
  }

  function exportMarkdown() {
    const blob = new Blob([`# ${active.title}\n\n${active.content}`], { type: 'text/markdown;charset=utf-8' })
    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.download = `${active.title}.md`
    link.click()
    URL.revokeObjectURL(link.href)
  }

  function setPlatform(id, changes) {
    patch({ platforms: { ...active.platforms, [id]: { url: '', published: false, ...(active.platforms[id] || {}), ...changes } } })
  }

  const textareaRef = useRef(null)

  return (
    <section className="wb-writing">
      <div className="wb-writing-list">
        <button className="primary" onClick={create}>＋ 新文章</button>
        {articles.map(a => (
          <div key={a.id} className={`wb-writing-item ${active?.id === a.id ? 'active' : ''}`} onClick={() => open(a.id)}>
            <span className={a.status === 'published' ? 'wb-status published' : 'wb-status'}>{a.status === 'published' ? '已发布' : '草稿'}</span>
            <span className="wb-writing-item-title">{a.title}</span>
            <small>{(a.updated_at || '').slice(0, 10)}</small>
          </div>
        ))}
        {articles.length === 0 && <p className="wb-muted">还没有文章。</p>}
      </div>

      {!active ? (
        <div className="wb-empty" style={{ flex: 1 }}>
          <h1>写作</h1>
          <p>公众号、博客、Substack、Medium——在这里写，一次成稿，多处发布。</p>
        </div>
      ) : (
        <div className="wb-editor">
          <div className="wb-editor-toolbar">
            <input className="wb-editor-title" value={active.title} onChange={e => patch({ title: e.target.value })} placeholder="文章标题" />
            <select value={active.status} onChange={e => patch({ status: e.target.value })}>
              <option value="draft">草稿</option>
              <option value="published">已发布</option>
            </select>
            <label className="wb-ghost wb-upload-btn">
              插入配图
              <input type="file" accept="image/*" hidden onChange={e => uploadImage(e.target.files[0], textareaRef.current)} />
            </label>
            <button className="wb-ghost" onClick={() => setShowPreview(v => !v)}>{showPreview ? '隐藏预览' : '显示预览'}</button>
            <button className="wb-ghost" onClick={exportMarkdown}>导出 .md</button>
            <button className="wb-ghost" onClick={remove}>删除</button>
            <button className="primary" onClick={save} disabled={!dirty || saving}>{saving ? '保存中…' : dirty ? '保存' : '已保存'}</button>
          </div>
          <div className={showPreview ? 'wb-editor-body split' : 'wb-editor-body'}>
            <textarea
              ref={textareaRef}
              value={active.content}
              onChange={e => patch({ content: e.target.value })}
              placeholder={'用 Markdown 写作。\n\n# 标题\n**重点** *强调*\n- 列表\n点击「插入配图」上传图片。'}
            />
            {showPreview && (
              <article className="wb-preview" dangerouslySetInnerHTML={{ __html: renderMarkdown(active.content) }} />
            )}
          </div>
          <div className="wb-platforms">
            <h4>发布到平台</h4>
            <div className="wb-platform-rows">
              {PLATFORMS.map(p => {
                const state = active.platforms[p.id] || {}
                return (
                  <div key={p.id} className="wb-platform-row">
                    <label>
                      <input type="checkbox" checked={!!state.published} onChange={e => setPlatform(p.id, { published: e.target.checked })} />
                      {p.label}
                    </label>
                    <input
                      className="wb-platform-url"
                      value={state.url || ''}
                      onChange={e => setPlatform(p.id, { url: e.target.value })}
                      placeholder="已发布文章的链接（可选）"
                    />
                  </div>
                )
              })}
            </div>
            <p className="wb-muted">Substack 与公众号无公开 API：导出 Markdown 或全选正文粘贴到对应后台后，在这里勾选「已发布」并记录链接。保存文章时平台状态会一并保存。</p>
          </div>
        </div>
      )}
    </section>
  )
}
