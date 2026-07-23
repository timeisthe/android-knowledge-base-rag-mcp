# Android Knowledge Base MCP Server

本目录是可独立安装的 Python 包，提供：

- Markdown 安全读写。
- ChromaDB 持久化索引。
- Qwen3 Sentence Transformers、OpenAI 和本地测试嵌入器。
- RAG 搜索、CRUD 和批量索引。
- MCP tools 与 resources。

完整的 macOS 从零安装、VitePress 启动和 MCP 客户端配置步骤见仓库根目录的 [README.md](../README.md)。

## 只开发 MCP Server 时的步骤

以下命令都在**仓库根目录**执行，而不是在 `mcp-server/` 内执行。

### 1. 进入仓库根目录

```zsh
cd "/Users/你的用户名/项目所在目录/vitepress-android-rag-mcp-server-ai"
pwd
```

### 2. 创建 Python 3.12 虚拟环境

```zsh
brew install python@3.12
"$(brew --prefix python@3.12)/bin/python3.12" -m venv .venv
source .venv/bin/activate
```

`.venv/` 用于隔离本项目依赖。激活成功后，提示符前通常会出现 `(.venv)`。

### 3. 安装 MCP Server 和测试依赖

```zsh
python -m pip install --upgrade pip
python -m pip install -e './mcp-server[dev,local-models]'
```

`-e` 表示可编辑安装；修改 `mcp-server/src/android_kb_mcp/` 后不需要重新安装。

### 4. 创建配置

```zsh
cp .env.example .env
open -e .env
```

Qwen3 本地语义检索推荐设置：

```dotenv
EMBEDDING_PROVIDER=sentence-transformers
LOCAL_EMBEDDING_MODEL=Qwen/Qwen3-Embedding-0.6B
LOCAL_EMBEDDING_CACHE_PATH=.model-cache/huggingface
LOCAL_EMBEDDING_DEVICE=auto
LOCAL_EMBEDDING_BATCH_SIZE=8
HF_HUB_OFFLINE=0
TRANSFORMERS_OFFLINE=0
KNOWLEDGE_BASE_PATH=knowledge-base
CHROMA_PERSIST_PATH=.chroma
CHROMA_COLLECTION=android_knowledge_qwen3_06b
MCP_TRANSPORT=stdio
```

### 5. 建立索引并搜索

```zsh
.venv/bin/android-kb-mcp reindex
.venv/bin/android-kb-mcp metadata
.venv/bin/android-kb-mcp search "Activity 生命周期" --top-k 3
```

- `reindex` 同步全部 Markdown 与 ChromaDB。
- `metadata` 查看文件数与索引数是否一致。
- `search` 验证嵌入和向量检索链路。

### 6. 运行测试

```zsh
.venv/bin/python -m pytest mcp-server/tests
```

### 7. 手动启动 MCP Server

```zsh
.venv/bin/android-kb-mcp serve
```

stdio Server 会等待 MCP 客户端输入，启动后没有持续日志是正常现象。按 `Control + C` 停止。

## CLI 命令

| 命令 | 用途 |
|---|---|
| `android-kb-mcp serve` | 启动 MCP Server |
| `android-kb-mcp ingest [directory]` | 导入知识库下的指定目录 |
| `android-kb-mcp reindex` | 全量同步文件与向量索引 |
| `android-kb-mcp metadata` | 输出文档、分类和索引统计 |
| `android-kb-mcp search QUERY` | 从 Terminal 执行语义搜索 |

未激活虚拟环境时，请在命令前使用 `.venv/bin/`，例如：

```zsh
.venv/bin/android-kb-mcp reindex
```
