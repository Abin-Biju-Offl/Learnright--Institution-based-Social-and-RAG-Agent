"""
RAG step 1: build the search index. Run it once before starting the server:

    python -m app.ingest

What happens:
  1. Read every textbook PDF in data/ with Docling, page by page.
  2. Clean up the text (drop junk like "Reprint 2025-26").
  3. Split each page into chunks of about 512 tokens.
  4. Turn each chunk into a vector with the embedding model.
  5. Save chunks + vectors in the configured vector store (Qdrant by default).
  6. Write storage/index/index_info.json: parser, models, vector store, and corpus summary.

Run it again whenever you add, remove or change PDFs, or change EMBEDDER,
EMBED_MODEL, VECTOR_STORE, or the parser/index schema.
"""

import json
import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import NativePdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.pipeline.native_pdf_pipeline import NativePdfPipeline
from llama_index.core import Document, StorageContext, VectorStoreIndex, load_index_from_storage
from llama_index.core.node_parser import SentenceSplitter

from app.adapters import make_embed_model, make_vector_store
from app.catalog import chapter_info
from app.config import settings

log = logging.getLogger(__name__)
INDEX_SCHEMA_VERSION = 2
_converter: DocumentConverter | None = None


class IndexMismatch(RuntimeError):
    """The index was built with different settings than the ones in .env now."""


def clean_text(text: str) -> str:
    """Remove PDF noise that would only confuse the search and the LLM."""
    text = text.replace("\r\n", "\n")
    text = re.sub(r"^\s*Reprint \d{4}-\d{2}\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^n (?=\S)", "", text, flags=re.MULTILINE)  # bullet symbols come out as "n "
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)                # re-join words split across lines
    text = re.sub(r"[ \t]+", " ", text)                          # squeeze repeated spaces
    text = re.sub(r"\n\s*\n+", "\n\n", text)                     # squeeze blank lines
    return text.strip()


def make_page(text: str, metadata: dict) -> Document:
    """A page of text, labelled with where it came from (for citations)."""
    return Document(
        text=text,
        metadata=metadata,
        # Only the page text should become the vector, not labels like "page: 3"
        excluded_embed_metadata_keys=list(metadata),
        excluded_llm_metadata_keys=list(metadata),
    )


def read_pdf(pdf_path: Path, info: dict) -> list[Document]:
    """One Document per PDF page."""
    pages = []
    global _converter
    if _converter is None:
        # These textbooks already contain a text layer. The native pipeline
        # keeps Docling's page-aware document model without loading OCR,
        # layout, or table vision models for every page.
        options = NativePdfPipelineOptions()
        _converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_cls=NativePdfPipeline,
                    pipeline_options=options,
                )
            }
        )
    document = _converter.convert(pdf_path).document
    for page_number in document.pages:
        text = clean_text(document.export_to_markdown(page_no=page_number))
        if len(text) < 50:  # blank pages, full-page pictures, etc.
            continue
        file = pdf_path.relative_to(settings.data_dir).as_posix()
        pages.append(make_page(text, {**info, "page": page_number, "file": file}))
    return pages


def load_documents() -> list[Document]:
    documents = []
    for pdf_path in sorted(settings.data_dir.rglob("*.pdf")):
        info = chapter_info(pdf_path.name)
        if info is None:
            log.warning("Skipping %s: not a chapter of a book in app/catalog.py", pdf_path.name)
            continue
        pages = read_pdf(pdf_path, info)
        log.info("Read %s (Class %d %s, ch. %d): %d pages",
                 pdf_path.name, info["grade"], info["subject"], info["chapter"], len(pages))
        documents.extend(pages)
    return documents


def build_index() -> None:
    started = time.time()

    documents = load_documents()
    if not documents:
        raise SystemExit(f"No textbook PDFs found in {settings.data_dir}")

    splitter = SentenceSplitter(chunk_size=settings.chunk_size, chunk_overlap=settings.chunk_overlap)
    chunks = splitter.get_nodes_from_documents(documents)
    log.info("Split %d pages into %d chunks", len(documents), len(chunks))

    log.info("Embedding the chunks with %s via %s (the slow part)...", settings.embed_model, settings.embedder)
    vector_store = make_vector_store()  # None = LlamaIndex's built-in store
    if vector_store is not None:
        vector_store.clear()  # start from an empty collection, so removed PDFs disappear too
    storage = StorageContext.from_defaults(vector_store=vector_store)
    index = VectorStoreIndex(chunks, storage_context=storage, embed_model=make_embed_model(), show_progress=True)

    # Persist only after the complete embedding pass succeeds. The existing
    # index remains available if parsing or embedding fails.
    settings.index_dir.mkdir(parents=True, exist_ok=True)
    index.storage_context.persist(persist_dir=str(settings.index_dir))
    info = describe(chunks)
    settings.index_info_file.write_text(json.dumps(info, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("Saved the index (%s) in %.0f seconds", settings.vector_store, time.time() - started)


# ------------------------------------------------------------ index info ---

def describe(chunks) -> dict:
    """What an index holds and which settings built it. Saved as index_info.json."""
    chunks = list(chunks)
    found = {(c.metadata["grade"], c.metadata["subject"], c.metadata["book"]) for c in chunks}
    return {
        "embedder": settings.embedder,
        "embed_model": settings.embed_model,
        "vector_store": settings.vector_store,
        "parser": "docling",
        "index_schema": INDEX_SCHEMA_VERSION,
        "chunks": len(chunks),
        "subjects": [{"grade": g, "subject": s, "book": b} for g, s, b in sorted(found)],
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def read_index_info() -> dict:
    """index_info.json, after checking the index still matches the settings in .env.

    Without this check, changing EMBED_MODEL and forgetting to rebuild would quietly
    give bad search results: the question and the textbook would be turned into
    vectors by two different models, and those vectors can't be compared.
    """
    if not settings.index_info_file.exists():
        raise FileNotFoundError(f"No index in {settings.index_dir}. Build it with: python -m app.ingest")
    info = json.loads(settings.index_info_file.read_text(encoding="utf-8"))

    built_with = {
        "embedder": info.get("embedder"),
        "embed_model": info.get("embed_model"),
        "vector_store": info.get("vector_store"),
        "parser": info.get("parser"),
        "index_schema": info.get("index_schema"),
    }
    now = {
        "embedder": settings.embedder,
        "embed_model": settings.embed_model,
        "vector_store": settings.vector_store,
        "parser": "docling",
        "index_schema": INDEX_SCHEMA_VERSION,
    }
    if built_with != now:
        changed = ", ".join(f"{k.upper()} was {built_with[k]!r}, now {now[k]!r}"
                            for k in built_with if built_with[k] != now[k])
        raise IndexMismatch(f"The index was built with other settings ({changed}). "
                            f"Rebuild it with: python -m app.ingest")
    return info


def load_index(embed_model=None) -> VectorStoreIndex:
    read_index_info()  # fails clearly if there's no index, or it doesn't match .env
    embed_model = embed_model or make_embed_model()
    vector_store = make_vector_store()
    if vector_store is None:  # built-in store: everything is in the index files
        storage = StorageContext.from_defaults(persist_dir=str(settings.index_dir))
        return load_index_from_storage(storage, embed_model=embed_model)
    return VectorStoreIndex.from_vector_store(vector_store, embed_model=embed_model)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s", datefmt="%H:%M:%S")
    build_index()
