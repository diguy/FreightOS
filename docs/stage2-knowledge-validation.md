# 第二阶段：知识库小样本验证

## 当前样本

当前只使用一份物流规则文档：

```text
app/data/knowledge/source/顺丰快递规则——进出口件禁止 限制寄递物品.md
```

`物流查询测试.yml` 是 Dify Chatflow 配置，不是知识库文档。

## 1. 生成 ETL 语料

在项目根目录执行：

```powershell
poetry run python scripts/build_knowledge_corpus.py `
  --input app/data/knowledge/source `
  --output app/data/knowledge/corpus.jsonl `
  --query-date 2026-09-04
```

预期结果：

```text
wrote 1 chunks
```

在导入前检查 `app/data/knowledge/corpus.jsonl`，确认只包含物流规则、
来源文件名和元数据，不包含订单、轨迹、手机号或地址。

## 2. 在 RAGFlow 页面验证

RAGFlow 启动后：

1. 创建知识库，例如 `电商物流 FAQ`。
2. 配置 Embedding 模型。
3. 配置 Reranker 模型。
4. 创建完成后上传原始 Markdown 文件，或使用清洗后的语料内容。
5. 等待文档状态变为可检索。
6. 在知识库检索/问答页面输入测试问题。

首批测试问题：

```text
顺丰进出口件哪些物品不能寄？
酒能通过顺丰进出口件寄送吗？
烟草制品是否属于限制寄递物品？
为什么顺丰可能拒绝某些包裹？
液体能寄吗？
```

验收重点：

- 能召回顺丰进出口件禁寄/限寄规则。
- 回答中保留“进出口件”的适用范围。
- 酒和烟草应命中原文明确内容。
- 对原文没有明确说明的电池、液体规则，不得自行补充结论。
- 结果能够展示来源文档。

以下问题不属于 FAQ 知识库：

```text
ORD1001 到哪里了？
```

它必须进入 Dify 的 `tracking` 分支，并调用 FastAPI 订单接口。

## 3. 在 Dify 中验证

当前 YAML 中已有 `knowledge-retrieval` 节点，但它使用的是 Dify
原生知识库配置。导入 YAML 后，需要确认该节点的数据集是否是当前
RAGFlow 数据集；旧的 `dataset_id` 不能直接假定仍然有效。

联调顺序：

1. 先在 RAGFlow 页面验证检索结果。
2. 再在 Dify 中配置 RAGFlow 外部知识库。
3. 将 FAQ 分支连接到该外部知识库。
4. 保留现有 `tracking`、`change_address`、`complaint` 和 `human` 分支。
5. 在 Dify 对话页面重复上述 FAQ 测试。
6. 验证 `ORD1001 到哪里了？` 没有进入 FAQ 分支。

## 4. RAGFlow 源码准备

当前环境无法直接访问 GitHub，执行 clone 时连接被代理拒绝。
可以在网络正常的机器执行：

```powershell
git clone https://github.com/infiniflow/ragflow.git
cd ragflow
git fetch --tags
git checkout <确认的版本或 commit>
```

然后将完整的 `ragflow` 文件夹压缩为 ZIP，放到项目可访问的位置，
或直接将文件夹复制到：

```text
E:\PythonProject5\backend-lab\vendor\ragflow
```

不要只复制 `api/ragflow_server.py`，RAGFlow 需要完整源码和依赖目录。
