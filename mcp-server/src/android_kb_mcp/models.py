from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass(frozen=True)
class KnowledgeDocument:
    file_path: str
    raw_content: str
    body: str
    metadata: Dict[str, Any]

    def to_dict(self, include_content: bool = True) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "file_path": self.file_path,
            "metadata": dict(self.metadata),
        }
        if include_content:
            result["content"] = self.raw_content
        return result


@dataclass(frozen=True)
class VectorRecord:
    file_path: str
    text: str
    metadata: Dict[str, Any]
    embedding: List[float]


@dataclass(frozen=True)
class SearchHit:
    file_path: str
    text: str
    metadata: Dict[str, Any]
    similarity: float
