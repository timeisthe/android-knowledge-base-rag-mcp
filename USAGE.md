# AI 编辑知识库使用指南

## 推荐工作流

所有编辑任务都遵循同一条最短链路：

1. `search_knowledge` 语义定位相关文档。
2. `get_document` 只读取准备修改的完整文档。
3. 调用一个明确的写工具。
4. 必要时再次搜索或读取，确认内容与索引同步。

不要先调用 `list_documents` 后把全库内容塞入上下文。该工具只返回元数据，适合分类盘点和批量规划。

## Tools

### `search_knowledge`

```json
{
  "query": "Activity 配置变更生命周期",
  "top_k": 5,
  "filters": {
    "category": "android-framework",
    "difficulty": "medium",
    "tags": ["高频"]
  }
}
```

返回文件路径、标题、完整元数据、余弦相似度和最多约 1200 字符的纯文本摘要。`tags` 要求文档同时包含所有指定标签；其他字段按精确值过滤。

### `get_document`

```json
{
  "file_path": "android-framework/four-components/activity.md"
}
```

路径始终相对于 `knowledge-base`。绝对路径、`..`、非 `.md` 文件以及 `.vitepress` 配置都会被拒绝。

### `create_document`

```json
{
  "file_path": "jetpack/saved-state-handle.md",
  "content": "# SavedStateHandle\n\n## 概述\n...",
  "metadata": {
    "title": "SavedStateHandle",
    "tags": ["jetpack", "viewmodel"],
    "difficulty": "medium",
    "category": "jetpack",
    "subcategory": "architecture-components"
  }
}
```

Server 会合并 content 中已有 frontmatter 与 metadata 参数，补全创建/更新时间，计算字数、代码示例和关联文档，然后写入 ChromaDB。

### `update_document`

传入无 frontmatter 的正文时保留原元数据；传入带 frontmatter 的完整 Markdown 时，用新 frontmatter 覆盖同名字段。`created_at` 保留，`updated_at` 自动更新。

### `delete_document`

同步删除 Markdown 与向量。工具不会删除分类目录。

### `append_to_section`

```json
{
  "file_path": "kotlin/coroutines/basics.md",
  "section": "参考资料",
  "content": "- [Kotlin Coroutines Guide](https://kotlinlang.org/docs/coroutines-guide.html)"
}
```

若标题存在，内容追加到该标题末尾、下一个同级或更高级标题之前；标题不存在时自动创建 `## 参考资料`。

### `list_documents`

支持 `category`、`subcategory`、`difficulty`、`title` 和 `tags`。只返回路径与元数据，不返回正文。

### `bulk_ingest`

```json
{ "directory": "android-framework" }
```

目录必须位于知识库根目录内。返回成功导入的 Markdown 数量。

### `reindex_all`

全量 upsert 当前文件，并删除没有对应 Markdown 的陈旧向量。手动改过文件、切换嵌入模型或怀疑索引不一致时调用。

## Resources

| URI | 内容 |
|---|---|
| `knowledge://documents/{category}` | 分类下全部文档元数据 |
| `knowledge://document/{file_path}` | 单篇完整文档；斜杠需由客户端 URI 编码 |
| `knowledge://metadata` | 文档总数、索引数、分类和难度统计 |
| `knowledge://tags` | 全部标签 |

## 场景示例

### 添加 ViewModel 生命周期文章

1. `search_knowledge("ViewModel lifecycle", 5)` 获取当前写作风格和相关页面。
2. 发现已有 `jetpack/viewmodel.md` 时，先判断是补充而不是重复创建。
3. 新主题才调用 `create_document`，已有主题调用 `update_document`。

### 添加 Activity 配置变更面试题

1. 搜索 `Activity lifecycle configuration change`。
2. `get_document("android-framework/four-components/activity.md")`。
3. 生成包含原文全部内容的新版本。
4. `update_document` 提交；Server 自动重建该文档向量。

### 添加官方协程链接

1. 搜索 `Kotlin coroutines`。
2. 定位 `kotlin/coroutines/basics.md`。
3. 用 `append_to_section` 写入“参考资料”，不需要 AI 手动计算插入行号。

## 知识点模板

```markdown
---
title: 知识点标题
tags: [分类, 高频]
difficulty: medium
category: category-name
subcategory: subcategory-name
---

# 知识点标题

## 概述
2～3 句话说明角色和问题。

## 核心知识点
- 关键事实

## 常见面试题
### 1. 问题？
**答案：**
...

**为什么：**
...

## 深入理解
- 源码关系、应用场景和边界情况

## 参考资料
### 官方文档
- [Android Developers](https://developer.android.com/)

## 相关知识点
- [[another-document]]
```

## 运维建议

- 修改嵌入模型或 `dimensions` 后必须执行 `reindex_all`，同一 Collection 不能混用不同维度。
- 定期比较 `knowledge://metadata` 中 `total_documents` 与 `indexed_documents`。
- `.chroma` 是派生数据，不进 Git；Markdown 才是事实来源。
- 备份时优先备份 Markdown。ChromaDB 可由 `reindex_all` 重建。
