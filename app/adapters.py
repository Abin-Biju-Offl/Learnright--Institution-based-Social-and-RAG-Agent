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

    VECTOR_STORE=simple    →  LlamaIndex's built-in store (default: files in storage/index)
    VECTOR_STORE=qdrant    →  Qdrant                     (OPEA-supported vector database)

Rule: no other file checks these settings. To add a new service, add one
branch here and nothing else changes.

The extra packages for tei, opea, openai_like and qdrant are optional:
    pip install -r requirements-opea.txt
"""

import importlib

from llama_index.core.base.embeddings.base import BaseEmbedding
from llama_index.core.llms import LLM
from llama_index.core.vector_stores.types import BasePydanticVectorStore

from app.config import settings

EMBEDDERS = ("ollama", "tei", "opea")
LLMS = ("ollama", "openai_like", "opea")
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
        raise ImportError(f"{module} isn't installed. Run: pip install -r requirements-opea.txt") from error


def unknown(setting: str, value: str, choices: tuple[str, ...]) -> ValueError:
    return ValueError(f"Unknown {setting}={value!r} in .env. Choose one of: {', '.join(choices)}")
