"""
Shared test fixtures.

The tests never call Ollama: we swap in a tiny fake embedding model (word
counting) and a fake LLM that returns a fixed answer. That keeps the tests
fast and lets them run anywhere.
"""

import hashlib
import re
from collections.abc import Iterator

import pytest
from llama_index.core import Document, StorageContext, VectorStoreIndex
from llama_index.core.embeddings import BaseEmbedding
from llama_index.core.llms import CompletionResponse, CustomLLM, LLMMetadata
from llama_index.core.llms.callbacks import llm_completion_callback

from app.config import settings
from app.ingest import describe, make_page
from app.rag import RAG


class WordCountEmbedding(BaseEmbedding):
    """Texts that share words get similar vectors. Good enough for tests."""

    def _vector(self, text: str) -> list[float]:
        vector = [0.0] * 256
        for word in re.findall(r"[a-z]{4,}", text.lower()):  # skip little words like "the"
            vector[int(hashlib.md5(word.encode()).hexdigest(), 16) % 256] += 1.0
        return vector

    def _get_text_embedding(self, text: str) -> list[float]:
        return self._vector(text)

    def _get_query_embedding(self, query: str) -> list[float]:
        return self._vector(query)

    async def _aget_query_embedding(self, query: str) -> list[float]:
        return self._vector(query)


class FakeLLM(CustomLLM):
    """Always gives the same answer, and remembers the last prompt it saw."""

    answer: str = "Plants make their own food using sunlight [1]."
    last_prompt: str = ""

    @property
    def metadata(self) -> LLMMetadata:
        return LLMMetadata(is_chat_model=False)

    @llm_completion_callback()
    def complete(self, prompt: str, formatted: bool = False, **kwargs) -> CompletionResponse:
        self.last_prompt = prompt
        return CompletionResponse(text=self.answer)

    @llm_completion_callback()
    def stream_complete(self, prompt: str, formatted: bool = False, **kwargs) -> Iterator[CompletionResponse]:
        self.last_prompt = prompt
        text = ""
        for word in self.answer.split(" "):
            delta = word if not text else " " + word
            text += delta
            yield CompletionResponse(text=text, delta=delta)


def page(text: str, subject: str, chapter: int, page_number: int, grade: int = 10) -> Document:
    return make_page(text, {
        "grade": grade,
        "subject": subject,
        "book": f"{subject} book",
        "chapter": chapter,
        "chapter_title": f"Chapter title {chapter}",
        "page": page_number,
        "file": f"class-{grade}/{subject.lower()}/ch{chapter:02d}.pdf",
    })


@pytest.fixture
def fake_llm() -> FakeLLM:
    return FakeLLM()


def documents() -> list[Document]:
    """A tiny textbook collection: two classes, two subjects."""
    return [
        page("Photosynthesis is the process by which green plants make their own food "
             "using sunlight, carbon dioxide and water.", "Science", 6, 2),
        page("The human eye can focus on near and far objects by changing the focal length "
             "of the eye lens. This is called accommodation.", "Science", 10, 1),
        page("Lencho wrote a letter to God asking for a hundred pesos after hail destroyed "
             "his corn field.", "English", 1, 3),
        # The same topic in a younger class's book, told more simply
        page("Green leaves are the kitchens of plants. Plants make their own food "
             "using sunlight and water.", "Science", 4, 7, grade=5),
    ]


def build_rag(llm, vector_store=None) -> RAG:
    """A RAG over documents(). vector_store=None means LlamaIndex's built-in store."""
    storage = StorageContext.from_defaults(vector_store=vector_store)
    index = VectorStoreIndex.from_documents(documents(), storage_context=storage, embed_model=WordCountEmbedding())
    return RAG(index, llm, describe(documents()))


@pytest.fixture
def rag(fake_llm, monkeypatch) -> RAG:
    # Word counting gives lower scores than a real embedding model, so lower the bar
    monkeypatch.setattr(settings, "min_score", 0.2)
    return build_rag(fake_llm)
