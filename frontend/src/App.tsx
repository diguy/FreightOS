import { useMemo, useState } from 'react'
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

const demoAdapter: ChatModelAdapter = {
  async run({ messages }) {
    const lastMessage = messages.at(-1)
    const textPart = lastMessage?.content.find((part) => part.type === 'text')
    const query = textPart?.type === 'text' ? textPart.text : ''

    await new Promise((resolve) => window.setTimeout(resolve, 650))

    return {
      content: [
        {
          type: 'text',
          text: query.includes('ORD1001')
            ? '我可以帮您查询订单 ORD1001 的物流进度。当前页面先使用演示数据，下一步会接入真实查询接口。'
            : '收到。我会先理解您的物流需求，并在信息不足时向您询问必要内容。',
        },
      ],
    }
  },
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <CustomerWorkspace />
    </QueryClientProvider>
  )
}

function CustomerWorkspace() {
  const [conversationKey, setConversationKey] = useState(0)
  const runtime = useLocalRuntime(demoAdapter)
  const shortcuts = useMemo(
    () => ['查一下 ORD1001 到哪里了', '我要修改收货地址', '查询工单状态'],
    [],
  )

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
              onClick={() => setConversationKey((key) => key + 1)}
            >
              <Plus size={17} /> 新建会话
            </button>
            <nav className="side-nav" aria-label="主导航">
              <a className="nav-item active" href="#chat"><LifeBuoy size={17} />智能客服</a>
              <a className="nav-item" href="#orders"><Box size={17} />我的订单</a>
              <a className="nav-item" href="#tickets"><Clock3 size={17} />我的工单</a>
            </nav>
            <div className="sidebar-footer">
              <div className="secure-note"><ShieldCheck size={16} /><span>您的订单信息已受保护</span></div>
              <div className="user-card">
                <div className="user-avatar">张</div>
                <div><strong>张三</strong><span>138****0001</span></div>
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
                    <h2>您好，张三</h2>
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
