"""
Unit and integration tests for the Parent-Controlled Textbook Upload & Auto-Ingestion System.
"""

import io
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException, UploadFile
from fastapi.security import HTTPAuthorizationCredentials

from app.catalog import BOOKS, remove_custom_book
from app.config import settings
from app.parental import routes
from app.parental.auth import create_session, clear_all_sessions
from app.parental.schemas import PinSetupRequest
from app.textbook_upload import (
    process_and_ingest_textbook,
    verify_parental_authorization,
    load_uploaded_metadata,
)


def _create_sample_pdf_bytes(text: str = "This is a sample science lesson on photosynthesis.") -> bytes:
    """Helper to create valid PDF bytes with text stream in memory without external tools."""
    content = f"BT /F1 12 Tf 72 712 Td ({text}) Tj ET".encode("latin-1")
    pdf = (
        b"%PDF-1.4\n"
        b"1 0 obj <</Type /Catalog /Pages 2 0 R>> endobj\n"
        b"2 0 obj <</Type /Pages /Kids [3 0 R] /Count 1>> endobj\n"
        b"3 0 obj <</Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources <</Font <</F1 5 0 R>>>>>> endobj\n"
        b"4 0 obj <</Length " + str(len(content)).encode("ascii") + b">> stream\n"
        + content + b"\nendstream\nendobj\n"
        b"5 0 obj <</Type /Font /Subtype /Type1 /BaseFont /Helvetica>> endobj\n"
        b"xref\n0 6\n"
        b"0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n"
        b"0000000115 00000 n \n0000000244 00000 n \n0000000350 00000 n \n"
        b"trailer <</Size 6 /Root 1 0 R>>\nstartxref\n425\n%%EOF\n"
    )
    return pdf


@pytest.fixture(autouse=True)
def clean_environment(tmp_path):
    """Isolate storage and test catalogs for each run."""
    clear_all_sessions()
    test_storage = tmp_path / "storage"
    test_storage.mkdir(parents=True, exist_ok=True)
    test_data = tmp_path / "data"
    test_data.mkdir(parents=True, exist_ok=True)

    with patch.object(settings, "storage_dir", test_storage), \
         patch.object(settings, "data_dir", test_data), \
         patch("app.catalog.CUSTOM_BOOKS_FILE", test_storage / "custom_books.json"), \
         patch("app.textbook_upload.UPLOADED_METADATA_FILE", test_storage / "uploaded_textbooks_meta.json"):
        yield


# ==============================================================================
# 1. PARENTAL AUTHORIZATION TESTS
# ==============================================================================

def test_verify_parental_authorization_no_credentials():
    """Uploading without token or PIN must raise HTTP 401."""
    with pytest.raises(HTTPException) as exc:
        verify_parental_authorization(token=None, pin=None)
    assert exc.value.status_code == 401


def test_verify_parental_authorization_invalid_pin():
    """Uploading with invalid PIN must raise HTTP 400 or 401."""
    routes.setup_pin(PinSetupRequest(pin="1234", confirm_pin="1234"))
    with pytest.raises(HTTPException) as exc:
        verify_parental_authorization(pin="9999")
    assert exc.value.status_code in (401, 403)


def test_verify_parental_authorization_valid_pin():
    """Uploading with correct PIN succeeds."""
    routes.setup_pin(PinSetupRequest(pin="1234", confirm_pin="1234"))
    assert verify_parental_authorization(pin="1234") is True


def test_verify_parental_authorization_valid_token():
    """Uploading with valid parent Bearer session token succeeds."""
    token = create_session(timeout_seconds=300)
    assert verify_parental_authorization(token=token) is True


# ==============================================================================
# 2. FILE FORMAT & SAFETY VALIDATION
# ==============================================================================

def test_upload_rejects_non_pdf():
    """Files not ending in .pdf must be rejected with HTTP 400."""
    file = UploadFile(filename="lesson.txt", file=io.BytesIO(b"Hello world"))
    with pytest.raises(HTTPException) as exc:
        process_and_ingest_textbook(
            file=file,
            grade=9,
            subject="Physics",
            book_title="Class 9 Physics",
        )
    assert exc.value.status_code == 400
    assert "PDF" in exc.value.detail


def test_upload_rejects_invalid_pdf_header():
    """A .pdf file that does not start with %PDF- header is rejected."""
    file = UploadFile(filename="corrupt.pdf", file=io.BytesIO(b"Not a real pdf content"))
    with pytest.raises(HTTPException) as exc:
        process_and_ingest_textbook(
            file=file,
            grade=9,
            subject="Physics",
            book_title="Class 9 Physics",
        )
    assert exc.value.status_code == 400
    assert "Invalid PDF" in exc.value.detail


def test_upload_rejects_inappropriate_content():
    """Textbooks containing adult sexual or violent content must be blocked under U18 safety."""
    inappropriate_text = (
        "This chapter details extreme adult pornography, sexual violence, and illegal weapons manufacturing "
        "and explosive chemical bombs designed to cause severe injury and terror."
    )
    pdf_bytes = _create_sample_pdf_bytes(inappropriate_text)
    file = UploadFile(filename="unsafe_manual.pdf", file=io.BytesIO(pdf_bytes))

    with pytest.raises(HTTPException) as exc:
        process_and_ingest_textbook(
            file=file,
            grade=10,
            subject="Defense",
            book_title="Dangerous Manual",
        )
    assert exc.value.status_code == 400
    assert "Safety Refusal" in exc.value.detail


# ==============================================================================
# 3. END-TO-END INGESTION & CATALOG INTEGRATION
# ==============================================================================

def test_upload_success_and_catalog_registration():
    """A valid educational PDF is extracted, chunked, registered, and queryable."""
    edu_text = (
        "Photosynthesis is the fundamental biological process by which green plants and certain "
        "other organisms transform light energy into chemical energy. During photosynthesis in green plants, "
        "light energy is captured and used to convert water, carbon dioxide, and minerals into oxygen and "
        "energy-rich organic compounds like glucose and starches. The chloroplasts contain chlorophyll pigments."
    )
    pdf_bytes = _create_sample_pdf_bytes(edu_text)
    file = UploadFile(filename="class9_botany.pdf", file=io.BytesIO(pdf_bytes))

    mock_rag = MagicMock()
    mock_rag.index = MagicMock()
    mock_rag.info = {"subjects": []}

    result = process_and_ingest_textbook(
        file=file,
        grade=9,
        subject="Botany",
        book_title="Introductory Botany",
        chapter_number=1,
        chapter_title="Plant Physiology & Photosynthesis",
        rag_instance=mock_rag,
    )

    assert result["success"] is True
    assert result["grade"] == 9
    assert result["subject"] == "Botany"
    assert result["book_title"] == "Introductory Botany"
    assert result["chunks_count"] >= 1
    assert result["pages_count"] == 1

    # Check node insertion into vector space
    assert mock_rag.index.insert_nodes.called

    # Check catalog registration
    book_code = result["book_code"]
    assert book_code in BOOKS
    registered_book = BOOKS[book_code]
    assert registered_book.grade == 9
    assert registered_book.subject == "Botany"
    assert registered_book.title == "Introductory Botany"
    assert "Plant Physiology & Photosynthesis" in registered_book.chapters

    # Check persistence in metadata
    meta = load_uploaded_metadata()
    assert len(meta) == 1
    assert meta[0]["code"] == book_code
    assert meta[0]["subject"] == "Botany"

    # Cleanup custom book
    remove_custom_book(book_code)
    assert book_code not in BOOKS


# ==============================================================================
# 4. PARENTAL ROUTER ENDPOINT TESTS
# ==============================================================================

def test_parental_routes_upload_and_delete_workflow():
    """Test router functions upload_textbook, list_uploaded_textbooks, and delete_uploaded_textbook."""
    routes.setup_pin(PinSetupRequest(pin="2468", confirm_pin="2468"))
    token = create_session(timeout_seconds=900)
    bearer_creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    edu_text = (
        "Gravitation is a natural phenomenon by which all things with mass or energy are attracted "
        "toward one another. On Earth, gravity gives weight to physical objects."
    )
    pdf_bytes = _create_sample_pdf_bytes(edu_text)
    file = UploadFile(filename="physics_ch1.pdf", file=io.BytesIO(pdf_bytes))

    # 1. Upload via route
    res = routes.upload_textbook(
        file=file,
        grade=9,
        subject="Physics",
        book_title="Conceptual Physics",
        chapter_number=1,
        chapter_title="Universal Gravitation",
        pin=None,
        credentials=bearer_creds,
    )
    assert res["success"] is True
    book_code = res["book_code"]

    # 2. List uploaded textbooks
    list_res = routes.list_textbooks(token=token)
    books = list_res["textbooks"]
    assert any(b["code"] == book_code for b in books)

    # 3. Delete uploaded textbook
    del_res = routes.delete_textbook(book_code=book_code, token=token)
    assert del_res["success"] is True

    # 4. Verify book is removed from catalog and list
    assert book_code not in BOOKS
    list_after = routes.list_textbooks(token=token)["textbooks"]
    assert not any(b["code"] == book_code for b in list_after)
