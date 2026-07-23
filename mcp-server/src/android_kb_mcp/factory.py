from __future__ import annotations

from .config import Settings
from .embeddings import (
    LocalHashEmbeddingProvider,
    OpenAIEmbeddingProvider,
    SentenceTransformerEmbeddingProvider,
)
from .repository import MarkdownRepository
from .service import KnowledgeService
from .vector_store import ChromaVectorStore


def build_service(settings: Settings | None = None) -> KnowledgeService:
    settings = settings or Settings.from_env()
    repository = MarkdownRepository(settings.knowledge_base_path)
    if settings.embedding_provider == "local":
        embedder = LocalHashEmbeddingProvider(
            dimensions=settings.openai_embedding_dimensions or 384
        )
    elif settings.embedding_provider == "openai":
        embedder = OpenAIEmbeddingProvider(
            api_key=settings.openai_api_key,
            model=settings.openai_embedding_model,
            base_url=settings.openai_base_url,
            dimensions=settings.openai_embedding_dimensions,
        )
    else:
        embedder = SentenceTransformerEmbeddingProvider(
            model_name=settings.local_embedding_model,
            cache_folder=settings.local_embedding_cache_path,
            device=settings.local_embedding_device,
            batch_size=settings.local_embedding_batch_size,
            query_instruction=settings.local_embedding_query_instruction,
            trust_remote_code=settings.local_embedding_trust_remote_code,
        )
    vector_store = ChromaVectorStore(
        settings.chroma_persist_path, settings.chroma_collection
    )
    return KnowledgeService(repository, embedder, vector_store)
