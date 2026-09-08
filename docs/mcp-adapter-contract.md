# MCP 适配层契约

## 1. 边界

`McpToolAdapter` 只负责把已经稳定的业务能力转换为 MCP 风格的工具描述
和受控调用入口。它不替代 Dify 的当前轮意图识别，也不直接读取或写入
MySQL、Redis。

调用链保持为：

```text
Dify result_json
    -> SessionManager
    -> EffectiveSessionContext
    -> McpToolAdapter
    -> BusinessToolExecutor
    -> Business Service
```

## 2. 工具约束

- `list_tools()` 返回工具名称、输入 JSON Schema、只读标记和破坏性标记。
- `invoke()` 必须校验工具存在、用户身份、当前意图、工具门控和参数槽位一致性。
- 地址修改要求调用参数 `confirmed=true`，但最终仍由会话确认状态和业务服务决定。
- MCP 适配层不接受绕过 `EffectiveSessionContext` 的直接数据库操作。
- 外部 MCP transport 或 SDK 属于后续集成，不属于本适配层。

## 3. 当前工具

| 工具 | 类型 | 对应意图 |
| --- | --- | --- |
| `get_order_tracking` | 只读 | `tracking_query` |
| `get_ticket_status` | 只读 | `ticket_status` |
| `search_knowledge` | 只读 | `knowledge_query` |
| `create_address_change_ticket` | 写入 | `address_change` |
| `create_complaint_ticket` | 写入 | `complaint` |
| `create_human_transfer_ticket` | 写入 | `human_transfer` |
