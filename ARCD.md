# 电商物流智能客服架构说明

## 1. 总体架构

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

知识问答和 MCP 是受控扩展路径：

```text
EffectiveSessionContext
  -> KnowledgeRetriever -> 本地知识库或 RAGFlow

EffectiveSessionContext
  -> McpToolAdapter -> MCP Server/Transport
```

## 2. 责任边界

### 2.1 Dify

Dify 只负责当前轮消息的意图识别、实体抽取、缺失槽位判断、动作和 `should_call_tool` 输出。当前使用的结构化契约由 `docs/intent-contract.md` 定义。

Dify 不负责：

- 长期会话状态。
- 最终用户权限判断。
- 直接决定写操作是否可以落库。
- 直接替代业务服务。

当前 Dify 到 Python 的主要接口：

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
  -> HttpDifyClient
  -> parse_dify_output
  -> SessionManager.process_turn
  -> BusinessToolExecutor
  -> 业务 Service
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
