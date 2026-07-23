from android_kb_mcp.config import Settings


def test_qwen_settings_from_environment(monkeypatch, tmp_path) -> None:
    knowledge_base = tmp_path / "knowledge-base"
    knowledge_base.mkdir()
    monkeypatch.setenv("KNOWLEDGE_BASE_PATH", str(knowledge_base))
    monkeypatch.setenv("CHROMA_PERSIST_PATH", str(tmp_path / "chroma"))
    monkeypatch.setenv("EMBEDDING_PROVIDER", "sentence-transformers")
    monkeypatch.setenv("OPENAI_API_KEY", "host-openai-key")
    monkeypatch.setenv("EMBEDDING_API_KEY", "project-embedding-key")
    monkeypatch.setenv("LOCAL_EMBEDDING_MODEL", "Qwen/Qwen3-Embedding-0.6B")
    monkeypatch.setenv("LOCAL_EMBEDDING_DEVICE", "mps")
    monkeypatch.setenv("LOCAL_EMBEDDING_BATCH_SIZE", "8")
    monkeypatch.setenv(
        "LOCAL_EMBEDDING_QUERY_INSTRUCTION", "Retrieve Android knowledge"
    )
    monkeypatch.setenv("OPENAI_EMBEDDING_BATCH_SIZE", "6")
    monkeypatch.setenv("OPENAI_TIMEOUT_SECONDS", "45")
    monkeypatch.setenv("OPENAI_MAX_RETRIES", "5")
    monkeypatch.setenv("OPENAI_EMBEDDING_QUERY_INSTRUCTION", "")
    monkeypatch.setenv("CHROMA_COLLECTION", "android_knowledge_qwen3_06b")

    settings = Settings.from_env()

    assert settings.embedding_provider == "sentence-transformers"
    assert settings.openai_api_key == "project-embedding-key"
    assert settings.local_embedding_model == "Qwen/Qwen3-Embedding-0.6B"
    assert settings.local_embedding_cache_path.name == "huggingface"
    assert settings.local_embedding_device == "mps"
    assert settings.local_embedding_batch_size == 8
    assert settings.openai_embedding_batch_size == 6
    assert settings.openai_timeout_seconds == 45
    assert settings.openai_max_retries == 5
    assert settings.openai_embedding_query_instruction == "Retrieve Android knowledge"
    assert settings.chroma_collection == "android_knowledge_qwen3_06b"
