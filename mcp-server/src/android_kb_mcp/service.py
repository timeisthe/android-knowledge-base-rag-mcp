from __future__ import annotations

from collections import Counter
from functools import wraps
from threading import RLock
from typing import Any, Dict, List, Optional, Sequence

from .embeddings import EmbeddingProvider
from .errors import ConsistencyError
from .models import KnowledgeDocument, VectorRecord
from .repository import MarkdownRepository
from .text import excerpt, make_embedding_text
from .vector_store import VectorStore


def synchronized(method):
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        with self._lock:
            return method(self, *args, **kwargs)

    return wrapper


class KnowledgeService:
    """Coordinates Markdown storage, embeddings and vector-index consistency."""

    def __init__(
        self,
        repository: MarkdownRepository,
        embedder: EmbeddingProvider,
        vector_store: VectorStore,
    ):
        self.repository = repository
        self.embedder = embedder
        self.vector_store = vector_store
        self._lock = RLock()

    @synchronized
    def search_knowledge(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        if not query.strip():
            raise ValueError("query 不能为空")
        if top_k < 1 or top_k > 50:
            raise ValueError("top_k 必须在 1 到 50 之间")
        query_embedding = self.embedder.embed_query(query)
        hits = self.vector_store.query(query_embedding, top_k, filters)
        results: List[Dict[str, Any]] = []
        for hit in hits:
            try:
                current = self.repository.get(hit.file_path)
            except Exception:
                # A stale vector must not expose content that no longer exists.
                continue
            results.append(
                {
                    "file_path": current.file_path,
                    "title": current.metadata.get("title"),
                    "metadata": current.metadata,
                    "similarity": round(hit.similarity, 6),
                    "excerpt": excerpt(current.body),
                }
            )
        return results

    @synchronized
    def get_document(self, file_path: str) -> Dict[str, Any]:
        return self.repository.get(file_path).to_dict(include_content=True)

    @synchronized
    def create_document(
        self, file_path: str, content: str, metadata: Dict[str, Any]
    ) -> bool:
        document = self.repository.prepare_create(file_path, content, metadata)
        self.repository.write(document)
        try:
            self._index([document])
        except Exception as exc:
            try:
                self.repository.delete(document.file_path)
            except Exception as rollback_exc:
                raise ConsistencyError(
                    "创建后的向量化失败，且文件回滚失败；请运行 reindex_all 检查一致性"
                ) from rollback_exc
            raise ConsistencyError("向量化失败，已回滚新建文件") from exc
        return True

    @synchronized
    def update_document(self, file_path: str, content: str) -> bool:
        current = self.repository.get(file_path)
        updated = self.repository.prepare_update(file_path, content)
        self._replace_with_rollback(current, updated)
        return True

    @synchronized
    def delete_document(self, file_path: str) -> bool:
        current = self.repository.get(file_path)
        self.repository.delete(file_path)
        try:
            self.vector_store.delete([current.file_path])
        except Exception as exc:
            try:
                self.repository.write(current)
                self._index([current])
            except Exception as rollback_exc:
                raise ConsistencyError(
                    "删除向量失败，且文档回滚失败；请运行 reindex_all 修复一致性"
                ) from rollback_exc
            raise ConsistencyError("删除向量失败，已恢复原文档与索引") from exc
        return True

    @synchronized
    def append_to_section(self, file_path: str, section: str, content: str) -> bool:
        current = self.repository.get(file_path)
        updated = self.repository.prepare_append(file_path, section, content)
        self._replace_with_rollback(current, updated)
        return True

    @synchronized
    def list_documents(
        self, filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        return [
            document.to_dict(include_content=False)
            for document in self.repository.list_documents()
            if self.repository.matches_filters(document, filters)
        ]

    @synchronized
    def bulk_ingest(self, directory: str = ".") -> int:
        documents = self.repository.list_documents(directory)
        self._index(documents)
        return len(documents)

    @synchronized
    def reindex_all(self) -> bool:
        documents = self.repository.list_documents()
        # Compute all embeddings before touching Chroma. If OpenAI fails, the
        # existing index remains unchanged.
        records = self._build_records(documents)
        self.vector_store.upsert(records)
        current_ids = {document.file_path for document in documents}
        stale_ids = [
            file_path
            for file_path in self.vector_store.list_ids()
            if file_path not in current_ids
        ]
        if stale_ids:
            self.vector_store.delete(stale_ids)
        return True

    @synchronized
    def documents_by_category(self, category: str) -> List[Dict[str, Any]]:
        return self.list_documents({"category": category})

    @synchronized
    def metadata_summary(self) -> Dict[str, Any]:
        documents = self.repository.list_documents()
        categories = Counter(
            str(document.metadata.get("category", "uncategorized"))
            for document in documents
        )
        difficulties = Counter(
            str(document.metadata.get("difficulty", "unknown"))
            for document in documents
        )
        return {
            "total_documents": len(documents),
            "indexed_documents": self.vector_store.count(),
            "categories": dict(sorted(categories.items())),
            "difficulties": dict(sorted(difficulties.items())),
        }

    @synchronized
    def tags(self) -> List[str]:
        values = set()
        for document in self.repository.list_documents():
            values.update(document.metadata.get("tags", []))
        return sorted(str(value) for value in values)

    def _replace_with_rollback(
        self, current: KnowledgeDocument, updated: KnowledgeDocument
    ) -> None:
        self.repository.write(updated)
        try:
            self._index([updated])
        except Exception as exc:
            try:
                self.repository.write(current)
                self._index([current])
            except Exception as rollback_exc:
                raise ConsistencyError(
                    "更新向量失败，且旧版本回滚失败；请运行 reindex_all 修复一致性"
                ) from rollback_exc
            raise ConsistencyError("更新向量失败，已恢复原文档与原索引") from exc

    def _index(self, documents: Sequence[KnowledgeDocument]) -> None:
        self.vector_store.upsert(self._build_records(documents))

    def _build_records(
        self, documents: Sequence[KnowledgeDocument]
    ) -> List[VectorRecord]:
        if not documents:
            return []
        texts = [
            make_embedding_text(
                str(document.metadata.get("title", "")),
                document.metadata.get("tags", []),
                document.body,
            )
            for document in documents
        ]
        embeddings = self.embedder.embed(texts)
        if len(embeddings) != len(documents):
            raise RuntimeError("嵌入器返回数量与输入文档数量不一致")
        return [
            VectorRecord(
                file_path=document.file_path,
                text=text,
                metadata=dict(document.metadata),
                embedding=embedding,
            )
            for document, text, embedding in zip(documents, texts, embeddings)
        ]
