import sys
from types import SimpleNamespace

import numpy as np

from android_kb_mcp.embeddings import (
    OpenAIEmbeddingProvider,
    SentenceTransformerEmbeddingProvider,
)


def test_openai_provider_uses_current_embeddings_api_shape() -> None:
    captured = {}

    class FakeEmbeddings:
        def create(self, **kwargs):
            captured.update(kwargs)
            if len(kwargs["input"]) == 1:
                return SimpleNamespace(
                    data=[SimpleNamespace(index=0, embedding=[1.0, 0.0])]
                )
            return SimpleNamespace(
                data=[
                    SimpleNamespace(index=1, embedding=[0.0, 1.0]),
                    SimpleNamespace(index=0, embedding=[1.0, 0.0]),
                ]
            )

    provider = OpenAIEmbeddingProvider(
        api_key="test-key",
        model="text-embedding-3-small",
        dimensions=256,
    )
    provider.client = SimpleNamespace(embeddings=FakeEmbeddings())

    result = provider.embed(["Activity", "ViewModel"])

    assert captured == {
        "model": "text-embedding-3-small",
        "input": ["Activity", "ViewModel"],
        "encoding_format": "float",
        "dimensions": 256,
    }
    assert result == [[1.0, 0.0], [0.0, 1.0]]
    assert provider.embed_query("Activity") == [1.0, 0.0]


def test_openai_provider_batches_inputs_and_adds_query_instruction() -> None:
    captured = []

    class FakeEmbeddings:
        def create(self, **kwargs):
            captured.append(kwargs)
            return SimpleNamespace(
                data=[
                    SimpleNamespace(index=index, embedding=[float(index), 1.0])
                    for index, _ in enumerate(kwargs["input"])
                ]
            )

    provider = OpenAIEmbeddingProvider(
        api_key="test-key",
        model="Qwen/Qwen3-Embedding-0.6B",
        dimensions=1024,
        batch_size=2,
        query_instruction="Retrieve Android knowledge",
    )
    provider.client = SimpleNamespace(embeddings=FakeEmbeddings())

    result = provider.embed(["one", "two", "three", "four", "five"])
    query = provider.embed_query("Activity lifecycle")

    assert len(result) == 5
    assert query == [0.0, 1.0]
    assert [request["input"] for request in captured] == [
        ["one", "two"],
        ["three", "four"],
        ["five"],
        [
            "Instruct: Retrieve Android knowledge\n"
            "Query:Activity lifecycle"
        ],
    ]


def test_openai_provider_configures_timeout_and_retries(monkeypatch) -> None:
    captured = {}

    def fake_openai(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace()

    monkeypatch.setitem(
        sys.modules,
        "openai",
        SimpleNamespace(OpenAI=fake_openai),
    )

    OpenAIEmbeddingProvider(
        api_key="test-key",
        base_url="https://api.siliconflow.cn/v1",
        timeout_seconds=45,
        max_retries=6,
    )

    assert captured == {
        "api_key": "test-key",
        "base_url": "https://api.siliconflow.cn/v1",
        "timeout": 45,
        "max_retries": 6,
    }


def test_sentence_transformer_provider_adds_qwen_query_instruction(
    monkeypatch, tmp_path,
) -> None:
    created = {}
    encoded = []

    class FakeSentenceTransformer:
        def __init__(self, model_name, **kwargs):
            created["model_name"] = model_name
            created.update(kwargs)

        def encode(self, texts, **kwargs):
            encoded.append((list(texts), kwargs))
            return np.asarray([[1.0, 0.0] for _ in texts], dtype=float)

    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        SimpleNamespace(SentenceTransformer=FakeSentenceTransformer),
    )

    provider = SentenceTransformerEmbeddingProvider(
        model_name="Qwen/Qwen3-Embedding-0.6B",
        cache_folder=tmp_path / "qwen-test-cache",
        device="cpu",
        batch_size=4,
        query_instruction="Retrieve Android knowledge",
    )

    assert provider.embed(["Activity document"]) == [[1.0, 0.0]]
    assert provider.embed_query("Activity lifecycle") == [1.0, 0.0]
    assert created == {
        "model_name": "Qwen/Qwen3-Embedding-0.6B",
        "device": "cpu",
        "cache_folder": str(tmp_path / "qwen-test-cache"),
        "trust_remote_code": False,
    }
    assert encoded[0][0] == ["Activity document"]
    assert encoded[1][0] == [
        "Instruct: Retrieve Android knowledge\nQuery:Activity lifecycle"
    ]
    assert encoded[0][1] == {
        "batch_size": 4,
        "normalize_embeddings": True,
        "convert_to_numpy": True,
        "show_progress_bar": False,
    }
