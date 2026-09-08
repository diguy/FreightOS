# 电商物流智能客服架构说明

> 项目全局工作规范见 `WORKFLOW.md`。新窗口必须与本文件、`prd.md`、`project.md` 一起阅读。

## 0. 2026年9月8日产品化架构结论

当前架构已经能够支撑第一阶段消费者端，但还不是完整网站产品。现阶段继续保持以下边界：

```text
消费者电脑网页
  -> 用户认证服务
  -> 消费者聊天与业务 API
  -> ChatService
  -> Dify 理解阶段
  -> SessionManager 多轮状态
  -> 业务 Service / Repository
  -> MySQL、Redis、RAGFlow
  -> Dify 回答阶段
  -> 客户可见 final_answer
```

第一阶段必须新增或完善的架构能力：

- 正式手机号验证码登录和用户会话，替换当前仅用于测试的 `X-User-Id`。
- 客户可见的最终回答层。内部工具结果继续保持结构化，不能直接展示给用户。
- Dify 理解阶段输入需要包含当前消息、经过裁剪的历史摘要、最近对话、
  当前槽位和系统提示词；Python 仍负责最终状态合并、权限校验和工具门控。
- Dify 回答阶段输入需要包含当前消息、经过裁剪的历史摘要、最近对话、
  有效会话上下文、结构化工具结果和回答系统提示词，并只输出 `final_answer`。
- 最近会话持久化与用户身份绑定，Redis 保存短期会话状态，MySQL 保存必要的会话索引或摘要。
- 第一阶段只实现电脑网页和消费者 API，不提前引入物流公司后台和多租户管理。

第二阶段再扩展：

- 物流公司账号、角色、权限和公司数据隔离。
- 用户、订单、修改申请、投诉和人工工单管理台。
- PDF/Markdown 上传、文件校验、解析、切分、RAGFlow 入库、处理状态和版本管理。
- 多家公司各自的订单范围和知识库范围。

### 技术路线原则

- 前端优先选择成熟的 React/TypeScript 管理系统和聊天界面模块，但必须逐项检查许可证、维护状态、React 版本、UI 组件依赖和可拆分程度。
- 后端继续使用 FastAPI、Pydantic、MySQL、Redis、Dify 和 RAGFlow，优先扩展现有 Service、Repository 和 Route，不替换已验证的核心链路。
- GitHub 模块只能作为边界清晰的前端组件、认证辅助、文件处理或后台表格能力引入；不得直接复制带有数据库、权限或业务模型的整套应用。
- 每个候选模块必须经过许可证、依赖、运行方式、数据安全、版本兼容和测试成本评估后才能进入技术方案。

### 已确定的前端基础模块

第一阶段前端确定使用：

```text
React + TypeScript
  -> shadcn/ui
  -> assistant-ui
  -> TanStack Query
  -> FastAPI API
```

三项模块只负责界面、聊天交互和前端数据请求，不替代 Dify、SessionManager、业务 Service、权限校验或 RAGFlow。前端不得直接访问 MySQL、Redis、Dify API Key 或 RAGFlow API Key。

## 1. 当前总体架构

```text
用户
  -> Dify Chatflow
  -> FastAPI
  -> Python Agent 编排层
  -> SessionManager
  -> EffectiveSessionContext
  -> BusinessToolExecutor
  -> 业务 Service
  -> Repository
  -> SQLite 或 MySQL
```

第一阶段产品化目标是在上述已验证后端链路前增加消费者电脑网页和正式用户认证，
并将客户可见回答与内部结构化工具结果分离。SQLite 仅作为开发和回退测试路径，
正式运行默认使用 MySQL。

知识问答和 MCP 是受控扩展路径：

```text
EffectiveSessionContext
  -> KnowledgeRetriever -> 本地知识库或 RAGFlow

EffectiveSessionContext
  -> McpToolAdapter -> MCP Server/Transport
```

## 2. 责任边界

### 2.1 Dify

Dify 分为两个职责明确的阶段：

1. **理解阶段**：根据当前用户问题、经过裁剪的历史摘要、最近几轮对话、
   当前槽位和系统提示词，输出意图、实体、缺失槽位、动作和
   `should_call_tool`。当前使用的结构化契约由 `docs/intent-contract.md` 定义。
2. **回答阶段**：在 Python 完成会话合并、权限校验和工具调用后，根据当前问题、
   历史对话、有效会话上下文、工具结果和回答系统提示词，输出客户可见的
   `final_answer`。

Dify 不负责：

- 长期会话状态。
- 最终用户权限判断。
- 直接决定写操作是否可以落库。
- 直接替代业务服务。
- 把未经 Python 校验的工具结果直接展示给客户。

当前 Dify 到 Python 的主要接口（内部回调，非消费者登录接口）：

```text
POST /api/v1/agent/turn
Header: X-User-Id
Body: session_id, message, result_json
```

### 2.2 Python Agent

`app/agent/` 是系统的状态和编排核心：

- `dify_output_parser.py`：解析和校验 Dify 输出。
- `intent_schema.py`：定义当前轮 `IntentResult`。
- `session_schema.py`：定义跨轮会话状态和有效上下文。
- `session_manager.py`：合并槽位、处理确认、计算缺失字段和工具门控。
- `chat_service.py`：连接 Dify、会话管理器和业务工具执行器。
- `business_tool_executor.py`：将有效上下文分发到已有业务服务。
- `session_store.py`、`in_memory_session_store.py`、`redis_session_store.py`：抽象和实现会话存储。

`IntentResult` 只表示当前轮结果；跨轮数据必须进入 `SessionState`。

Python 是两个大模型阶段之间的可信边界：

- 解析和校验理解阶段的 `intent_result`。
- 合并历史会话、当前问题和当前轮实体。
- 执行权限检查、缺槽位判断、确认门控和业务工具调用。
- 向回答阶段提供经过裁剪的 `answer_context`，其中包含工具结果但不包含密钥、
  数据库连接信息或不必要的内部字段。
- 校验 `final_answer` 为普通文本；回答阶段失败时返回确定性兜底话术。

### 2.3 业务服务和 Repository

业务服务是订单、物流轨迹和工单事实的业务入口：

- `app/services/order_service.py`
- `app/services/ticket_service.py`

Repository 只处理数据读写，不负责 HTTP 编排或 Dify 逻辑：

- `app/repositories/order_repository.py`
- `app/repositories/ticket_repository.py`
- `app/repositories/mysql_order_repository.py`
- `app/repositories/mysql_ticket_repository.py`

### 2.4 Routes

Routes 负责 HTTP 参数、请求头、响应模型和错误码适配，不承担业务编排。主要入口：

- `app/routes/chat.py`
- `app/routes/orders.py`
- `app/routes/tickets.py`
- `app/routes/knowledge.py`

### 2.5 数据存储

- SQLite：本地开发和回退测试。
- MySQL：正式订单、物流轨迹和工单业务数据。
- Redis：短期会话状态，以及后续可扩展的查询缓存。

通过 `APP_DATABASE` 选择业务数据库，通过 `SESSION_STORE` 选择会话存储。

### 2.6 知识库

`app/rag/` 负责物流规则文档的清洗、检索和 RAGFlow 接入。知识库只回答通用物流规则，不保存订单、工单、手机号或地址等业务事实。

### 2.7 MCP

`app/agent/mcp_adapter.py` 和 `app/mcp/` 提供受控工具描述、鉴权、会话归属检查和协议入口。MCP 必须接收已经经过 `EffectiveSessionContext` 门控的调用，不得绕过业务服务直接访问数据库。

## 3. 关键数据流

### 3.1 普通聊天链路

```text
POST /api/v1/chat
  -> Dify 理解阶段
  -> parse_dify_output
  -> SessionManager.process_turn
  -> BusinessToolExecutor
  -> 业务 Service
  -> answer_context
  -> Dify 回答阶段
  -> final_answer
  -> ChatResult
```

### 3.2 Dify 内部回调链路

```text
Dify HTTP 节点
  -> POST /api/v1/agent/turn
  -> parse result_json
  -> Python 会话状态和工具门控
  -> 返回 tool_result
```

当前本地约定：

- Dify API Endpoint：`http://localhost/v1`
- Python 后端：`http://localhost:8000`
- Dify Docker 调用后端：`http://host.docker.internal:8000/api/v1/agent/turn`
- 测试用户：`demo-user-001`

回答阶段的最小输入契约：

```text
current_message
history_summary
recent_turns
effective_session_context
tool_result
answer_system_prompt
```

回答阶段的输出契约：

```json
{
  "final_answer": "面向客户的自然语言回答"
}
```

`intent_result`、`tool_result`、`context` 和 `final_answer` 必须分字段传输。
前端只允许读取 `final_answer`，不得读取内部调试字段作为展示文本。

## 4. 修改原则

1. 每次只实现一个可验证的小切片。
2. 先读取相关代码和测试，再编辑。
3. 修改前说明目标、验收标准和文件清单。
4. Dify DSL 修改必须复制为新版本文件，保留历史版本。
5. 不修改 `vendor/`。
6. 不覆盖用户已有 dirty worktree。
7. 优先使用现有 Service、Repository、Schema 和 Adapter。
8. 业务行为变化必须补充或更新聚焦测试。
9. 完成后先运行聚焦测试，再视影响范围运行全量测试。
10. 提交后使用阶段步骤命名，例如 `1.1（项目上下文基线）`。

## 5. 当前已验证的边界

- Dify 的后端包装 `answer` 由 `ChatService` 解包后再交给 `IntentResult` 解析器。
- `IntentResult` 只表示当前轮；跨轮槽位和确认状态保存在 SessionManager 管理的会话中。
- 当前 Dify 主要完成理解阶段；回答阶段尚未形成独立、可验证的 `final_answer` 契约。
- 工具结果的 Python 确定性格式化只能作为过渡和故障兜底，不能替代回答阶段的大模型生成。
- 业务事实来自 MySQL Service/Repository，不来自 Dify 输出或 RAGFlow。
- RAGFlow 只提供知识检索结果和来源，不提供订单、工单或用户权限事实。
- RAGFlow 通过 FastAPI 中间层调用，不直接把 RAGFlow 知识库绑定到 Dify。
- MCP Server 不接受调用方传入的 `user_id`，身份来自受控 Token 或本地配置。
- MCP 当前暴露六个工具：订单查询、工单查询、知识检索、地址修改、投诉、人工转接。
- 外部模型、RAGFlow、MySQL、Redis 的真实验证不能被 fake 测试结果替代。

## 6. 当前运行配置

- 业务 MySQL：`127.0.0.1:3308`。
- 业务 Redis：`127.0.0.1:6380`。
- FastAPI：`http://localhost:8000`。
- Dify API：`http://localhost/v1`。
- Dify Docker 回调：`http://host.docker.internal:8000/api/v1/agent/turn`。
- RAGFlow Endpoint、API Key 和知识库 ID 只从本机 `.env` 读取，不能写入文档或回复。
