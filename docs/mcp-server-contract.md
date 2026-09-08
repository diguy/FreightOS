# MCP Server 契约

## 1. 当前实现

项目使用官方 MCP Python SDK v2 的 `MCPServer`。第一阶段只启用独立
`stdio` 传输，不挂载到 FastAPI，也不开放远程 HTTP。

启动入口：

```powershell
poetry run python -m app.mcp.server
```

## 2. 身份与会话

- `MCP_USER_ID` 是本地 stdio 进程的受控运行身份，不是 MCP 工具参数。
- 每次工具调用必须提供 `session_id`。
- Server 从配置的 `MCP_USER_ID` 和 Redis/内存会话恢复状态。
- 会话必须属于该用户，且必须通过 `EffectiveSessionContext.should_call_tool`。
- 工具参数必须与会话槽位一致。
- 地址修改还必须传入 `confirmed=true`。

stdio 只适合本地开发、Inspector 和受控自动化测试。远程调用不能复用
`MCP_USER_ID`，后续 Streamable HTTP 阶段必须接入 OAuth 2.1 Bearer Token，
再把 Token 身份映射为内部 `user_id`。

## 3. 工具集合

Server 暴露六个业务工具，工具实现全部转发至现有
`McpToolAdapter -> BusinessToolExecutor -> Service` 链路。Server 不直接
访问 MySQL、Redis 或 RAGFlow。

## 4. 安全边界

- 不接受调用方传入的 `user_id`。
- 不允许未知工具。
- 不允许跨用户会话。
- 不允许绕过会话门控。
- 不允许通过 MCP 参数替换已确认会话中的业务槽位。
- 本阶段不启用 `streamable-http` 参数；远程鉴权和部署另行验收。
