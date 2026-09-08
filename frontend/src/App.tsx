import { useEffect, useMemo, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import {
  AssistantRuntimeProvider,
  ComposerPrimitive,
  MessagePrimitive,
  ThreadPrimitive,
  useLocalRuntime,
  type ChatModelAdapter,
} from '@assistant-ui/react'
import { ArrowUp, Box, Clock3, LifeBuoy, Plus, Send, ShieldCheck } from 'lucide-react'
import './App.css'

const queryClient = new QueryClient()
const USER_STORAGE_KEY = 'logistics-customer-user'
const SESSION_STORAGE_KEY = 'logistics-customer-sessions'

function App() {
  const [user, setUser] = useState<User | null>(() => readStoredUser())

  function handleLogin(nextUser: User) {
    localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(nextUser))
    setUser(nextUser)
  }

  return (
    <QueryClientProvider client={queryClient}>
      {user ? <CustomerWorkspace user={user} /> : <LoginView onLogin={handleLogin} />}
    </QueryClientProvider>
  )
}

type User = {
  user_id: string
  name: string
  phone_masked: string
}

type SavedMessage = {
  role: 'user' | 'assistant'
  content: string
}

type SavedSession = {
  sessionId: string
  difyConversationId: string | null
  title: string
  updatedAt: string
  messages: SavedMessage[]
}

function readStoredUser(): User | null {
  try {
    const value = localStorage.getItem(USER_STORAGE_KEY)
    return value ? JSON.parse(value) as User : null
  } catch {
    return null
  }
}

function readStoredSessions(): SavedSession[] {
  try {
    const value = localStorage.getItem(SESSION_STORAGE_KEY)
    const sessions = value ? JSON.parse(value) as SavedSession[] : []
    return Array.isArray(sessions) ? sessions : []
  } catch {
    return []
  }
}

function writeStoredSessions(sessions: SavedSession[]) {
  localStorage.setItem(
    SESSION_STORAGE_KEY,
    JSON.stringify(sessions.slice(0, 8)),
  )
}

function createSession(): SavedSession {
  return {
    sessionId: crypto.randomUUID(),
    difyConversationId: null,
    title: '新会话',
    updatedAt: new Date().toISOString(),
    messages: [],
  }
}

function LoginView({ onLogin }: { onLogin: (user: User) => void }) {
  const [phone, setPhone] = useState('13800000001')
  const [code, setCode] = useState('')
  const [hint, setHint] = useState('')
  const [error, setError] = useState('')

  async function requestCode() {
    setError('')
    const response = await fetch('/api/v1/auth/send-code', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ phone }),
    })
    const body = await response.json()
    if (!response.ok || !body.success) {
      setError(body.error?.message || '验证码发送失败')
      return
    }
    setHint(`验证码已发送，演示验证码：${body.data.dev_code}`)
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    const response = await fetch('/api/v1/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ phone, code }),
    })
    const body = await response.json()
    if (!response.ok || !body.success) {
      setError(body.error?.message || '登录失败')
      return
    }
    onLogin(body.data)
  }

  return (
    <main className="login-shell">
      <section className="login-panel">
        <div className="brand login-brand">
          <div className="brand-mark"><Box size={19} strokeWidth={2.4} /></div>
          <div><strong>快达物流</strong><span>智能客服</span></div>
        </div>
        <p className="eyebrow">消费者服务</p>
        <h1>登录智能客服</h1>
        <form className="login-form" onSubmit={submit}>
          <label>手机号<input value={phone} onChange={(event) => setPhone(event.target.value)} /></label>
          <div className="code-field">
            <label>验证码<input value={code} onChange={(event) => setCode(event.target.value)} /></label>
            <button type="button" onClick={requestCode}>获取验证码</button>
          </div>
          {hint && <p className="login-hint">{hint}</p>}
          {error && <p className="login-error">{error}</p>}
          <button className="login-submit" type="submit">登录</button>
        </form>
      </section>
    </main>
  )
}

function CustomerWorkspace({ user }: { user: User }) {
  const [conversationKey, setConversationKey] = useState(0)
  const [awaitingConfirmation, setAwaitingConfirmation] = useState(false)
  const [session, setSession] = useState<SavedSession>(
    () => readStoredSessions()[0] || createSession(),
  )
  const [recentSessions, setRecentSessions] = useState<SavedSession[]>(
    () => readStoredSessions(),
  )
  const sessionRef = useRef(session)
  const difyConversationId = useRef<string | null>(session.difyConversationId)
  const apiAdapter = useMemo<ChatModelAdapter>(
    () => ({
      async run({ messages }) {
        const lastMessage = messages.at(-1)
        const textPart = lastMessage?.content.find((part) => part.type === 'text')
        const query = textPart?.type === 'text' ? textPart.text : ''

        try {
          const response = await fetch('/api/v1/chat', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'X-User-Id': user.user_id,
            },
            body: JSON.stringify({
              session_id: sessionRef.current.sessionId,
              message: query,
              dify_conversation_id: difyConversationId.current,
            }),
          })
          const body = await response.json()
          if (!response.ok || !body.success) {
            throw new Error(body.error?.message || '客服暂时无法响应')
          }

          difyConversationId.current = body.data.conversation_id || null
          setAwaitingConfirmation(Boolean(body.data.context?.awaiting_confirmation))
          const currentSession = sessionRef.current
          const updatedSession: SavedSession = {
            ...currentSession,
            difyConversationId: difyConversationId.current,
            title: currentSession.messages.length
              ? currentSession.title
              : query.slice(0, 24) || '新会话',
            updatedAt: new Date().toISOString(),
            messages: [
              ...currentSession.messages,
              { role: 'user', content: query },
              {
                role: 'assistant',
                content: body.data.answer || '我暂时没有找到可用的处理结果。',
              },
            ],
          }
          sessionRef.current = updatedSession
          setSession(updatedSession)
          const nextSessions = [
            updatedSession,
            ...readStoredSessions().filter(
              (item) => item.sessionId !== updatedSession.sessionId,
            ),
          ]
          writeStoredSessions(nextSessions)
          setRecentSessions(nextSessions)
          return {
            content: [
              {
                type: 'text',
                text: body.data.answer || '我暂时没有找到可用的处理结果。',
              },
            ],
          }
        } catch {
          return {
            content: [
              {
                type: 'text',
                text: '抱歉，客服服务暂时不可用，请稍后再试。',
              },
            ],
          }
        }
      },
    }),
    [user.user_id],
  )
  const runtime = useLocalRuntime(apiAdapter, {
    initialMessages: session.messages,
  })
  useEffect(() => {
    runtime.thread.reset(session.messages)
  }, [runtime, session.sessionId])
  const shortcuts = useMemo(
    () => ['查一下 ORD1001 到哪里了', '我要修改收货地址', '查询工单状态'],
    [],
  )

  function startNewChat() {
    const nextSession = createSession()
    sessionRef.current = nextSession
    difyConversationId.current = null
    setSession(nextSession)
    setAwaitingConfirmation(false)
    setRecentSessions((sessions) => [nextSession, ...sessions])
    setConversationKey((key) => key + 1)
  }

  function openRecentSession(nextSession: SavedSession) {
    sessionRef.current = nextSession
    difyConversationId.current = nextSession.difyConversationId
    setSession(nextSession)
    setAwaitingConfirmation(false)
    setConversationKey((key) => key + 1)
  }

  return (
    <AssistantRuntimeProvider key={conversationKey} runtime={runtime}>
      <div className="app-shell">
        <header className="topbar">
          <div className="brand">
            <div className="brand-mark"><Box size={19} strokeWidth={2.4} /></div>
            <div>
              <strong>快达物流</strong>
              <span>智能客服</span>
            </div>
          </div>
          <div className="topbar-actions">
            <span className="status-dot"><span />服务正常</span>
            <button className="avatar-button" type="button" aria-label="打开个人中心">张</button>
          </div>
        </header>

        <main className="workspace">
          <aside className="sidebar">
            <button
              className="new-chat-button"
              type="button"
              onClick={startNewChat}
            >
              <Plus size={17} /> 新建会话
            </button>
            <nav className="side-nav" aria-label="主导航">
              <a className="nav-item active" href="#chat"><LifeBuoy size={17} />智能客服</a>
              <a className="nav-item" href="#orders"><Box size={17} />我的订单</a>
              <a className="nav-item" href="#tickets"><Clock3 size={17} />我的工单</a>
            </nav>
            {recentSessions.length > 0 && (
              <div className="recent-sessions">
                <p className="eyebrow">最近会话</p>
                {recentSessions.slice(0, 5).map((item) => (
                  <button
                    className={`recent-session ${item.sessionId === session.sessionId ? 'active' : ''}`}
                    key={item.sessionId}
                    type="button"
                    onClick={() => openRecentSession(item)}
                  >
                    {item.title}
                  </button>
                ))}
              </div>
            )}
            <div className="sidebar-footer">
              <div className="secure-note"><ShieldCheck size={16} /><span>您的订单信息已受保护</span></div>
              <div className="user-card">
                <div className="user-avatar">{user.name.slice(0, 1)}</div>
                <div><strong>{user.name}</strong><span>{user.phone_masked}</span></div>
              </div>
            </div>
          </aside>

          <section className="chat-panel" id="chat">
            <div className="chat-header">
              <div>
                <p className="eyebrow">在线服务</p>
                <h1>物流智能客服</h1>
              </div>
              <span className="session-label">当前会话</span>
            </div>
            <div className="chat-content">
              <ThreadPrimitive.Root className="thread-root">
                <ThreadPrimitive.Viewport className="thread-viewport">
                  <div className="welcome-block">
                    <div className="welcome-icon"><LifeBuoy size={22} /></div>
                    <h2>您好，{user.name}</h2>
                    <p>我可以帮您查询物流、办理地址修改和处理工单。</p>
                  </div>
                  <ThreadPrimitive.Messages
                    components={{
                      UserMessage,
                      AssistantMessage,
                    }}
                  />
                  <ThreadPrimitive.ViewportFooter />
                </ThreadPrimitive.Viewport>
              </ThreadPrimitive.Root>
            </div>
            <div className="suggestions">
              {shortcuts.map((shortcut) => (
                <button key={shortcut} type="button" onClick={() => runtime.thread.composer.setText(shortcut)}>
                  {shortcut}
                </button>
              ))}
            </div>
            {awaitingConfirmation && (
              <div className="confirmation-actions" aria-label="提交确认操作">
                <span>请确认是否提交本次申请</span>
                <button type="button" onClick={() => runtime.thread.composer.setText('确认提交')}>
                  确认提交
                </button>
                <button type="button" onClick={() => runtime.thread.composer.setText('取消')}>
                  取消
                </button>
              </div>
            )}
            <ComposerPrimitive.Root className="composer">
              <ComposerPrimitive.Input
                className="composer-input"
                placeholder="请输入您想咨询的物流问题"
                autoFocus
              />
              <ComposerPrimitive.Send className="send-button" aria-label="发送消息">
                <Send size={17} />
                <span>发送</span>
              </ComposerPrimitive.Send>
            </ComposerPrimitive.Root>
            <p className="composer-hint">请勿在对话中发送银行卡、密码等敏感信息</p>
          </section>

          <aside className="context-panel">
            <div className="context-heading">
              <div><p className="eyebrow">快捷入口</p><h2>需要帮助吗？</h2></div>
            </div>
            <div className="context-links">
              <button type="button"><Box size={18} /><span><strong>查询订单</strong><small>查看物流最新进度</small></span><ArrowUp size={15} /></button>
              <button type="button"><Clock3 size={18} /><span><strong>查看工单</strong><small>跟进申请处理状态</small></span><ArrowUp size={15} /></button>
            </div>
            <div className="context-divider" />
            <p className="eyebrow">服务时间</p>
            <p className="service-time">周一至周日 09:00 - 21:00</p>
            <p className="context-copy">智能客服全天在线，复杂问题可提交人工工单。</p>
          </aside>
        </main>
      </div>
    </AssistantRuntimeProvider>
  )
}

function UserMessage() {
  return (
    <MessagePrimitive.Root className="message-row user-message">
      <div className="message-bubble"><MessagePrimitive.Content /></div>
    </MessagePrimitive.Root>
  )
}

function AssistantMessage() {
  return (
    <MessagePrimitive.Root className="message-row assistant-message">
      <div className="assistant-avatar"><LifeBuoy size={16} /></div>
      <div className="message-bubble"><MessagePrimitive.Content /></div>
    </MessagePrimitive.Root>
  )
}

export default App
