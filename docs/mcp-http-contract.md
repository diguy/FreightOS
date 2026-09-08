# MCP Streamable HTTP 契约

## 1. 当前传输

当前阶段使用官方 MCP Python SDK v2 的 Streamable HTTP，独立监听：

```text
http://127.0.0.1:8001/mcp
```

启动：

```powershell
$env:MCP_BEARER_TOKEN="在本地安全配置"
$env:MCP_USER_ID="demo-user-001"
poetry run python -m app.mcp.server --transport streamable-http
```

`MCP_BEARER_TOKEN` 不应写入仓库、日志或用户回复。

## 2. 身份校验

- HTTP 请求必须带 `Authorization: Bearer ...`。
- 第一阶段使用本地静态 Token 验证器，仅用于开发和内网验收。
- Token 的 `subject` 映射为内部 `user_id`。
- MCP 工具参数不接受 `user_id`。
- `session_id` 仍由调用方提供，服务端检查会话归属。

这不是正式 OAuth 授权服务器。生产环境应替换
`StaticTokenVerifier` 为 OAuth 2.1 JWT 或 introspection 验证器，并保留
同样的 `TokenVerifier` 接口。

## 3. 工具与业务边界

HTTP 工具仍经过：

```text
Bearer Token
    -> SessionManager
    -> EffectiveSessionContext
    -> McpToolAdapter
    -> BusinessToolExecutor
    -> Business Service
```

MCP Server 不直接访问 MySQL、Redis 或 RAGFlow。
