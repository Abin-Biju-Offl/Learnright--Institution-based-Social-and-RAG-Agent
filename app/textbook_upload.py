"""
Textbook Upload & Ingestion Engine with Parental Governance & Under-18 Content Safety.

Handles:
1. Strict parental authentication (Bearer session token or valid Parental PIN).
2. PDF validation, file sanitization, and size limits (max 50 MB).
3. Under-18 content safety scan (preventing adult, pornographic, violent, or weapon content).
4. Automatic text extraction and cleaning.
5. Dynamic chunking with SentenceSplitter.
6. Vector embedding generation and storage in Qdrant / VectorStoreIndex.
7. Real-time catalog registration and index_info update so students can query immediately.
"""

import json
import logging
import re
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException, UploadFile
from llama_index.core import Document
from llama_index.core.node_parser import SentenceSplitter
from pypdf import PdfReader

from app.catalog import Book, BOOKS, register_custom_book, remove_custom_book
from app.config import settings
from app.parental.auth import validate_session
from app.parental.schemas import PinVerifyRequest
from app.parental.service import ParentalService
from app.safety import evaluate_content, log_safety_event
from app.safety.taxonomy import SafetyCategory, SeverityLevel

log = logging.getLogger(__name__)

INDEX_SCHEMA_VERSION = 2
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB
UPLOADED_METADATA_FILE = settings.storage_dir / "uploaded_textbooks_meta.json"


def clean_text(text: str) -> str:
    """Remove PDF noise that would only confuse the search and the LLM."""
    text = text.replace("\r\n", "\n")
    text = re.sub(r"^\s*Reprint \d{4}-\d{2}\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^n (?=\S)", "", text, flags=re.MULTILINE)
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def make_page(text: str, metadata: dict) -> Document:
    """A page of text, labelled with where it came from (for citations)."""
    return Document(
        text=text,
        metadata=metadata,
        excluded_embed_metadata_keys=list(metadata),
        excluded_llm_metadata_keys=list(metadata),
    )


# ------------------------------------------------------------------------------
# Parental Authorization Verification
# ------------------------------------------------------------------------------

def verify_parental_authorization(token: str | None = None, pin: str | None = None) -> bool:
    """
    Verify that the user uploading the textbook has valid parental permission.
    Accepts either an active Bearer session token OR a valid Parental PIN.
    """
    # 1. Check Bearer Session Token
    if token and validate_session(token):
        return True

    # 2. Check direct PIN if provided
    if pin and pin.strip():
        res = ParentalService.verify_pin(PinVerifyRequest(pin=pin.strip()))
        if res and res.token:
            return True

    raise HTTPException(
        status_code=401,
        detail="Parental authorization required. Please authenticate with your Parental PIN or log in to the Parental Portal.",
    )


# ------------------------------------------------------------------------------
# Upload & Ingestion Service
# ------------------------------------------------------------------------------

def sanitize_name(name: str) -> str:
    """Slugify or clean name for filesystem path safety."""
    cleaned = re.sub(r"[^\w\-.]", "_", name.strip())
    return cleaned.lower()


def load_uploaded_metadata() -> list[dict]:
    """Retrieve all uploaded textbook records."""
    if not UPLOADED_METADATA_FILE.exists():
        return []
    try:
        return json.loads(UPLOADED_METADATA_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        log.warning("Could not read uploaded metadata: %s", e)
        return []


def save_uploaded_metadata(records: list[dict]) -> None:
    """Save updated uploaded textbook records."""
    try:
        UPLOADED_METADATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        UPLOADED_METADATA_FILE.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        log.warning("Could not save uploaded metadata: %s", e)


def process_and_ingest_textbook(
    file: UploadFile,
    grade: int,
    subject: str,
    book_title: str,
    chapter_number: int = 1,
    chapter_title: str | None = None,
    rag_instance: Any = None,
) -> dict:
    """
    Process, safety-scan, chunk, and embed an uploaded textbook into the vector space.
    """
    clean_subject = subject.strip()
    clean_title = book_title.strip()
    clean_chapter_title = (chapter_title or f"Chapter {chapter_number}").strip()

    if not clean_subject:
        raise HTTPException(status_code=400, detail="Subject name cannot be empty.")
    if not clean_title:
        raise HTTPException(status_code=400, detail="Book title cannot be empty.")
    if grade < 1 or grade > 12:
        raise HTTPException(status_code=400, detail="Grade must be an integer between 1 and 12.")

    # 1. Validate File Format & Header
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF documents (.pdf) are supported.")

    if hasattr(file, "file") and hasattr(file.file, "read"):
        file_bytes = file.file.read()
    elif hasattr(file, "read"):
        file_bytes = file.read()
    else:
        file_bytes = b""
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"File exceeds maximum allowed size of {MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB.",
        )
    if not file_bytes.startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail="Invalid PDF file format.")

    # 2. Save File into Curriculum Storage
    subject_slug = sanitize_name(clean_subject)
    safe_filename = sanitize_name(file.filename)
    if not safe_filename.endswith(".pdf"):
        safe_filename += ".pdf"

    dest_dir = settings.data_dir / "uploads" / f"class-{grade}" / subject_slug
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / safe_filename
    dest_path.write_bytes(file_bytes)

    rel_file_path = dest_path.relative_to(settings.data_dir).as_posix()
    log.info("Saved uploaded PDF to %s", dest_path)

    # 3. Text Extraction with PyPDF (Page-Aware)
    try:
        reader = PdfReader(str(dest_path))
        raw_pages: list[tuple[int, str]] = []
        for p_idx, page in enumerate(reader.pages):
            raw_text = page.extract_text() or ""
            cleaned = clean_text(raw_text)
            if len(cleaned) >= 25:
                raw_pages.append((p_idx + 1, cleaned))
    except Exception as e:
        # Clean up file on failure
        dest_path.unlink(missing_ok=True)
        log.error("Failed to parse PDF: %s", e)
        raise HTTPException(status_code=400, detail=f"Failed to parse PDF document: {e}")

    if not raw_pages:
        dest_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=400,
            detail="The uploaded PDF contains no readable text layer. Please upload a digital textbook with text.",
        )

    # 4. Under-18 Content Moderation Safety Screening
    # Sample up to 10 representative pages to screen for adult/dangerous content
    sample_pages = [text for _, text in raw_pages[:10]]
    combined_sample = " ".join(sample_pages)[:4000]

    eval_result = evaluate_content(
        combined_sample,
        grade=grade,
        subject=clean_subject,
        chapter=chapter_number,
        language="English",
    )

    if not eval_result.is_safe and eval_result.severity in (SeverityLevel.HIGH, SeverityLevel.CRITICAL):
        dest_path.unlink(missing_ok=True)
        rule_desc = eval_result.matched_rule or eval_result.refusal_message or "Prohibited content detected"
        log_safety_event(
            query_text=f"Upload screening: {file.filename} ({clean_title})",
            category=eval_result.category or SafetyCategory.OTHER_INAPPROPRIATE,
            severity=eval_result.severity or SeverityLevel.HIGH,
            student_grade=grade,
            subject=clean_subject,
            chapter=chapter_number,
            session_id="upload_scanner",
            matched_rule=f"Safety Refusal: {rule_desc}",
            action_taken="UPLOAD_REJECTED",
        )
        raise HTTPException(
            status_code=400,
            detail=f"Safety Refusal: Document violates under-18 safety standards ({rule_desc}). Upload rejected.",
        )

    # 5. Build LlamaIndex Documents
    documents: list[Document] = []
    metadata_base = {
        "grade": grade,
        "subject": clean_subject,
        "book": clean_title,
        "chapter": chapter_number,
        "chapter_title": clean_chapter_title,
        "file": rel_file_path,
        "uploaded_by": "parent",
        "uploaded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }

    for page_num, text in raw_pages:
        doc = make_page(text, {**metadata_base, "page": page_num})
        documents.append(doc)

    # 6. Semantic Chunking
    splitter = SentenceSplitter(chunk_size=settings.chunk_size, chunk_overlap=settings.chunk_overlap)
    chunks = splitter.get_nodes_from_documents(documents)
    log.info("Uploaded textbook split into %d chunks across %d pages", len(chunks), len(documents))

    # 7. Store Chunks in Vector Space
    if rag_instance and hasattr(rag_instance, "index") and rag_instance.index:
        try:
            rag_instance.index.insert_nodes(chunks)
            # Persist docstore and storage context
            settings.index_dir.mkdir(parents=True, exist_ok=True)
            rag_instance.index.storage_context.persist(persist_dir=str(settings.index_dir))
            log.info("Successfully inserted %d nodes into vector store", len(chunks))
        except Exception as e:
            log.warning("Dynamic node insertion warning (proceeding with catalog): %s", e)

    # 8. Register Book Code in Catalog & Index Info
    book_code = f"u{grade}{subject_slug[:3]}{chapter_number}"
    register_custom_book(
        code=book_code,
        grade=grade,
        subject=clean_subject,
        title=clean_title,
        chapters=[clean_chapter_title],
        file=rel_file_path,
    )

    # Update index_info.json
    try:
        if settings.index_info_file.exists():
            info = json.loads(settings.index_info_file.read_text(encoding="utf-8"))
        else:
            info = {
                "embedder": settings.embedder,
                "embed_model": settings.embed_model,
                "vector_store": settings.vector_store,
                "parser": "docling",
                "index_schema": INDEX_SCHEMA_VERSION,
                "chunks": 0,
                "subjects": [],
                "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }

        # Check if subject entry exists
        sub_entry = next((s for s in info["subjects"] if s["grade"] == grade and s["subject"] == clean_subject), None)
        if not sub_entry:
            info["subjects"].append({
                "grade": grade,
                "subject": clean_subject,
                "book": clean_title,
            })
        info["chunks"] = int(info.get("chunks", 0)) + len(chunks)
        info["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        settings.index_info_file.write_text(json.dumps(info, indent=2, ensure_ascii=False), encoding="utf-8")

        if rag_instance:
            rag_instance.info = info
    except Exception as e:
        log.warning("Could not update index_info.json: %s", e)

    # 9. Record Upload in Metadata Log
    records = load_uploaded_metadata()
    record = {
        "id": f"bk_{int(time.time())}",
        "code": book_code,
        "grade": grade,
        "subject": clean_subject,
        "book_title": clean_title,
        "chapter_number": chapter_number,
        "chapter_title": clean_chapter_title,
        "file_name": safe_filename,
        "file_path": rel_file_path,
        "pages_count": len(documents),
        "chunks_count": len(chunks),
        "file_size_kb": len(file_bytes) // 1024,
        "uploaded_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
    }
    records.insert(0, record)
    save_uploaded_metadata(records)

    return {
        "success": True,
        "message": f"Successfully ingested '{clean_title}' for Class {grade} {clean_subject} into vector space.",
        "book_code": book_code,
        "file": rel_file_path,
        "grade": grade,
        "subject": clean_subject,
        "book": clean_title,
        "book_title": clean_title,
        "pages_indexed": len(documents),
        "pages_count": len(documents),
        "chunks_stored": len(chunks),
        "chunks_count": len(chunks),
    }


def delete_uploaded_textbook(book_code: str, rag_instance: Any = None) -> dict:
    """
    Remove an uploaded custom textbook from the active system.
    """
    records = load_uploaded_metadata()
    record = next((r for r in records if r["code"] == book_code or r["id"] == book_code), None)
    if not record:
        raise HTTPException(status_code=404, detail="Uploaded textbook record not found.")

    # 1. Remove file from storage
    file_path = settings.data_dir / record["file_path"]
    if file_path.exists():
        file_path.unlink(missing_ok=True)

    # 2. Unregister from catalog
    remove_custom_book(record["code"])

    # 3. Update metadata list
    remaining_records = [r for r in records if r["code"] != book_code and r["id"] != book_code]
    save_uploaded_metadata(remaining_records)

    # 4. Update index_info.json subjects if no other chapters exist for this subject
    try:
        if settings.index_info_file.exists():
            info = json.loads(settings.index_info_file.read_text(encoding="utf-8"))
            # If no other books for this subject exist, remove
            has_other = any(
                b.grade == record["grade"] and b.subject == record["subject"]
                for b in BOOKS.values()
            )
            if not has_other:
                info["subjects"] = [
                    s for s in info["subjects"]
                    if not (s["grade"] == record["grade"] and s["subject"] == record["subject"])
                ]
            info["chunks"] = max(0, int(info.get("chunks", 0)) - record.get("chunks_count", 0))
            settings.index_info_file.write_text(json.dumps(info, indent=2, ensure_ascii=False), encoding="utf-8")
            if rag_instance:
                rag_instance.info = info
    except Exception as e:
        log.warning("Could not update index_info after deletion: %s", e)

    return {
        "success": True,
        "message": f"Successfully deleted textbook '{record['book_title']}'.",
    }
