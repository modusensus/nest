import { useEffect, useRef, useState } from 'react'
import { api, getBaseUrl } from '../api'

export default function ChatView({ conversationId, onDataChanged, onConversationsChanged, onNewConversation }) {
  const [conversation, setConversation] = useState(null)
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const bottomRef = useRef(null)

  useEffect(() => {
    setConversation(null)
    if (conversationId) api(`/conversations/${conversationId}`).then(setConversation)
  }, [conversationId])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [conversation])

  if (!conversationId) {
    return (
      <section className="wb-empty">
        <h1>和你的 Agent 说点什么</h1>
        <p>试试：「帮我建一个网站项目，加三个任务」「今天健身打卡」「我现在进展怎么样」</p>
        {onNewConversation && (
          <div className="wb-empty-actions">
            <button className="primary" onClick={onNewConversation}>＋ 新建对话</button>
          </div>
        )}
      </section>
    )
  }
  if (!conversation) return null

  function patchAssistant(updater) {
    setConversation(c => ({
      ...c,
      messages: c.messages.map((m, i) => (i === c.messages.length - 1 ? updater(m) : m)),
    }))
  }

  async function send() {
    const content = input.trim()
    if (!content || streaming) return
    setInput('')
    setStreaming(true)
    setConversation(c => ({
      ...c,
      messages: [
        ...c.messages,
        { id: `u-${Date.now()}`, role: 'user', content },
        { id: `a-${Date.now()}`, role: 'assistant', content: '', tools: [] },
      ],
    }))
    let mutated = false
    try {
      const response = await fetch(`${getBaseUrl()}/api/conversations/${conversationId}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content }),
      })
      if (!response.ok) throw new Error((await response.json()).detail || '请求失败')
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let pending = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        pending += decoder.decode(value, { stream: true })
        const events = pending.split('\n\n')
        pending = events.pop()
        for (const item of events) {
          const raw = item.replace(/^data: /, '')
          if (raw === '[DONE]') continue
          const data = JSON.parse(raw)
          if (data.error) throw new Error(data.error)
          if (data.content) {
            patchAssistant(m => ({ ...m, content: m.content + data.content }))
          }
          if (data.tool) {
            mutated = true
            patchAssistant(m => {
              const tools = [...(m.tools || [])]
              const index = tools.findIndex(t => t.id === data.tool.id)
              if (index >= 0) tools[index] = data.tool
              else tools.push(data.tool)
              return { ...m, tools }
            })
          }
        }
      }
      const fresh = await api(`/conversations/${conversationId}`)
      setConversation(fresh)
      onConversationsChanged()
    } catch (error) {
      patchAssistant(m => ({ ...m, content: `请求出错：${error.message}` }))
    } finally {
      setStreaming(false)
      if (mutated) onDataChanged()
    }
  }

  return (
    <section className="wb-chat">
      <header className="wb-view-header"><h2>{conversation.title}</h2></header>
      <div className="wb-messages">
        {conversation.messages.map(m => (
          <article key={m.id} className={`wb-msg ${m.role}`}>
            <div className="wb-msg-role">{m.role === 'user' ? '我' : 'AI'}</div>
            <div className="wb-msg-body">
              {m.tools?.length > 0 && (
                <div className="wb-toolcard">
                  <div className="wb-toolcard-title">Agent 执行</div>
                  {m.tools.map(t => (
                    <div key={t.id} className="wb-tool">
                      <span className={`wb-dot ${t.status}`} />
                      <span>{t.label}</span>
                      <span className="wb-tool-status">{t.status === 'running' ? '进行中…' : (t.result?.error ? `失败：${t.result.error}` : '完成')}</span>
                    </div>
                  ))}
                </div>
              )}
              <div className={`wb-bubble ${streaming && m.role === 'assistant' && m === conversation.messages[conversation.messages.length - 1] ? 'streaming' : ''}`}>{m.content || (streaming && m.role === 'assistant' ? '正在思考…' : '')}</div>
            </div>
          </article>
        ))}
        <div ref={bottomRef} />
      </div>
      <div className="wb-composer">
        <textarea
          autoFocus
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }}
          placeholder="输入消息，Enter 发送，Shift + Enter 换行"
        />
        <button className="primary" disabled={streaming} onClick={send}>{streaming ? '生成中…' : '发送'}</button>
      </div>
    </section>
  )
}
