# 会话状态与多轮记忆契约

## 1. 模块边界

- `IntentResult` 只表示 Dify 对当前用户消息的识别结果。
- `SessionState` 保存跨轮状态、已填槽位、待确认状态和最近对话记录。
- `EffectiveSessionContext` 是业务编排使用的本轮有效上下文。
- `SessionManager` 负责合并状态并重新计算缺槽位和工具调用门槛。
- `SessionStore` 是存储抽象；当前使用内存实现，后续可替换 Redis。

## 2. 状态规则

1. 同一意图的后续轮次继承已有槽位。
2. 切换意图时只复用 `order_id`、`ticket_no`，不复用地址和投诉内容。
3. 地址修改即使槽位完整，也必须经过明确确认后才允许调用工具。
4. 未知意图、低置信度、缺少必要槽位或取消操作均禁止调用工具。
5. 最近轮次只保留有限条结构化记录；`summary` 是结构化摘要，不保存整段无限历史。
6. `content` 等非实体槽位可通过编排层的 `extra_slots` 注入，不扩张当前
   `IntentEntities` 的实体契约。

## 3. 与现有模块的交互

```text
Dify result_json
    -> dify_output_parser.parse_dify_output
    -> IntentResult
    -> SessionManager.process_turn
    -> EffectiveSessionContext
    -> OrderService / TicketService / Knowledge route
```

业务服务只接收经过会话管理器门控后的有效实体，不负责读取或修改会话内存。

## 4. 当前实现与后续扩展

项目默认配置采用进程内内存存储，适合本地开发和单进程验证。生产配置已启用
`RedisSessionStore`，实现相同的 `SessionStore` 方法；设置
`SESSION_STORE=redis` 后可使用 `REDIS_URL` 和
`REDIS_SESSION_KEY_PREFIX` 配置 Redis 持久化。会话状态不写入订单、
工单 SQLite 表，避免业务事实和短期对话状态耦合。

Redis 模式依赖 `redis` Python 客户端和可访问的 Redis 服务；未配置或仍使用
默认 `SESSION_STORE=memory` 时，不会连接 Redis。
