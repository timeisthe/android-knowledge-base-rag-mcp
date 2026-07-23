from __future__ import annotations

import hashlib
import math
import os
import re
import warnings
from pathlib import Path
from typing import List, Optional, Protocol, Sequence

from .errors import ConfigurationError


class EmbeddingProvider(Protocol):
    def embed(self, texts: Sequence[str]) -> List[List[float]]:
        """Return one embedding for each input, preserving input order."""

    def embed_query(self, text: str) -> List[float]:
        """Return an embedding optimized for a retrieval query."""


class OpenAIEmbeddingProvider:
    def __init__(
        self,
        api_key: Optional[str],
        model: str = "text-embedding-3-small",
        base_url: Optional[str] = None,
        dimensions: Optional[int] = None,
        batch_size: int = 8,
        timeout_seconds: int = 30,
        max_retries: int = 4,
        query_instruction: str = "",
    ):
        if not api_key:
            raise ConfigurationError(
                "缺少 EMBEDDING_API_KEY 或 OPENAI_API_KEY"
            )
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if max_retries < 0:
            raise ValueError("max_retries must not be negative")
        from openai import OpenAI

        client_options = {
            "api_key": api_key,
            "timeout": timeout_seconds,
            "max_retries": max_retries,
        }
        if base_url:
            client_options["base_url"] = base_url
        self.client = OpenAI(**client_options)
        self.model = model
        self.dimensions = dimensions
        self.batch_size = batch_size
        self.query_instruction = query_instruction.strip()

    def embed(self, texts: Sequence[str]) -> List[List[float]]:
        if not texts:
            return []
        embeddings: List[List[float]] = []
        for start in range(0, len(texts), self.batch_size):
            batch = [
                text if text.strip() else " "
                for text in texts[start : start + self.batch_size]
            ]
            embeddings.extend(self._embed_batch(batch))
        return embeddings

    def embed_query(self, text: str) -> List[float]:
        query = text if text.strip() else " "
        if self.query_instruction:
            query = f"Instruct: {self.query_instruction}\nQuery:{query}"
        return self.embed([query])[0]

    def _embed_batch(self, texts: List[str]) -> List[List[float]]:
        request = {
            "model": self.model,
            "input": texts,
            "encoding_format": "float",
        }
        if self.dimensions is not None:
            request["dimensions"] = self.dimensions
        response = self.client.embeddings.create(**request)
        embeddings = [
            list(item.embedding)
            for item in sorted(response.data, key=lambda item: item.index)
        ]
        if len(embeddings) != len(texts):
            raise RuntimeError("嵌入服务返回数量与请求数量不一致")
        return embeddings


class SentenceTransformerEmbeddingProvider:
    """Local semantic embeddings backed by Sentence Transformers.

    The default configuration targets Qwen3-Embedding-0.6B. Documents are
    encoded as-is, while queries can receive Qwen3's recommended retrieval
    instruction prefix.
    """

    def __init__(
        self,
        model_name: str = "Qwen/Qwen3-Embedding-0.6B",
        cache_folder: Optional[Path] = None,
        device: str = "auto",
        batch_size: int = 8,
        query_instruction: str = "",
        trust_remote_code: bool = False,
    ):
        if cache_folder is not None:
            cache_folder.mkdir(parents=True, exist_ok=True)
            os.environ["HF_HOME"] = str(cache_folder)
            os.environ["HF_HUB_CACHE"] = str(cache_folder / "hub")
            os.environ["HF_XET_CACHE"] = str(cache_folder / "xet")
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise ConfigurationError(
                "缺少 sentence-transformers。请在项目根目录执行: "
                "python -m pip install -e './mcp-server[local-models]'"
            ) from exc

        self.device = self._resolve_device(device)
        self.model_name = model_name
        self.batch_size = batch_size
        self.query_instruction = query_instruction.strip()
        self.model = SentenceTransformer(
            model_name,
            device=self.device,
            cache_folder=str(cache_folder) if cache_folder is not None else None,
            trust_remote_code=trust_remote_code,
        )

    def embed(self, texts: Sequence[str]) -> List[List[float]]:
        if not texts:
            return []
        return self._encode(list(texts))

    def embed_query(self, text: str) -> List[float]:
        query = text if text.strip() else " "
        if self.query_instruction:
            query = f"Instruct: {self.query_instruction}\nQuery:{query}"
        return self._encode([query])[0]

    def _encode(self, texts: List[str]) -> List[List[float]]:
        vectors = self.model.encode(
            texts,
            batch_size=self.batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return vectors.tolist()

    @staticmethod
    def _resolve_device(device: str) -> str:
        if device == "cpu":
            return device
        try:
            import torch
        except ImportError:
            return "cpu"
        mps_backend = getattr(torch.backends, "mps", None)
        mps_available = bool(mps_backend and mps_backend.is_available())
        cuda_available = torch.cuda.is_available()
        if device == "mps":
            if mps_available:
                return "mps"
            warnings.warn("MPS 当前不可用，已自动回退到 CPU", RuntimeWarning)
            return "cpu"
        if device == "cuda":
            if cuda_available:
                return "cuda"
            warnings.warn("CUDA 当前不可用，已自动回退到 CPU", RuntimeWarning)
            return "cpu"
        if mps_available:
            return "mps"
        if cuda_available:
            return "cuda"
        return "cpu"


class LocalHashEmbeddingProvider:
    """Deterministic, zero-cost embedding for tests and explicit offline demos.

    This provider is intentionally not the production default. It preserves lexical
    similarity well enough to exercise the complete RAG pipeline without API calls.
    """

    TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_]+|[\u3400-\u9fff]")

    def __init__(self, dimensions: int = 384):
        if dimensions <= 0:
            raise ValueError("dimensions must be positive")
        self.dimensions = dimensions

    def embed(self, texts: Sequence[str]) -> List[List[float]]:
        return [self._embed_one(text) for text in texts]

    def embed_query(self, text: str) -> List[float]:
        return self._embed_one(text)

    def _embed_one(self, text: str) -> List[float]:
        vector = [0.0] * self.dimensions
        tokens = self.TOKEN_PATTERN.findall(text.lower())
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] & 1 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]
