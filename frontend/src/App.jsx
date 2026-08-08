import { useCallback, useEffect, useState } from 'react'
import { api, post } from './api'
import HomeView from './views/HomeView'
import ChatView from './views/ChatView'
import ProjectsView from './views/ProjectsView'
import TasksView from './views/TasksView'
import HabitsView from './views/HabitsView'
import WritingView from './views/WritingView'
import MemoryView from './views/MemoryView'
import OverviewPanel from './components/OverviewPanel'
import ProfileEditor from './components/ProfileEditor'
import Icon from './components/Icon'
import ClaudePanel from './ClaudePanel'
import './workbench.css'

const NAV = [
  { id: 'home', label: '主页', icon: 'home' },
  { id: 'chat', label: '对话', icon: 'chat' },
  { id: 'projects', label: '项目', icon: 'folder' },
  { id: 'tasks', label: '任务看板', icon: 'kanban' },
  { id: 'habits', label: '打卡', icon: 'check' },
  { id: 'writing', label: '写作', icon: 'pen' },
  { id: 'claude', label: 'Claude Code', icon: 'terminal' },
  { id: 'memory', label: '记忆库', icon: 'book' },
]

const FULL_WIDTH_VIEWS = new Set(['home', 'writing'])

export default function App() {
  const [view, setView] = useState('home')
  const [conversations, setConversations] = useState([])
  const [activeId, setActiveId] = useState(null)
  const [search, setSearch] = useState('')
  const [overview, setOverview] = useState(null)
  const [dataVersion, setDataVersion] = useState(0)
  const [focusArticleId, setFocusArticleId] = useState(null)
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem('wb-sidebar') === 'collapsed')
  const [theme, setTheme] = useState(() =>
    localStorage.getItem('wb-theme') ||
    (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
  )
  const [profile, setProfile] = useState(null)
  const [editingProfile, setEditingProfile] = useState(false)

  const loadProfile = useCallback(() => api('/profile').then(setProfile).catch(() => {}), [])
  useEffect(() => { loadProfile() }, [loadProfile])

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    localStorage.setItem('wb-theme', theme)
  }, [theme])

  useEffect(() => {
    localStorage.setItem('wb-sidebar', collapsed ? 'collapsed' : 'expanded')
  }, [collapsed])

  const refreshData = useCallback(() => setDataVersion(v => v + 1), [])

  const loadConversations = useCallback(async (q = search) => {
    setConversations(await api(`/conversations?q=${encodeURIComponent(q)}`))
  }, [search])

  useEffect(() => { loadConversations('') }, []) // eslint-disable-line
  useEffect(() => {
    const timer = setTimeout(() => loadConversations(), 250)
    return () => clearTimeout(timer)
  }, [search]) // eslint-disable-line

  useEffect(() => {
    api('/overview').then(setOverview).catch(() => {})
  }, [dataVersion])

  function navigate(viewId, payload = null) {
    if (viewId === 'writing') setFocusArticleId(payload)
    setView(viewId)
  }

  async function createConversation() {
    const conversation = await post('/conversations')
    await loadConversations()
    setActiveId(conversation.id)
    setView('chat')
  }

  async function removeConversation(id) {
    if (!confirm('确定删除这个会话及其全部消息吗？')) return
    await api(`/conversations/${id}`, { method: 'DELETE' })
    if (activeId === id) setActiveId(null)
    loadConversations()
  }

  return (
    <div className="wb-app">
      <aside className={collapsed ? 'wb-sidebar collapsed' : 'wb-sidebar'}>
        <button className="wb-profile" onClick={() => setEditingProfile(true)} title="编辑个人信息">
          {profile?.avatar_url
            ? <img className="wb-avatar" src={profile.avatar_url} alt="头像" />
            : <span className="wb-avatar wb-avatar-fallback">◈</span>}
          {!collapsed && (
            <>
              <span className="wb-profile-text">
                <strong>{profile?.name || '个人 AI 工作台'}</strong>
                <small>Agent ID：{profile?.agent_id || '—'}</small>
              </span>
              <span className="wb-profile-edit">编辑</span>
            </>
          )}
        </button>
        <nav className="wb-nav">
          {NAV.map(item => (
            <button key={item.id} title={item.label} className={view === item.id ? 'active' : ''} onClick={() => navigate(item.id)}>
              <Icon name={item.icon} /> {!collapsed && <span>{item.label}</span>}
            </button>
          ))}
        </nav>
        {view === 'chat' && !collapsed && (
          <>
            <button className="primary" onClick={createConversation}>＋ 新建对话</button>
            <input className="search" value={search} onChange={e => setSearch(e.target.value)} placeholder="搜索聊天记录" />
            <div className="conversation-list">
              {conversations.map(c => (
                <div key={c.id} className={`conversation ${activeId === c.id ? 'selected' : ''}`} onClick={() => setActiveId(c.id)}>
                  <span>{c.title}</span>
                  <button onClick={e => { e.stopPropagation(); removeConversation(c.id) }}>×</button>
                </div>
              ))}
            </div>
          </>
        )}
        <button className="wb-theme-toggle" data-theme={theme} onClick={() => setTheme(t => (t === 'dark' ? 'light' : 'dark'))} title="切换日／夜刊">
          <span className="wb-theme-track">
            <span className="wb-theme-knob" />
            <span className="wb-theme-opt">日</span>
            <span className="wb-theme-opt">夜</span>
          </span>
          {!collapsed && <span className="wb-theme-label">{theme === 'dark' ? '夜刊' : '日刊'}</span>}
        </button>
        <button className="wb-collapse" onClick={() => setCollapsed(v => !v)} title={collapsed ? '展开导航' : '收起导航'}>
          {collapsed ? '»' : '«'}
        </button>
      </aside>
      <main className="wb-main">
        {view === 'home' && <HomeView profile={profile} onNavigate={navigate} onDataChanged={refreshData} />}
        {view === 'chat' && <ChatView conversationId={activeId} onDataChanged={refreshData} onConversationsChanged={loadConversations} />}
        {view === 'projects' && <ProjectsView onDataChanged={refreshData} />}
        {view === 'tasks' && <TasksView onDataChanged={refreshData} />}
        {view === 'habits' && <HabitsView onDataChanged={refreshData} />}
        {view === 'writing' && <WritingView focusArticleId={focusArticleId} onDataChanged={refreshData} />}
        {view === 'claude' && <ClaudePanel />}
        {view === 'memory' && <MemoryView />}
      </main>
      {!FULL_WIDTH_VIEWS.has(view) && <OverviewPanel overview={overview} />}
      {editingProfile && (
        <ProfileEditor profile={profile} onClose={() => setEditingProfile(false)} onSaved={setProfile} />
      )}
    </div>
  )
}
