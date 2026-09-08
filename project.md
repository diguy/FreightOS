# 当前项目阶段

## 1. 文档状态

本文档是新窗口进入项目时的当前状态入口。内容以当前代码、当前测试和当前真实运行环境为准。

交接文档、历史评测结果和历史测试数字只作为背景资料，不能自动视为当前事实。

当前日期：2026-09-08。

## 2. 当前阶段判断

项目处于：

> 阶段 1：核心 Agent 链路和业务能力已实现，正在进行真实 Dify 回归、工单端到端确认以及 MySQL/Redis 基础设施验收。

当前完成情况：

- Dify 意图识别 Chatflow v4 已有版本文件和发布记录。
- Dify 结构化 `result_json` 的 Python 解析链路已实现。
- 多轮会话、槽位合并、确认状态和用户隔离已实现。
- 订单物流查询已实现。
- 地址修改、投诉和人工转接工单已实现。
- 工单状态查询、状态流转、权限校验和路由测试已经存在。
- 本地知识库、RAGFlow 客户端和知识查询路由已经存在。
- Redis 会话存储、MySQL Repository、迁移和备份脚本已经存在。
- MCP 适配层、Server、鉴权和协议测试已经存在。

因此，“工单状态查询模块尚未开始”已经不是准确描述。当前应把它当作已实现模块，继续做真实 Dify 链路和基础设施条件下的验收。

## 3. 当前验证事实

### 3.1 全量测试

2026-09-08 在当前工作区执行：

```powershell
poetry run pytest tests -q
```

结果：

```text
157 passed, 23 failed
```

失败的主要原因是当前 `.env` 选择了 MySQL，但本机 MySQL 服务没有监听 `127.0.0.1:3308`。错误为连接被拒绝，并非已经确认的业务逻辑失败。

在临时使用 SQLite 和内存会话配置时，工单、订单和地址修改相关聚焦测试结果为：

```text
30 passed
```

### 3.2 Docker 和依赖

2026-09-08 检查 Docker 时，Docker Desktop Linux engine 不可连接。因此目前不能声称 MySQL、Redis 或 `/health/dependencies` 已通过真实环境验收。

### 3.3 意图回归

仓库内最近一份正式 50 条回归报告生成于 2026-09-07，记录的历史结果包括：

- 基础集意图准确率：97.14%。
- 对抗集意图准确率：93.33%。
- 对抗集工具门控准确率：100%。

这份报告不是 2026-09-08 重新运行的结果。下一次正式回归必须执行脚本并生成新的报告。

## 4. 当前难点

1. 本机 MySQL 和 Redis 服务没有启动，导致默认 `.env` 配置下的全量测试无法通过。
2. 需要区分测试环境回退到 SQLite/内存和正式环境使用 MySQL/Redis，避免测试结果被环境状态误导。
3. 需要重新运行真实 Dify v4 的 50 条意图回归，确认当前发布版本没有漂移。
4. 工单状态查询虽然有代码和测试，但仍需确认 Dify 能否正确识别 `ticket_status` 并在多轮场景中补齐 `ticket_no`。
5. RAGFlow、MCP 和真实外部服务的自动化测试主要依赖 fake 或本地替身，仍需要手工验收。
6. 当前工作区有大量既有 dirty worktree。后续提交必须只包含本次小切片的文件。

## 5. 下一步顺序

每一步都必须先报告将改动的文件和验收标准，然后只完成一个小切片。

### 5.1 依赖环境检查

目标：启动并确认 MySQL、Redis，初始化业务表，执行迁移和健康检查。

重点命令：

```powershell
docker ps
poetry run python scripts/init_mysql_schema.py
poetry run python scripts/migrate_sqlite_to_mysql.py
GET /health
GET /health/dependencies
```

验收重点：

- MySQL 可连接。
- Redis 可连接。
- `users`、`orders`、`tracking_events`、`tickets` 表存在。
- tracking event 重复数据已清理并受唯一约束保护。

### 5.2 重新运行 50 条 Dify 意图回归

目标：基于当前 v4 发布版本生成新的预测和报告。

```powershell
poetry run python scripts/run_formal_intent_regression.py
```

必须记录：

- intent accuracy。
- entity accuracy。
- missing_slots accuracy。
- tool_gate accuracy。
- 不安全工具调用。
- Dify 输出缺失或格式错误。

### 5.3 工单状态查询真实链路

目标：确认 `ticket_status` 从 Dify 到 Python Agent 再到工单 Service 的闭环。

验收重点：

- 没有 `ticket_no` 时只追问，不调用工具。
- 有效工单号可以查询状态。
- 用户不能查询其他用户的工单。
- 不存在工单时不泄露资源信息。
- 多轮补充工单号后能继续执行查询。

### 5.4 知识库和 RAGFlow 验收

```powershell
poetry run python evaluation/evaluate_knowledge.py
```

需要检查检索结果、来源信息、无答案降级和真实 RAGFlow 返回。

### 5.5 MCP 业务工具闭环

在前述链路稳定后，逐项验证订单查询、工单查询、知识检索、地址修改、投诉和人工转接的 MCP 调用门控。

### 5.6 交付收尾

完成全量测试、实链路测试、备份和恢复演练，并更新本文件中的当前事实和下一步。

## 6. Git 阶段命名规则

阶段名使用：

```text
主阶段.步骤（本切片名称）
```

当前切片：

```text
1.1（项目上下文基线）
```

后续示例：

```text
1.2（依赖环境验收）
1.3（Dify 意图回归）
1.4（工单状态端到端验收）
2.1（RAGFlow 知识问答验收）
```

Git 提交应只包含当前切片的文件。需要分支开发时，可以基于阶段名创建对应分支，例如从 `7.2` 派生 `7.2b`。
