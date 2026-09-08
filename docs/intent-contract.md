# 物流客服意图识别契约

## 1. 文档目的

本契约定义物流客服第一阶段的意图识别范围、结构化输出格式和工具调用门槛。

Dify 的意图识别节点、Python 解析器、自动化测试和后续会话状态模块都以本契约为准。

本阶段只负责识别当前用户消息，不负责长期记忆、复杂多轮编排或 MCP 接入。

## 2. 意图枚举

| 意图 | 标识 | 判断标准 |
| --- | --- | --- |
| 物流查询 | `tracking_query` | 查询具体订单的物流位置、运输进度、当前状态或最新物流节点 |
| 物流知识问答 | `knowledge_query` | 询问运费、时效、禁寄品、签收规则等通用物流知识 |
| 地址修改 | `address_change` | 要求修改、变更或纠正收货地址 |
| 投诉 | `complaint` | 投诉快递员、物流服务，或明确表达需要提交投诉 |
| 人工客服 | `human_transfer` | 明确要求人工客服、人工介入或转人工 |
| 工单查询 | `ticket_status` | 查询已有工单的处理状态或进度 |
| 未知 | `unknown` | 无法归入上述意图，信息不足，或不属于物流客服范围 |

## 3. 主意图规则

1. 每条用户消息只输出一个主意图。
2. 如果消息同时包含多个诉求，优先选择用户明确要求执行的动作。
3. 明确投诉优先于普通物流查询。
4. 明确转人工优先于普通咨询。
5. 只提到具体订单号，不代表用户一定要查询物流，需要结合语义判断。
6. 无法可靠判断时输出 `unknown`，不得猜测。

## 4. 实体字段

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `order_id` | `string \| null` | 订单号，例如 `ORD1001` |
| `ticket_no` | `string \| null` | 工单号，例如 `TABC123` |
| `new_address` | `string \| null` | 用户明确提供的新收货地址 |
| `complaint_content` | `string \| null` | 用户明确表达的投诉内容 |
| `contact` | `string \| null` | 用户明确提供的联系方式 |

实体提取规则：

1. 只提取当前消息中明确出现的实体。
2. 不从当前消息之外的内容猜测实体。
3. 订单号通常以 `ORD` 开头，后跟数字，输出时统一为大写。
4. 不能把手机号、金额、日期或运单号识别为订单号。
5. 本阶段不负责把历史消息中的实体合并到当前结果，历史实体合并属于下一阶段的会话状态模块。

## 5. 统一输出格式

意图识别节点必须输出严格 JSON，不得输出 Markdown 或额外解释：

```json
{
  "intent": "tracking_query",
  "confidence": 0.95,
  "entities": {
    "order_id": "ORD1001",
    "ticket_no": null,
    "new_address": null,
    "complaint_content": null,
    "contact": null
  },
  "missing_slots": [],
  "action": "query",
  "should_call_tool": true
}
```

字段规则：

- `intent` 必须是第 2 节中的一个标识。
- `confidence` 必须是 `0` 到 `1` 之间的数字。
- `entities` 必须包含第 4 节中的全部字段；没有提取到时使用 `null`。
- `missing_slots` 只描述当前意图所需但当前消息没有提供的字段。
- `action` 描述当前动作，例如 `query`、`collect_info`、`clarify` 或 `transfer`。
- `should_call_tool` 表示当前结果是否允许进入后续工具节点。

## 6. 工具调用门槛

以下任一条件满足时，`should_call_tool` 必须为 `false`：

1. `intent` 为 `unknown`。
2. `confidence < 0.70`。
3. 当前意图所需的必要字段不完整。
4. 输出 JSON 校验失败。
5. 用户尚未完成必要确认。

最低必要字段：

| 意图 | 必要字段 |
| --- | --- |
| `tracking_query` | `order_id` |
| `knowledge_query` | 当前问题文本 |
| `address_change` | `order_id`、`new_address`，提交前还需要确认 |
| `complaint` | `complaint_content`、`contact` |
| `human_transfer` | 用户的求助内容 |
| `ticket_status` | `ticket_no` |
| `unknown` | 无 |

## 7. 低置信度回复

当 `confidence < 0.70` 或 `intent = unknown` 时，不调用订单、工单或知识库工具，统一进入澄清回复：

```text
我暂时无法准确判断你的需求。请问你是想查询物流、咨询物流规则、修改地址、提交投诉，还是转人工？
```

## 8. 本阶段验收标准

### 结构化输出

- 所有正常样例都能生成合法 JSON。
- `intent` 始终属于固定枚举。
- `confidence` 始终在 `0` 到 `1` 之间。
- JSON 解析失败时自动降级为 `unknown`。

### 识别质量

- 基础意图准确率不低于 `90%`。
- 对抗样例意图准确率不低于 `85%`。
- 订单号提取准确率不低于 `95%`。
- 低置信度问题的工具误调用率为 `0`。

### 流程质量

- `unknown` 不进入 HTTP 请求节点。
- 低置信度结果不进入 HTTP 请求节点。
- 缺少必要字段时不进入业务工具节点。
- 每次 Prompt 或规则修改后都可以执行完整回归测试。
