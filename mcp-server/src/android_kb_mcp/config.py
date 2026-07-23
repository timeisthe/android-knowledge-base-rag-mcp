from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from .errors import ConfigurationError


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def _resolve_repo_path(value: str) -> Path:
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = REPOSITORY_ROOT / candidate
    return candidate.resolve()


def _optional_int(value: Optional[str], variable_name: str) -> Optional[int]:
    if value is None or not value.strip():
        return None
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ConfigurationError(f"{variable_name} 必须是整数") from exc
    if parsed <= 0:
        raise ConfigurationError(f"{variable_name} 必须大于 0")
    return parsed


def _positive_int(value: Optional[str], variable_name: str, default: int) -> int:
    parsed = _optional_int(value, variable_name)
    return parsed if parsed is not None else default


@dataclass(frozen=True)
class Settings:
    knowledge_base_path: Path
    chroma_persist_path: Path
    chroma_collection: str
    embedding_provider: str
    openai_api_key: Optional[str]
    openai_base_url: Optional[str]
    openai_embedding_model: str
    openai_embedding_dimensions: Optional[int]
    local_embedding_model: str
    local_embedding_cache_path: Path
    local_embedding_device: str
    local_embedding_batch_size: int
    local_embedding_query_instruction: str
    local_embedding_trust_remote_code: bool

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv(REPOSITORY_ROOT / ".env")
        settings = cls(
            knowledge_base_path=_resolve_repo_path(
                os.getenv("KNOWLEDGE_BASE_PATH", "knowledge-base")
            ),
            chroma_persist_path=_resolve_repo_path(
                os.getenv("CHROMA_PERSIST_PATH", ".chroma")
            ),
            chroma_collection=os.getenv("CHROMA_COLLECTION", "android_knowledge"),
            embedding_provider=os.getenv("EMBEDDING_PROVIDER", "openai").strip().lower(),
            openai_api_key=os.getenv("OPENAI_API_KEY") or None,
            openai_base_url=os.getenv("OPENAI_BASE_URL") or None,
            openai_embedding_model=os.getenv(
                "OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"
            ),
            openai_embedding_dimensions=_optional_int(
                os.getenv("OPENAI_EMBEDDING_DIMENSIONS"),
                "OPENAI_EMBEDDING_DIMENSIONS",
            ),
            local_embedding_model=os.getenv(
                "LOCAL_EMBEDDING_MODEL", "Qwen/Qwen3-Embedding-0.6B"
            ).strip(),
            local_embedding_cache_path=_resolve_repo_path(
                os.getenv(
                    "LOCAL_EMBEDDING_CACHE_PATH", ".model-cache/huggingface"
                )
            ),
            local_embedding_device=os.getenv(
                "LOCAL_EMBEDDING_DEVICE", "auto"
            ).strip().lower(),
            local_embedding_batch_size=_positive_int(
                os.getenv("LOCAL_EMBEDDING_BATCH_SIZE"),
                "LOCAL_EMBEDDING_BATCH_SIZE",
                8,
            ),
            local_embedding_query_instruction=os.getenv(
                "LOCAL_EMBEDDING_QUERY_INSTRUCTION",
                "Given an Android technical interview question, retrieve relevant "
                "knowledge-base documents that answer the question",
            ).strip(),
            local_embedding_trust_remote_code=os.getenv(
                "LOCAL_EMBEDDING_TRUST_REMOTE_CODE", "false"
            ).strip().lower()
            in {"1", "true", "yes", "on"},
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if not self.knowledge_base_path.is_dir():
            raise ConfigurationError(
                f"知识库目录不存在: {self.knowledge_base_path}"
            )
        if self.embedding_provider not in {
            "openai",
            "local",
            "sentence-transformers",
        }:
            raise ConfigurationError(
                "EMBEDDING_PROVIDER 仅支持 openai、sentence-transformers 或 local"
            )
        if self.embedding_provider == "openai" and not self.openai_api_key:
            raise ConfigurationError(
                "生产模式需要 OPENAI_API_KEY；离线演示可显式设置 "
                "EMBEDDING_PROVIDER=local"
            )
        if (
            self.embedding_provider == "sentence-transformers"
            and not self.local_embedding_model
        ):
            raise ConfigurationError("LOCAL_EMBEDDING_MODEL 不能为空")
        if self.local_embedding_device not in {"auto", "mps", "cuda", "cpu"}:
            raise ConfigurationError(
                "LOCAL_EMBEDDING_DEVICE 仅支持 auto、mps、cuda 或 cpu"
            )
