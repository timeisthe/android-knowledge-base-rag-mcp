from __future__ import annotations

from pathlib import Path

import pytest

from android_kb_mcp.embeddings import LocalHashEmbeddingProvider
from android_kb_mcp.models import VectorRecord
from android_kb_mcp.vector_store import ChromaVectorStore


def test_chroma_round_trip_and_filters(tmp_path: Path) -> None:
    pytest.importorskip("chromadb")
    embedder = LocalHashEmbeddingProvider(dimensions=32)
    texts = ["Activity lifecycle Android", "Kotlin coroutine Flow"]
    embeddings = embedder.embed(texts)
    store = ChromaVectorStore(tmp_path / "chroma", "test_collection")
    store.upsert(
        [
            VectorRecord(
                file_path="android/activity.md",
                text=texts[0],
                metadata={
                    "title": "Activity",
                    "category": "android",
                    "difficulty": "medium",
                    "tags": ["高频", "framework"],
                },
                embedding=embeddings[0],
            ),
            VectorRecord(
                file_path="kotlin/flow.md",
                text=texts[1],
                metadata={
                    "title": "Flow",
                    "category": "kotlin",
                    "difficulty": "hard",
                    "tags": ["coroutines"],
                },
                embedding=embeddings[1],
            ),
        ]
    )

    hits = store.query(
        embedder.embed(["Activity Android"])[0],
        top_k=5,
        filters={"category": "android", "tags": ["高频"]},
    )
    assert [hit.file_path for hit in hits] == ["android/activity.md"]
    assert hits[0].metadata["tags"] == ["高频", "framework"]
    assert store.count() == 2

    store.delete(["kotlin/flow.md"])
    assert store.list_ids() == ["android/activity.md"]
