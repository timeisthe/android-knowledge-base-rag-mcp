from __future__ import annotations

from pathlib import Path

import pytest

from android_kb_mcp.embeddings import LocalHashEmbeddingProvider
from android_kb_mcp.errors import ConsistencyError, InvalidDocumentPath
from android_kb_mcp.models import VectorRecord
from android_kb_mcp.repository import MarkdownRepository
from android_kb_mcp.service import KnowledgeService
from android_kb_mcp.vector_store import InMemoryVectorStore


def make_service(root: Path, store=None) -> KnowledgeService:
    return KnowledgeService(
        MarkdownRepository(root),
        LocalHashEmbeddingProvider(dimensions=64),
        store or InMemoryVectorStore(),
    )


def activity_body(extra: str = "") -> str:
    return f"""# Activity 生命周期

## 概述

Activity 页面创建、显示和销毁。{extra}

## 参考资料

- [Android](https://developer.android.com/)

## 相关知识点

- [[viewmodel]]
"""


def create_activity(service: KnowledgeService) -> None:
    service.create_document(
        "android-framework/four-components/activity.md",
        activity_body(),
        {
            "title": "Activity 生命周期",
            "tags": ["android-framework", "高频"],
            "difficulty": "medium",
            "category": "android-framework",
            "subcategory": "four-components",
        },
    )


def test_crud_search_filters_and_metadata(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    create_activity(service)

    document = service.get_document("android-framework/four-components/activity.md")
    assert document["metadata"]["title"] == "Activity 生命周期"
    assert document["metadata"]["related_docs"] == ["viewmodel"]
    assert document["metadata"]["word_count"] > 0

    results = service.search_knowledge(
        "Activity 页面", filters={"category": "android-framework", "tags": ["高频"]}
    )
    assert results[0]["file_path"].endswith("activity.md")
    assert "content" not in results[0]
    assert "excerpt" in results[0]

    listed = service.list_documents({"difficulty": "medium"})
    assert len(listed) == 1
    assert "content" not in listed[0]

    service.update_document(
        "android-framework/four-components/activity.md",
        activity_body("包含配置变更处理。"),
    )
    updated = service.get_document("android-framework/four-components/activity.md")
    assert "配置变更" in updated["content"]
    assert updated["metadata"]["tags"] == ["android-framework", "高频"]
    assert "file_path:" not in updated["content"].split("---", 2)[1]

    service.append_to_section(
        "android-framework/four-components/activity.md",
        "参考资料",
        "- [Lifecycle](https://developer.android.com/lifecycle)",
    )
    appended = service.get_document("android-framework/four-components/activity.md")["content"]
    assert appended.index("Lifecycle") < appended.index("## 相关知识点")

    assert service.delete_document("android-framework/four-components/activity.md")
    assert service.list_documents() == []
    assert service.metadata_summary()["indexed_documents"] == 0


def test_path_traversal_is_rejected(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    with pytest.raises(InvalidDocumentPath):
        service.get_document("../secrets.md")
    with pytest.raises(InvalidDocumentPath):
        service.create_document("/tmp/outside.md", "# Bad", {})
    with pytest.raises(InvalidDocumentPath):
        service.create_document(".vitepress/config.md", "# Bad", {})


def test_reindex_removes_stale_vectors(tmp_path: Path) -> None:
    store = InMemoryVectorStore()
    service = make_service(tmp_path, store)
    create_activity(service)
    store.upsert(
        [
            VectorRecord(
                file_path="removed.md",
                text="removed",
                metadata={"category": "old"},
                embedding=[0.0] * 64,
            )
        ]
    )

    assert service.reindex_all()
    assert store.list_ids() == ["android-framework/four-components/activity.md"]


class FailOnceStore(InMemoryVectorStore):
    def __init__(self):
        super().__init__()
        self.fail_upsert_once = False
        self.fail_delete_once = False

    def upsert(self, records):
        if self.fail_upsert_once:
            self.fail_upsert_once = False
            raise RuntimeError("simulated upsert failure")
        return super().upsert(records)

    def delete(self, file_paths):
        if self.fail_delete_once:
            self.fail_delete_once = False
            raise RuntimeError("simulated delete failure")
        return super().delete(file_paths)


def test_update_and_delete_roll_back_on_vector_failure(tmp_path: Path) -> None:
    store = FailOnceStore()
    service = make_service(tmp_path, store)
    create_activity(service)
    original = service.get_document("android-framework/four-components/activity.md")["content"]

    store.fail_upsert_once = True
    with pytest.raises(ConsistencyError, match="已恢复原文档"):
        service.update_document(
            "android-framework/four-components/activity.md",
            activity_body("不应保留的更新"),
        )
    assert service.get_document("android-framework/four-components/activity.md")["content"] == original

    store.fail_delete_once = True
    with pytest.raises(ConsistencyError, match="已恢复原文档与索引"):
        service.delete_document("android-framework/four-components/activity.md")
    assert service.get_document("android-framework/four-components/activity.md")["content"] == original
    assert store.list_ids() == ["android-framework/four-components/activity.md"]


def test_create_rolls_back_when_embedding_fails(tmp_path: Path) -> None:
    store = FailOnceStore()
    service = make_service(tmp_path, store)
    store.fail_upsert_once = True
    with pytest.raises(ConsistencyError, match="已回滚新建文件"):
        create_activity(service)
    assert not (tmp_path / "android-framework/four-components/activity.md").exists()
