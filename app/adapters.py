"""
The adapter layer: the ONE place that decides which service does each job.

A RAG system needs three outside services:

* an embedding model: turns text into a vector (a list of numbers), so we can
  find textbook passages whose meaning is close to the question;
* an LLM (large language model): reads those passages and writes the answer;
* a vector store: keeps the vectors and finds the closest ones quickly.

Each job can be done by more than one service. LlamaIndex gives every service
the same shape (an "interface"), so the rest of the app never needs to know
which one it is talking to. This file reads the names in .env and builds the
matching object:

    EMBEDDER=ollama        →  OllamaEmbedding            (default: free, local)
    EMBEDDER=tei           →  TextEmbeddingsInference    (OPEA's embedding server)
    EMBEDDER=opea          →  OPEAEmbedding              (OPEA embedding microservice)

    LLM=ollama             →  Ollama                     (default: free, local)
    LLM=openai_like        →  OpenAILike                 (any OpenAI-style server: OPEA, OpenVINO, vLLM)
    LLM=opea               →  OPEA                       (OPEA LLM microservice)
    LLM=claude             →  Anthropic / Claude SDK     (Claude 3.5 Sonnet, 3.7 Sonnet, etc.)
    LLM=codex              →  OpenAI / Codex SDK         (GPT-4o, Codex, o3-mini, etc.)
    LLM=antigravity        →  Gemini / AntiGravity SDK   (Gemini 2.0 Flash, Gemini 1.5 Pro, etc.)
    LLM=groq               →  Groq                       (Llama 3.3 70B, Llama 3.1 8B, ultra-fast)
    LLM=grok               →  xAI Grok / Groq            (Grok-2 or Groq key)

    VECTOR_STORE=simple    →  LlamaIndex's built-in store (default: files in storage/index)
    VECTOR_STORE=qdrant    →  Qdrant                     (OPEA-supported vector database)

Rule: no other file checks these settings. To add a new service, add one
branch here and nothing else changes.
"""

import importlib
import os

from llama_index.core.base.embeddings.base import BaseEmbedding
from llama_index.core.llms import LLM
from llama_index.core.vector_stores.types import BasePydanticVectorStore

from app.config import settings

EMBEDDERS = ("ollama", "tei", "opea", "openai", "gemini")
LLMS = (
    "ollama",
    "openai_like",
    "opea",
    "claude",
    "anthropic",
    "claude_agent",
    "codex",
    "openai",
    "antigravity",
    "gemini",
    "groq",
    "grok",
)
VECTOR_STORES = ("simple", "qdrant")

# Qwen3-Embedding finds better matches when questions carry a short task description.
# Only questions get it: the textbook chunks are embedded as they are.
QUERY_INSTRUCTION = "Instruct: Given a student's question, retrieve textbook passages that answer it\nQuery:"

# Hard limit on answer length (in tokens), the same for every LLM service
MAX_ANSWER_TOKENS = 600


def make_embed_model() -> BaseEmbedding:
    # Ingestion and search must use the same embedding model, so both call this.
    if settings.embedder == "ollama":
        from llama_index.embeddings.ollama import OllamaEmbedding
        return OllamaEmbedding(
            model_name=settings.embed_model,
            base_url=settings.ollama_url,
            embed_batch_size=50,
            query_instruction=QUERY_INSTRUCTION,
        )
    if settings.embedder == "tei":
        TextEmbeddingsInference = optional("llama_index.embeddings.text_embeddings_inference",
                                           "TextEmbeddingsInference")
        return TextEmbeddingsInference(
            model_name=settings.embed_model,
            base_url=settings.embed_url,
            query_instruction=QUERY_INSTRUCTION,
            timeout=60,
        )
    if settings.embedder == "opea":
        OPEAEmbedding = optional("llama_index.embeddings.opea", "OPEAEmbedding")
        return OPEAEmbedding(model_name=settings.embed_model, api_base=settings.embed_url)
    if settings.embedder == "openai":
        OpenAIEmbedding = optional("llama_index.embeddings.openai", "OpenAIEmbedding")
        api_key = settings.openai_api_key or settings.codex_api_key or os.getenv("OPENAI_API_KEY")
        model = settings.embed_model if settings.embed_model != "qwen3-embedding:0.6b" else "text-embedding-3-small"
        return OpenAIEmbedding(model_name=model, api_key=api_key)
    if settings.embedder == "gemini":
        GeminiEmbedding = optional("llama_index.embeddings.gemini", "GeminiEmbedding")
        api_key = (settings.gemini_api_key or settings.antigravity_api_key or
                   os.getenv("GEMINI_API_KEY") or os.getenv("ANTIGRAVITY_API_KEY") or os.getenv("GOOGLE_API_KEY"))
        model = settings.embed_model if settings.embed_model != "qwen3-embedding:0.6b" else "models/text-embedding-004"
        return GeminiEmbedding(model_name=model, api_key=api_key)
    raise unknown("EMBEDDER", settings.embedder, EMBEDDERS)


def make_llm() -> LLM:
    if settings.llm == "ollama":
        from llama_index.llms.ollama import Ollama
        return Ollama(
            model=settings.llm_model,
            base_url=settings.ollama_url,
            temperature=settings.temperature,
            context_window=settings.context_window,
            request_timeout=settings.request_timeout,
            thinking=False,    # qwen3.5 can "think out loud" first; we only want the answer (much faster)
            keep_alive="30m",  # keep the model in memory between questions
            additional_kwargs={"num_predict": MAX_ANSWER_TOKENS},
        )
    if settings.llm in ("openai_like", "opea"):
        # Both speak the OpenAI chat API, so they take the same settings
        if settings.llm == "opea":
            ServerLLM = optional("llama_index.llms.opea", "OPEA")
        else:
            ServerLLM = optional("llama_index.llms.openai_like", "OpenAILike")
        return ServerLLM(
            model=settings.llm_model,
            api_base=settings.llm_url,
            api_key="not-needed",  # local servers ignore it, but the client insists on one
            is_chat_model=True,
            temperature=settings.temperature,
            context_window=settings.context_window,
            max_tokens=MAX_ANSWER_TOKENS,
            timeout=settings.request_timeout,
        )
    if settings.llm in ("claude", "anthropic", "claude_agent"):
        Anthropic = optional("llama_index.llms.anthropic", "Anthropic")
        api_key = (
            settings.anthropic_api_key
            or settings.claude_api_key
            or os.getenv("ANTHROPIC_API_KEY")
            or os.getenv("CLAUDE_API_KEY")
        )
        if not api_key:
            raise ValueError("Missing Anthropic/Claude API key. Set ANTHROPIC_API_KEY (or CLAUDE_API_KEY) in .env")
        model = settings.llm_model if "claude" in settings.llm_model else "claude-3-5-sonnet-latest"
        return Anthropic(
            model=model,
            api_key=api_key,
            temperature=settings.temperature,
            max_tokens=MAX_ANSWER_TOKENS,
            timeout=settings.request_timeout,
        )
    if settings.llm in ("codex", "openai"):
        OpenAI = optional("llama_index.llms.openai", "OpenAI")
        api_key = (
            settings.openai_api_key
            or settings.codex_api_key
            or os.getenv("OPENAI_API_KEY")
            or os.getenv("CODEX_API_KEY")
        )
        if not api_key:
            raise ValueError("Missing OpenAI/Codex API key. Set OPENAI_API_KEY (or CODEX_API_KEY) in .env")
        model = settings.llm_model if (settings.llm_model.startswith(("gpt-", "o1-", "o3-", "chatgpt-")) or settings.llm_model in ("gpt-4o", "gpt-4o-mini", "gpt-4-turbo")) else "gpt-4o-mini"
        return OpenAI(
            model=model,
            api_key=api_key,
            temperature=settings.temperature,
            max_tokens=MAX_ANSWER_TOKENS,
            timeout=settings.request_timeout,
        )
    if settings.llm in ("antigravity", "gemini"):
        api_key = (
            settings.antigravity_api_key
            or settings.gemini_api_key
            or settings.google_api_key
            or os.getenv("ANTIGRAVITY_API_KEY")
            or os.getenv("GEMINI_API_KEY")
            or os.getenv("GOOGLE_API_KEY")
        )
        if not api_key:
            raise ValueError("Missing AntiGravity/Gemini API key. Set GEMINI_API_KEY or ANTIGRAVITY_API_KEY in .env")
        model = settings.llm_model if "gemini" in settings.llm_model else "gemini-2.0-flash"
        try:
            from llama_index.llms.google_genai import GoogleGenAI
            clean_model = model.replace("models/", "")
            return GoogleGenAI(
                model=clean_model,
                api_key=api_key,
                temperature=settings.temperature,
                max_tokens=MAX_ANSWER_TOKENS,
            )
        except Exception:
            Gemini = optional("llama_index.llms.gemini", "Gemini")
            gemini_model = model if model.startswith("models/") else f"models/{model}"
            return Gemini(
                model=gemini_model,
                api_key=api_key,
                temperature=settings.temperature,
                max_tokens=MAX_ANSWER_TOKENS,
            )
    if settings.llm == "groq":
        Groq = optional("llama_index.llms.groq", "Groq")
        api_key = (
            settings.groq_api_key
            or settings.grok_api_key
            or os.getenv("GROQ_API_KEY")
            or os.getenv("GROK_API_KEY")
        )
        if not api_key:
            raise ValueError("Missing Groq API key. Set GROQ_API_KEY in .env")
        non_groq_defaults = ("qwen3.5:4b", "claude-3-5-sonnet-latest", "gpt-4o-mini", "gemini-2.0-flash", "grok-2-latest")
        if settings.llm_model and settings.llm_model not in non_groq_defaults:
            model = settings.llm_model
        else:
            model = "openai/gpt-oss-120b"
        return Groq(
            model=model,
            api_key=api_key,
            temperature=settings.temperature,
            max_tokens=MAX_ANSWER_TOKENS,
            timeout=settings.request_timeout,
        )
    if settings.llm == "grok":
        api_key = (
            settings.grok_api_key
            or settings.groq_api_key
            or os.getenv("GROK_API_KEY")
            or os.getenv("GROQ_API_KEY")
        )
        if not api_key:
            raise ValueError("Missing Grok/Groq API key. Set GROK_API_KEY or GROQ_API_KEY in .env")
        if api_key.startswith("gsk_"):  # Groq API key format
            Groq = optional("llama_index.llms.groq", "Groq")
            model = settings.llm_model if any(k in settings.llm_model for k in ("llama", "mixtral", "gemma", "deepseek")) else "llama-3.3-70b-versatile"
            return Groq(
                model=model,
                api_key=api_key,
                temperature=settings.temperature,
                max_tokens=MAX_ANSWER_TOKENS,
                timeout=settings.request_timeout,
            )
        else:
            OpenAILike = optional("llama_index.llms.openai_like", "OpenAILike")
            model = settings.llm_model if "grok" in settings.llm_model else "grok-2-latest"
            return OpenAILike(
                model=model,
                api_base=settings.grok_url,
                api_key=api_key,
                is_chat_model=True,
                temperature=settings.temperature,
                max_tokens=MAX_ANSWER_TOKENS,
                timeout=settings.request_timeout,
            )
    raise unknown("LLM", settings.llm, LLMS)


def make_vector_store() -> BasePydanticVectorStore | None:
    """The vector store, or None for LlamaIndex's built-in one (it needs no setup)."""
    if settings.vector_store == "simple":
        return None
    if settings.vector_store == "qdrant":
        QdrantVectorStore = optional("llama_index.vector_stores.qdrant", "QdrantVectorStore")
        QdrantClient = optional("qdrant_client", "QdrantClient")
        if settings.qdrant_url:  # a Qdrant server, e.g. the one in Docker
            client = QdrantClient(url=settings.qdrant_url)
        else:                    # no server: Qdrant keeps its files in a folder
            client = QdrantClient(path=str(settings.storage_dir / "qdrant"))
        return QdrantVectorStore(collection_name="ncert", client=client)
    raise unknown("VECTOR_STORE", settings.vector_store, VECTOR_STORES)


# ------------------------------------------------------------- helpers ---

def optional(module: str, name: str):
    """Import a class from a package that only some setups install."""
    try:
        return getattr(importlib.import_module(module), name)
    except ImportError as error:
        raise ImportError(f"{module} isn't installed. Run: pip install -r requirements.txt") from error


def unknown(setting: str, value: str, choices: tuple[str, ...]) -> ValueError:
    return ValueError(f"Unknown {setting}={value!r} in .env. Choose one of: {', '.join(choices)}")
