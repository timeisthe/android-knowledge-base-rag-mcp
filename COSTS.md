# 成本估算与优化建议

当前推荐通过硅基流动在线调用国产 `Qwen/Qwen3-Embedding-0.6B`，Markdown 原文和 ChromaDB 向量索引仍保存在本机。这样可以避免本地加载 PyTorch 和 0.6B 模型带来的内存压力，但向量化请求会按照硅基流动的实际价格或代金券规则计费。

`Qwen/Qwen3-Embedding-0.6B` 的公开价格可能调整，本文不硬编码单价。使用前请以[硅基流动价格页](https://www.siliconflow.cn/pricing)、控制台模型详情和“费用明细”为准。账户中的全平台代金券通常会自动抵扣符合范围的 API 消费。

## 哪些操作会产生费用

| 操作 | 是否调用在线 Embedding | 处理范围 |
|---|---:|---|
| `search_knowledge` / CLI `search` | 是 | 当前查询文本 |
| MCP `create_document` | 是 | 新文档 |
| MCP `update_document` | 是 | 被修改文档 |
| MCP `append_to_section` | 是 | 被修改文档 |
| MCP `delete_document` | 否 | 只删除本地向量 |
| `get_document` / `list_documents` | 否 | 只读取本地 Markdown |
| `reindex_all` / CLI `reindex` | 是 | 全部知识文档 |
| CLI `ingest` | 是 | 指定目录中的文档 |

通过 MCP 更新内容时不会扫描全库，只重新计算目标文档的向量。直接修改 Markdown 或执行 `git pull` 不会自动请求模型，需要手动运行 `reindex`。

## 费用估算

通用公式：

```text
费用（元） = 输入 Token 数 ÷ 1,000,000 × 每百万输入 Token 单价
```

如果模型单价记为 `P 元 / 百万 Token`：

| 场景 | 输入 Token 数 | 估算费用 |
|---|---:|---:|
| 初始化 100 篇，每篇 3,000 Token | 300,000 | `0.3 × P` 元 |
| 每月更新 40 篇，每篇 3,000 Token | 120,000 | `0.12 × P` 元 |
| 每月查询 5,000 次，每次 50 Token | 250,000 | `0.25 × P` 元 |
| 初始化 500 篇，每篇 3,000 Token | 1,500,000 | `1.5 × P` 元 |

Token 数并不等于字符数，中文、英文和代码的分词比例不同。准确费用应以服务端计量和硅基流动“费用明细”为准。

当前知识库包含 19 篇向量文档。最近一次使用在线 Qwen3 全量重建时分为 `8 + 8 + 3` 三次请求，约 2.5 秒完成；耗时会随网络、限流、文档长度和服务负载变化。

## 当前实现的成本与性能控制

- 远端请求默认每批 8 篇，降低单次请求体积和网络往返次数。
- OpenAI SDK 默认配置 30 秒超时和最多 4 次重试，用于处理限流及临时服务错误。
- 每篇文章一个向量单元，frontmatter 不直接参与嵌入；索引文本由标题、标签和正文组成。
- MCP 创建、更新和章节追加只重算目标文档，不扫描整个知识库。
- 查询只返回摘要，完整正文由 `get_document` 按需读取，不增加嵌入费用。
- 当前使用 1024 维向量，在检索质量、本地存储和 Chroma 搜索内存之间取得平衡。
- 更换模型、服务端实现或向量维度时使用新的 Chroma Collection，避免新旧向量混用。

批处理主要优化请求效率，不会减少输入 Token 总量。极少数情况下，如果服务端已经处理请求但客户端没有收到响应，自动重试可能产生重复调用，最终以服务商账单为准。

## 本地离线备选

将 `EMBEDDING_PROVIDER` 设置为 `sentence-transformers` 后，可以在本机运行相同的 `Qwen/Qwen3-Embedding-0.6B`：

```dotenv
EMBEDDING_PROVIDER=sentence-transformers
LOCAL_EMBEDDING_MODEL=Qwen/Qwen3-Embedding-0.6B
LOCAL_EMBEDDING_DEVICE=auto
LOCAL_EMBEDDING_BATCH_SIZE=8
CHROMA_COLLECTION=android_knowledge_local_qwen3_06b_1024_v1
```

本地模式没有按 Token 计费，但会增加首次下载时间、磁盘占用、启动时间和运行内存。内存不足时可以降低 `LOCAL_EMBEDDING_BATCH_SIZE` 或切换 CPU。

## 规模增长后的优化

### 1. 增加内容哈希

在元数据中保存正文哈希，让全量同步只请求新增或变化的文档。当前 MCP 的单文档更新已经是增量的，但 CLI `reindex` 仍会重新计算全库。

### 2. 超长文档按章节索引

当前严格按“一篇文章一个向量”实现。如果单篇文档超过模型输入限制或同时包含多个独立主题，应按二级标题拆分成子向量，并保留父文档路径。

### 3. 缓存重复查询

可以按照“模型 + 维度 + 规范化查询文本”缓存高频查询向量。查询规模较小时不建议过早引入缓存失效逻辑。

### 4. 控制 `top_k`

`top_k` 不影响向量化费用，因为查询文本只嵌入一次；它主要影响 Chroma 返回数量和发送给 AI 客户端的上下文长度。事实型问题通常使用 2～3，跨主题综述使用 5～8。

### 5. 监控服务端账单

定期核对硅基流动的代金券余额、费用明细、模型价格和限流策略。不要依赖文档中的历史单价做长期预算。
