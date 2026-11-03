"""
The adapter layer (app/adapters.py): the settings in .env pick which service
does each job. These tests only build the objects; nothing connects to a server.
"""

import json

import pytest

from app import adapters, ingest
from app.config import Settings, settings
from tests.conftest import build_rag

# ------------------------------------------------------- picking adapters ---


def test_default_setup_is_free_and_local(monkeypatch):
    defaults = {name: Settings.model_fields[name].default for name in ("embedder", "llm", "vector_store")}
    assert defaults == {"embedder": "ollama", "llm": "ollama", "vector_store": "simple"}
    for name, value in defaults.items():  # ignore whatever a local .env says
        monkeypatch.setattr(settings, name, value)
    assert type(adapters.make_embed_model()).__name__ == "OllamaEmbedding"
    assert type(adapters.make_llm()).__name__ == "Ollama"
    assert adapters.make_vector_store() is None  # None = LlamaIndex's built-in store


@pytest.mark.parametrize("setting, value, expected", [
    ("embedder", "tei", "TextEmbeddingsInference"),
    ("embedder", "opea", "OPEAEmbedding"),
    ("llm", "openai_like", "OpenAILike"),
    ("llm", "opea", "OPEA"),
])
def test_opea_mode_adapters(monkeypatch, setting, value, expected):
    pytest.importorskip("llama_index.llms.openai_like", reason="optional: pip install -r requirements.txt")
    monkeypatch.setattr(settings, setting, value)
    make = adapters.make_embed_model if setting == "embedder" else adapters.make_llm
    assert type(make()).__name__ == expected


def test_claude_adapter(monkeypatch):
    monkeypatch.setattr(settings, "llm", "claude")
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-ant-test-key")
    llm = adapters.make_llm()
    assert type(llm).__name__ == "Anthropic"
    assert llm.model == "claude-3-5-sonnet-latest"


def test_codex_openai_adapter(monkeypatch):
    monkeypatch.setattr(settings, "llm", "codex")
    monkeypatch.setattr(settings, "openai_api_key", "sk-test-key")
    llm = adapters.make_llm()
    assert type(llm).__name__ == "OpenAI"
    assert llm.model == "gpt-4o-mini"


def test_antigravity_gemini_adapter(monkeypatch):
    from unittest.mock import MagicMock
    import google.generativeai as genai
    mock_meta = MagicMock()
    mock_meta.supported_generation_methods = ["generateContent"]
    mock_meta.output_token_limit = 8192
    monkeypatch.setattr(genai, "get_model", lambda m: mock_meta)
    monkeypatch.setattr(genai, "GenerativeModel", lambda *args, **kwargs: MagicMock())

    try:
        from google import genai as modern_genai
        monkeypatch.setattr(modern_genai.models.Models, "get", lambda *args, **kwargs: mock_meta)
    except Exception:
        pass

    monkeypatch.setattr(settings, "llm", "antigravity")
    monkeypatch.setattr(settings, "gemini_api_key", "test-gemini-key")
    llm = adapters.make_llm()
    assert type(llm).__name__ in ("GoogleGenAI", "Gemini")
    assert "gemini" in llm.model


def test_groq_adapter(monkeypatch):
    monkeypatch.setattr(settings, "llm", "groq")
    monkeypatch.setattr(settings, "groq_api_key", "gsk_test_groq_key")
    llm = adapters.make_llm()
    assert type(llm).__name__ == "Groq"
    assert llm.model in ("llama-3.1-8b-instant", "llama-3.3-70b-versatile", "openai/gpt-oss-120b")


def test_grok_adapter_auto_detects_groq_or_xai(monkeypatch):
    monkeypatch.setattr(settings, "llm", "grok")
    monkeypatch.setattr(settings, "grok_api_key", "gsk_test_key_from_groq")
    llm = adapters.make_llm()
    assert type(llm).__name__ == "Groq"

    monkeypatch.setattr(settings, "grok_api_key", "xai-test-key")
    llm2 = adapters.make_llm()
    assert type(llm2).__name__ == "OpenAILike"
    assert llm2.model == "grok-2-latest"


def test_missing_api_key_raises_informative_error(monkeypatch):
    monkeypatch.setattr(settings, "llm", "groq")
    monkeypatch.setattr(settings, "groq_api_key", "")
    monkeypatch.setattr(settings, "grok_api_key", "")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("GROK_API_KEY", raising=False)
    with pytest.raises(ValueError, match="Missing Groq API key"):
        adapters.make_llm()


def test_every_llm_gets_the_same_answer_limits(monkeypatch):
    pytest.importorskip("llama_index.llms.openai_like")
    monkeypatch.setattr(settings, "llm", "openai_like")
    llm = adapters.make_llm()
    assert llm.temperature == settings.temperature
    assert llm.max_tokens == adapters.MAX_ANSWER_TOKENS


def test_qdrant_without_a_server_keeps_files_in_storage(monkeypatch, tmp_path):
    pytest.importorskip("llama_index.vector_stores.qdrant")
    monkeypatch.setattr(settings, "vector_store", "qdrant")
    monkeypatch.setattr(settings, "storage_dir", tmp_path)
    store = adapters.make_vector_store()
    assert type(store).__name__ == "QdrantVectorStore"
    assert (tmp_path / "qdrant").exists()
    store.client.close()


@pytest.mark.parametrize("setting, make", [
    ("embedder", adapters.make_embed_model),
    ("llm", adapters.make_llm),
    ("vector_store", adapters.make_vector_store),
])
def test_a_typo_in_env_names_the_valid_choices(monkeypatch, setting, make):
    monkeypatch.setattr(settings, setting, "olama")
    with pytest.raises(ValueError, match=f"Unknown {setting.upper()}='olama'.*Choose one of"):
        make()


# ----------------------------------------- swapping changes nothing else ---

def test_qdrant_finds_the_same_pages_as_the_built_in_store(fake_llm, monkeypatch):
    """Swapping the vector store must not change what students get."""
    qdrant = pytest.importorskip("qdrant_client")
    from llama_index.vector_stores.qdrant import QdrantVectorStore
    monkeypatch.setattr(settings, "min_score", 0.2)

    built_in = build_rag(fake_llm)
    in_qdrant = build_rag(fake_llm, QdrantVectorStore(
        collection_name="test", client=qdrant.QdrantClient(location=":memory:")))

    for question, grade, subject in [
        ("How do plants make food using sunlight?", 10, "Science"),
        ("How do plants make their own food using sunlight?", 5, "Science"),  # grade filter
        ("Why did Lencho write a letter to God?", 10, "English"),             # subject filter
    ]:
        expected = [(s.file, s.page) for s in built_in.search(question, grade, subject)]
        assert [(s.file, s.page) for s in in_qdrant.search(question, grade, subject)] == expected
        assert expected  # the question found something, so the comparison means something

    # Qdrant itself applies the class filter (rag.search() checks again, which would hide a miss)
    hits = in_qdrant.retrieve("How do plants make their own food using sunlight?", 5, "Science")
    assert {hit.node.metadata["grade"] for hit in hits} == {5}


# ------------------------------------------------- index matches .env ---

def write_info(tmp_path, monkeypatch, **changes):
    monkeypatch.setattr(settings, "storage_dir", tmp_path)
    monkeypatch.setattr(settings, "vector_store", "simple")
    settings.index_dir.mkdir(parents=True)
    info = {"embedder": "ollama", "embed_model": "qwen3-embedding:0.6b", "vector_store": "simple",
            "parser": "docling", "index_schema": ingest.INDEX_SCHEMA_VERSION,
            "chunks": 1, "subjects": [], **changes}
    settings.index_info_file.write_text(json.dumps(info), encoding="utf-8")


def test_index_info_is_read_when_it_matches(tmp_path, monkeypatch):
    write_info(tmp_path, monkeypatch)
    monkeypatch.setattr(settings, "embed_model", "qwen3-embedding:0.6b")
    assert ingest.read_index_info()["chunks"] == 1


def test_changed_embedding_model_needs_a_rebuild(tmp_path, monkeypatch):
    write_info(tmp_path, monkeypatch)
    monkeypatch.setattr(settings, "embed_model", "bge-m3")
    with pytest.raises(ingest.IndexMismatch, match="EMBED_MODEL was 'qwen3-embedding:0.6b', now 'bge-m3'"):
        ingest.read_index_info()


def test_changed_vector_store_needs_a_rebuild(tmp_path, monkeypatch):
    write_info(tmp_path, monkeypatch, embed_model=settings.embed_model)
    monkeypatch.setattr(settings, "vector_store", "qdrant")
    with pytest.raises(ingest.IndexMismatch, match="python -m app.ingest"):
        ingest.read_index_info()


def test_describe_lists_what_the_index_holds():
    from tests.conftest import documents
    info = ingest.describe(documents())
    assert info["chunks"] == 4
    assert [(s["grade"], s["subject"]) for s in info["subjects"]] == [(5, "Science"), (10, "English"), (10, "Science")]
    assert info["embed_model"] == settings.embed_model
