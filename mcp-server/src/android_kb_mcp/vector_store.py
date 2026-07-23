from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Sequence

from .models import SearchHit, VectorRecord


class VectorStore(Protocol):
    def upsert(self, records: Sequence[VectorRecord]) -> None:
        ...

    def delete(self, file_paths: Sequence[str]) -> None:
        ...

    def query(
        self,
        embedding: Sequence[float],
        top_k: int,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[SearchHit]:
        ...

    def list_ids(self) -> List[str]:
        ...

    def count(self) -> int:
        ...


SCALAR_FILTER_FIELDS = {"category", "subcategory", "difficulty", "title"}


def _normalize_tags(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return [str(item).strip() for item in value if str(item).strip()]


def _tag_key(tag: str) -> str:
    digest = hashlib.sha1(tag.encode("utf-8")).hexdigest()[:20]
    return f"tag_{digest}"


def _metadata_matches(metadata: Dict[str, Any], filters: Optional[Dict[str, Any]]) -> bool:
    if not filters:
        return True
    for key, expected in filters.items():
        if key == "tags":
            expected_tags = set(_normalize_tags(expected))
            actual_tags = set(_normalize_tags(metadata.get("tags", [])))
            if not expected_tags.issubset(actual_tags):
                return False
        elif metadata.get(key) != expected:
            return False
    return True


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right):
        return -1.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


class InMemoryVectorStore:
    """Simple vector store used by unit tests and isolated service tests."""

    def __init__(self):
        self.records: Dict[str, VectorRecord] = {}

    def upsert(self, records: Sequence[VectorRecord]) -> None:
        for record in records:
            self.records[record.file_path] = record

    def delete(self, file_paths: Sequence[str]) -> None:
        for file_path in file_paths:
            self.records.pop(file_path, None)

    def query(
        self,
        embedding: Sequence[float],
        top_k: int,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[SearchHit]:
        hits = [
            SearchHit(
                file_path=record.file_path,
                text=record.text,
                metadata=dict(record.metadata),
                similarity=_cosine(embedding, record.embedding),
            )
            for record in self.records.values()
            if _metadata_matches(record.metadata, filters)
        ]
        return sorted(hits, key=lambda hit: hit.similarity, reverse=True)[:top_k]

    def list_ids(self) -> List[str]:
        return sorted(self.records)

    def count(self) -> int:
        return len(self.records)


class ChromaVectorStore:
    """Persistent cosine-similarity store backed by ChromaDB."""

    def __init__(self, persist_path: Path, collection_name: str):
        import chromadb
        from chromadb.config import Settings as ChromaSettings

        persist_path.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(
            path=str(persist_path),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def upsert(self, records: Sequence[VectorRecord]) -> None:
        if not records:
            return
        self.collection.upsert(
            ids=[record.file_path for record in records],
            embeddings=[record.embedding for record in records],
            documents=[record.text for record in records],
            metadatas=[self._encode_metadata(record.metadata) for record in records],
        )

    def delete(self, file_paths: Sequence[str]) -> None:
        if file_paths:
            self.collection.delete(ids=list(file_paths))

    def query(
        self,
        embedding: Sequence[float],
        top_k: int,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[SearchHit]:
        collection_count = self.count()
        if collection_count == 0:
            return []

        # Chroma metadata values are scalar. Tags and future complex filters are
        # checked after retrieval, while scalar filters are pushed into Chroma.
        where = self._where(filters)
        needs_post_filter = bool(
            filters
            and any(key not in SCALAR_FILTER_FIELDS | {"tags"} for key in filters)
        )
        requested = min(
            collection_count,
            max(top_k * 8, top_k) if needs_post_filter else top_k,
        )
        query_options: Dict[str, Any] = {
            "query_embeddings": [list(embedding)],
            "n_results": requested,
            "include": ["metadatas", "documents", "distances"],
        }
        if where:
            query_options["where"] = where
        result = self.collection.query(**query_options)

        ids = result.get("ids", [[]])[0]
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]
        hits: List[SearchHit] = []
        for file_path, text, metadata, distance in zip(
            ids, documents, metadatas, distances
        ):
            decoded = self._decode_metadata(metadata or {})
            if not _metadata_matches(decoded, filters):
                continue
            hits.append(
                SearchHit(
                    file_path=file_path,
                    text=text or "",
                    metadata=decoded,
                    similarity=max(-1.0, min(1.0, 1.0 - float(distance))),
                )
            )
            if len(hits) >= top_k:
                break
        return hits

    def list_ids(self) -> List[str]:
        result = self.collection.get(include=[])
        return sorted(result.get("ids", []))

    def count(self) -> int:
        return self.collection.count()

    @staticmethod
    def _encode_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
        encoded: Dict[str, Any] = {}
        for key, value in metadata.items():
            if value is None:
                continue
            if isinstance(value, (str, int, float, bool)):
                encoded[key] = value
            elif isinstance(value, (list, tuple, dict)):
                encoded[f"{key}__json"] = json.dumps(value, ensure_ascii=False)
                if key == "tags":
                    for tag in _normalize_tags(value):
                        encoded[_tag_key(tag)] = True
            else:
                encoded[key] = str(value)
        return encoded

    @staticmethod
    def _decode_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
        decoded: Dict[str, Any] = {}
        for key, value in metadata.items():
            if key.startswith("tag_"):
                continue
            if key.endswith("__json"):
                try:
                    decoded[key[: -len("__json")]] = json.loads(value)
                except (TypeError, json.JSONDecodeError):
                    decoded[key[: -len("__json")]] = value
            else:
                decoded[key] = value
        return decoded

    @staticmethod
    def _where(filters: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not filters:
            return None
        conditions = [
            {key: {"$eq": value}}
            for key, value in filters.items()
            if key in SCALAR_FILTER_FIELDS and isinstance(value, (str, int, float, bool))
        ]
        for tag in _normalize_tags(filters.get("tags")):
            conditions.append({_tag_key(tag): {"$eq": True}})
        if not conditions:
            return None
        if len(conditions) == 1:
            return conditions[0]
        return {"$and": conditions}
