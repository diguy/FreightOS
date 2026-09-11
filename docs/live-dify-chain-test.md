# 真实 Dify 链路测试

## 1. 配置

在项目根目录 `.env` 中配置：

```text
DIFY_BASE_URL=http://你的-dify地址
DIFY_API_KEY=你的应用API密钥
DIFY_TIMEOUT_SECONDS=30
```

应用应导入 `docs/artifacts/物流意图识别-v3-契约修正版.yml`，并确保它返回
`result_json` 结构化意图 JSON。

## 2. 执行

在项目根目录运行：

```powershell
poetry run python scripts/test_live_dify_chain.py
```

默认样例是只读查询：

```text
查一下 ORD1001 到哪里了
```

也可以指定独立会话和用户：

```powershell
poetry run python scripts/test_live_dify_chain.py `
  --session-id live-check-001 `
  --user-id demo-user-001
```

## 3. 验收点

- Dify 请求成功并返回 `conversation_id` 或有效响应。
- `result_json` 能被解析为 `tracking_query`。
- `order_id` 为 `ORD1001`。
- 会话门控允许调用工具。
- 订单服务返回物流数据。

脚本默认不测试改址、投诉或转人工，因为这些操作可能创建工单。真实写操作
应单独准备测试订单、测试用户和幂等请求号后再验证。
