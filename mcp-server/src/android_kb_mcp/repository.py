from __future__ import annotations

import os
import re
import tempfile
from datetime import date, datetime
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Iterable, List, Optional

import frontmatter

from .errors import (
    DocumentAlreadyExists,
    DocumentNotFound,
    InvalidDocumentPath,
)
from .models import KnowledgeDocument
from .text import count_words, related_documents


class MarkdownRepository:
    """Owns safe filesystem access and Markdown/frontmatter normalization."""

    def __init__(self, root: Path):
        self.root = root.resolve()

    def resolve_file(self, file_path: str) -> Path:
        normalized = file_path.strip().replace("\\", "/")
        if normalized.startswith("knowledge-base/"):
            normalized = normalized[len("knowledge-base/") :]

        pure_path = PurePosixPath(normalized)
        if not normalized or pure_path.is_absolute() or ".." in pure_path.parts:
            raise InvalidDocumentPath(f"非法文档路径: {file_path}")
        if pure_path.suffix.lower() != ".md":
            raise InvalidDocumentPath("知识库文档必须使用 .md 扩展名")

        candidate = (self.root / Path(*pure_path.parts)).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise InvalidDocumentPath(f"路径超出知识库目录: {file_path}") from exc
        if ".vitepress" in candidate.relative_to(self.root).parts:
            raise InvalidDocumentPath("不允许通过 MCP 修改 .vitepress 配置")
        return candidate

    def relative_path(self, path: Path) -> str:
        return path.resolve().relative_to(self.root).as_posix()

    def exists(self, file_path: str) -> bool:
        return self.resolve_file(file_path).is_file()

    def get(self, file_path: str) -> KnowledgeDocument:
        path = self.resolve_file(file_path)
        if not path.is_file():
            raise DocumentNotFound(f"文档不存在: {file_path}")
        return self._parse(path, path.read_text(encoding="utf-8"))

    def list_documents(self, directory: Optional[str] = None) -> List[KnowledgeDocument]:
        scan_root = self._resolve_directory(directory)
        documents = []
        for path in sorted(scan_root.rglob("*.md")):
            relative_parts = path.relative_to(self.root).parts
            if ".vitepress" in relative_parts or path.name == "index.md":
                continue
            documents.append(self._parse(path, path.read_text(encoding="utf-8")))
        return documents

    def prepare_create(
        self,
        file_path: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> KnowledgeDocument:
        path = self.resolve_file(file_path)
        if path.exists():
            raise DocumentAlreadyExists(f"文档已存在: {file_path}")

        incoming = frontmatter.loads(content)
        merged = dict(incoming.metadata)
        merged.update(metadata or {})
        today = date.today().isoformat()
        merged.setdefault("created_at", today)
        merged["updated_at"] = today
        raw = self._serialize(incoming.content, self._base_metadata(path, merged, incoming.content))
        return self._parse(path, raw)

    def prepare_update(self, file_path: str, content: str) -> KnowledgeDocument:
        current = self.get(file_path)
        path = self.resolve_file(file_path)
        incoming = frontmatter.loads(content)

        # Content without frontmatter updates the body but preserves existing metadata.
        metadata = dict(current.metadata)
        metadata.pop("word_count", None)
        metadata.pop("has_code_examples", None)
        metadata.pop("related_docs", None)
        metadata.update(incoming.metadata)
        metadata.setdefault("created_at", current.metadata.get("created_at"))
        metadata["updated_at"] = date.today().isoformat()
        raw = self._serialize(incoming.content, self._base_metadata(path, metadata, incoming.content))
        return self._parse(path, raw)

    def prepare_append(
        self, file_path: str, section: str, content: str
    ) -> KnowledgeDocument:
        if not section.strip():
            raise ValueError("section 不能为空")
        if not content.strip():
            raise ValueError("content 不能为空")

        current = self.get(file_path)
        post = frontmatter.loads(current.raw_content)
        body = post.content.rstrip()
        heading_pattern = re.compile(
            rf"^(#{{1,6}})\s+{re.escape(section.strip())}\s*$", re.MULTILINE
        )
        heading = heading_pattern.search(body)

        if heading:
            level = len(heading.group(1))
            tail = body[heading.end() :]
            next_heading = re.search(rf"^#{{1,{level}}}\s+", tail, re.MULTILINE)
            insert_at = heading.end() + (next_heading.start() if next_heading else len(tail))
            before = body[:insert_at].rstrip()
            after = body[insert_at:].lstrip()
            body = f"{before}\n\n{content.strip()}"
            if after:
                body += f"\n\n{after}"
        else:
            body += f"\n\n## {section.strip()}\n\n{content.strip()}"

        metadata = dict(post.metadata)
        metadata["updated_at"] = date.today().isoformat()
        path = self.resolve_file(file_path)
        raw = self._serialize(body, self._base_metadata(path, metadata, body))
        return self._parse(path, raw)

    def write(self, document: KnowledgeDocument) -> None:
        path = self.resolve_file(document.file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        file_descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
        )
        try:
            with os.fdopen(file_descriptor, "w", encoding="utf-8") as handle:
                handle.write(document.raw_content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, path)
        finally:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)

    def delete(self, file_path: str) -> None:
        path = self.resolve_file(file_path)
        if not path.is_file():
            raise DocumentNotFound(f"文档不存在: {file_path}")
        path.unlink()

    def matches_filters(
        self, document: KnowledgeDocument, filters: Optional[Dict[str, Any]]
    ) -> bool:
        if not filters:
            return True
        metadata = document.metadata
        for key, expected in filters.items():
            if key == "tags":
                expected_tags = self._normalize_list(expected)
                actual_tags = set(self._normalize_list(metadata.get("tags", [])))
                if not set(expected_tags).issubset(actual_tags):
                    return False
            elif metadata.get(key) != expected:
                return False
        return True

    def _resolve_directory(self, directory: Optional[str]) -> Path:
        if directory is None or not directory.strip() or directory.strip() == ".":
            return self.root
        normalized = directory.strip().replace("\\", "/").strip("/")
        if normalized.startswith("knowledge-base/"):
            normalized = normalized[len("knowledge-base/") :]
        pure_path = PurePosixPath(normalized)
        if pure_path.is_absolute() or ".." in pure_path.parts:
            raise InvalidDocumentPath(f"非法目录路径: {directory}")
        candidate = (self.root / Path(*pure_path.parts)).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise InvalidDocumentPath(f"目录超出知识库范围: {directory}") from exc
        if not candidate.is_dir():
            raise DocumentNotFound(f"目录不存在: {directory}")
        return candidate

    def _parse(self, path: Path, raw: str) -> KnowledgeDocument:
        post = frontmatter.loads(raw)
        metadata = self._derived_metadata(path, dict(post.metadata), post.content)
        return KnowledgeDocument(
            file_path=self.relative_path(path),
            raw_content=raw if raw.endswith("\n") else raw + "\n",
            body=post.content.strip(),
            metadata=metadata,
        )

    def _base_metadata(
        self, path: Path, metadata: Dict[str, Any], body: str
    ) -> Dict[str, Any]:
        result = dict(metadata)
        for key in {"file_path", "word_count", "has_code_examples", "related_docs"}:
            result.pop(key, None)
        relative = path.relative_to(self.root)
        parts = relative.parts
        result.setdefault("title", self._title_from_body(body, path.stem))
        result["tags"] = self._normalize_list(result.get("tags", []))
        result.setdefault("difficulty", "medium")
        if parts:
            result.setdefault("category", parts[0])
        if len(parts) > 2:
            result.setdefault("subcategory", parts[1])
        return result

    def _derived_metadata(
        self, path: Path, metadata: Dict[str, Any], body: str
    ) -> Dict[str, Any]:
        result = self._base_metadata(path, metadata, body)
        result["file_path"] = self.relative_path(path)
        result["word_count"] = count_words(body)
        result["has_code_examples"] = "```" in body
        result["related_docs"] = related_documents(body)
        if not result.get("created_at"):
            result["created_at"] = date.fromtimestamp(path.stat().st_ctime).isoformat()
        if not result.get("updated_at"):
            result["updated_at"] = date.fromtimestamp(path.stat().st_mtime).isoformat()
        return {key: self._json_safe(value) for key, value in result.items()}

    @staticmethod
    def _normalize_list(value: Any) -> List[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(value, Iterable):
            return [str(item).strip() for item in value if str(item).strip()]
        return [str(value)]

    @staticmethod
    def _title_from_body(body: str, fallback: str) -> str:
        match = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
        return match.group(1).strip() if match else fallback.replace("-", " ").title()

    @staticmethod
    def _serialize(body: str, metadata: Dict[str, Any]) -> str:
        post = frontmatter.Post(body.strip(), **metadata)
        return frontmatter.dumps(post) + "\n"

    @classmethod
    def _json_safe(cls, value: Any) -> Any:
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        if isinstance(value, list):
            return [cls._json_safe(item) for item in value]
        if isinstance(value, tuple):
            return [cls._json_safe(item) for item in value]
        if isinstance(value, dict):
            return {str(key): cls._json_safe(item) for key, item in value.items()}
        return value
