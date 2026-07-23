from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional
from urllib.parse import unquote

from mcp.server.fastmcp import FastMCP

from .factory import build_service
from .service import KnowledgeService


mcp = FastMCP(
    "Android Interview Knowledge Base",
    instructions=(
        "先用 search_knowledge 定位相关文档；需要完整内容时再调用 "
        "get_document。所有写操作都会同步更新 Markdown 与向量索引。"
    ),
)
_service: Optional[KnowledgeService] = None


def get_service() -> KnowledgeService:
    global _service
    if _service is None:
        _service = build_service()
    return _service


@mcp.tool()
def search_knowledge(
    query: str,
    top_k: int = 5,
    filters: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """语义搜索知识库，返回最相关文档的元数据、相似度和短摘要。"""
    return get_service().search_knowledge(query, top_k, filters)


@mcp.tool()
def get_document(file_path: str) -> Dict[str, Any]:
    """读取一篇 Markdown 文档的完整原文与派生元数据。"""
    return get_service().get_document(file_path)


@mcp.tool()
def create_document(
    file_path: str, content: str, metadata: Dict[str, Any]
) -> bool:
    """创建新文档并自动生成 frontmatter、写入文件和向量化。"""
    return get_service().create_document(file_path, content, metadata)


@mcp.tool()
def update_document(file_path: str, content: str) -> bool:
    """更新文档并重建该文档向量；失败时自动恢复旧版本。"""
    return get_service().update_document(file_path, content)


@mcp.tool()
def delete_document(file_path: str) -> bool:
    """删除 Markdown 文档及对应向量；失败时执行补偿回滚。"""
    return get_service().delete_document(file_path)


@mcp.tool()
def append_to_section(file_path: str, section: str, content: str) -> bool:
    """向指定 Markdown 标题区域末尾追加内容，并同步更新向量。"""
    return get_service().append_to_section(file_path, section, content)


@mcp.tool()
def list_documents(
    filters: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """列出文档元数据，支持 category、subcategory、difficulty 和 tags 过滤。"""
    return get_service().list_documents(filters)


@mcp.tool()
def bulk_ingest(directory: str = ".") -> int:
    """批量向量化知识库某个相对目录下的全部 Markdown 文档。"""
    return get_service().bulk_ingest(directory)


@mcp.tool()
def reindex_all() -> bool:
    """全量重建索引，并删除已不存在文件对应的陈旧向量。"""
    return get_service().reindex_all()


@mcp.resource("knowledge://documents/{category}", mime_type="application/json")
def documents_resource(category: str) -> str:
    """某一分类下的全部文档元数据。"""
    return json.dumps(
        get_service().documents_by_category(category),
        ensure_ascii=False,
        default=str,
    )


@mcp.resource("knowledge://document/{file_path}", mime_type="application/json")
def document_resource(file_path: str) -> str:
    """单篇文档资源；含斜杠路径应进行 URI 编码。"""
    return json.dumps(
        get_service().get_document(unquote(file_path)),
        ensure_ascii=False,
        default=str,
    )


@mcp.resource("knowledge://metadata", mime_type="application/json")
def metadata_resource() -> str:
    """知识库总文档数、已索引数与分类统计。"""
    return json.dumps(
        get_service().metadata_summary(), ensure_ascii=False, default=str
    )


@mcp.resource("knowledge://tags", mime_type="application/json")
def tags_resource() -> str:
    """知识库中的全部可用标签。"""
    return json.dumps(get_service().tags(), ensure_ascii=False)


def run_server() -> None:
    transport = os.getenv("MCP_TRANSPORT", "stdio").strip().lower()
    if transport == "stdio":
        mcp.run()
    elif transport in {"sse", "streamable-http"}:
        mcp.run(transport=transport)
    else:
        raise ValueError("MCP_TRANSPORT 仅支持 stdio、sse 或 streamable-http")
