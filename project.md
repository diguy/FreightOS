# 当前项目阶段

> 新窗口必须先阅读 `AGENTS.md`、`WORKFLOW.md`、`prd.md`、`ARCD.md` 和本文件。

## 1. 当前结论

当前日期：2026-09-08。

项目已完成 MVP 核心能力和主要真实环境验收，当前处于最终交付文档与
残余风险收口阶段。不应再把工单状态查询、RAGFlow 或 MCP 描述为“尚未开始”。

已完成模块：

- Dify Chatflow v4 当前轮意图识别和结构化输出。
- Python Agent 输出解析、会话状态、槽位合并、确认和工具门控。
- 订单物流查询。
- 工单创建、工单状态查询、权限和状态流转。
- RAGFlow 经 FastAPI 中间层的真实知识检索。
- MySQL 业务数据、Redis 会话存储、迁移、健康检查和备份脚本。
- MCP 六项业务工具及 stdio 协议入口。

## 2. 当前真实运行环境

- 默认业务数据库：MySQL，`127.0.0.1:3308`。
- 默认会话存储：Redis，`127.0.0.1:6380`。
- FastAPI：`http://localhost:8000`。
- Dify API：`http://localhost/v1`。
- Dify Docker 调用后端：`http://host.docker.internal:8000/api/v1/agent/turn`。
- 测试用户：`demo-user-001`。
- RAGFlow 真实 Endpoint、API Key 和知识库 ID 只从本机 `.env` 读取，不写入文档或回复。

开始任何数据测试前，必须从当前 MySQL 查询并核对订单号、工单号、用户归属、
状态和关联关系。历史交接文档、旧报告和示例编号不能作为数据库事实。

## 3. 已验证事实

### 3.1 默认环境全量测试

执行：

```powershell
poetry run pytest tests -q
```

结果：

```text
183 passed in 11.32s
```

### 3.2 真实 Dify 链路

执行：

```powershell
poetry run pytest tests/test_chat_service.py tests/test_chat_route.py -q
poetry run python scripts/test_live_dify_chain.py --message "查一下 ORD1001 到哪里了" --session-id final-live-dify-fixed-20260908 --user-id demo-user-001
```

结果：

- 聚焦测试 `14 passed`。
- 真实 Dify -> FastAPI/ChatService -> MySQL 订单查询通过。
- `tracking_query`、订单号 `ORD1001`、工具调用和物流结果均正确。
- 修复提交：`f7bcb6b 1.5（Dify 实链路回包解析验收）`。

### 3.3 知识库和 RAGFlow

执行：

```powershell
poetry run python evaluation/evaluate_knowledge.py
```

结果：

```text
5/5 passed
```

五个案例均使用 `ragflow` 后端并校验了结果内容和来源。无关问题返回空结果；
FastAPI `/api/v1/knowledge/query` 在上游错误时返回明确降级上下文。

### 3.4 工单状态和 MCP

- 工单状态聚焦测试与真实链路已通过：缺少 `ticket_no` 不调用工具，本人可查，
  他人和不存在工单返回统一安全错误，多轮带查询语义补充工单号可继续查询。
- MCP 聚焦测试：`24 passed`。
- 真实 MCP stdio 已逐项验证订单查询、工单查询、知识检索、地址修改、投诉和
  人工转接六个工具。
- 地址修改、投诉和人工转接的临时验收工单已清理。

### 3.5 MySQL、Redis 和备份恢复

- `/health`：成功。
- `/health/dependencies`：MySQL 和 Redis 均为 `ok`。
- 当前 MySQL 数据：`orders=3`、`tickets=117`、`tracking_events=5`。
- 备份脚本已生成：
  `data/backups/logistics_20260908_175619.sql`。
- 该备份已导入临时数据库并核对恢复数据，临时数据库随后已清理。

### 3.6 正式 50 条意图回归

最新一次完整尝试已执行全部 50 条，但 `intent-017` 发生 Dify HTTP 超时。
因此该报告记录为 49 条成功、1 条缺失，不能称为全量通过。该行为已由
`1.3（回归失败继续执行与抽样复测规范）` 固化：少量错误修复后只运行同类
代表案例，不默认重复消耗全部模型调用额度。

## 4. 当前风险

1. Dify 外部模型偶发单条请求超时，正式 50 条报告仍不是完整无缺失结果。
2. 多轮补充工单号时，纯工单号输入曾被 Dify 判为 `unknown`；带“查询状态”
   等明确语义的补充输入已通过。
3. RAGFlow 是外部服务，真实查询存在网络超时风险；FastAPI 已提供降级回复。
4. MCP 当前主要完成本地 stdio 和真实业务闭环验收，生产级 OAuth、远程部署、
   观测和限流不在本 MVP 范围。
5. 工作区仍有用户或历史遗留 dirty changes。任何新提交只能包含当前切片文件。

## 5. 下一步

1. 新窗口先检查四件套、`AGENTS.md`、`WORKFLOW.md` 和当前 `git status`。
2. 不重复执行完整 50 条意图回归，除非需要确认共享逻辑没有回归或用户明确要求。
3. 如需处理 `intent-017` 超时，先检查 Dify/网络日志，再只运行该类代表案例。
4. 如需继续生产化，优先补充 MCP 远程 OAuth、外部服务重试/观测和备份定期演练。
5. 每个新改动仍按小切片、先说明文件和验收标准、先聚焦验证、只提交相关文件
   的规则执行。

## 6. Git 阶段版本

最近提交：

```text
f7bcb6b 1.5（Dify 实链路回包解析验收）
f5e7b04 1.4（测试数据对齐与失败复测规范）
bcee054 1.3（回归失败继续执行与抽样复测规范）
```

下一次提交继续使用：

```text
主阶段.步骤（本切片名称）
```
