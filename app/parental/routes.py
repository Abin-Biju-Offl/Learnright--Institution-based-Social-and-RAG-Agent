"""
FastAPI route definitions for Parental Controls (/api/parent/*).
"""

from typing import Any
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Security, UploadFile
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.parental.auth import revoke_session, validate_session
from app.parental.schemas import (
    AuthStatusResponse,
    AuthTokenResponse,
    ChangePinRequest,
    ChatHistoryResponse,
    FlaggedAlertsResponse,
    LogoutResponse,
    OverviewResponse,
    ParentalSettingsUpdate,
    PinSetupRequest,
    PinVerifyRequest,
    ResetPinRequest,
    ReviewFlagRequest,
    ReviewFlagResponse,
    SettingsResponse,
)
from app.parental.service import ParentalService

parental_router = APIRouter()
security_bearer = HTTPBearer(auto_error=False)


def require_parent_session(
    credentials: HTTPAuthorizationCredentials | None = Security(security_bearer),
) -> str:
    """
    Dependency verifying that the request presents an active, unexpired Bearer session token.
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Please provide a valid Bearer token.",
        )
    token = credentials.credentials
    if not validate_session(token):
        raise HTTPException(
            status_code=401,
            detail="Session expired or invalid. Please re-authenticate with your parental PIN.",
        )
    return token


# ------------------------------------------------------------------------------
# Authentication & PIN Management Endpoints
# ------------------------------------------------------------------------------

@parental_router.get("/auth/status", response_model=AuthStatusResponse)
def get_auth_status():
    """Check if parental PIN is configured and if brute-force lockout is active."""
    return ParentalService.get_auth_status()


@parental_router.post("/auth/setup", response_model=AuthTokenResponse)
def setup_pin(req: PinSetupRequest):
    """Initial PIN configuration. Generates an Emergency Recovery Key."""
    return ParentalService.setup_pin(req)


@parental_router.post("/auth/verify", response_model=AuthTokenResponse)
def verify_pin(req: PinVerifyRequest):
    """Verify parental PIN and issue a 15-minute Bearer session token."""
    return ParentalService.verify_pin(req)


@parental_router.post("/auth/change-pin")
def change_pin(req: ChangePinRequest, token: str = Depends(require_parent_session)):
    """Authenticated PIN update."""
    return ParentalService.change_pin(req)


@parental_router.post("/auth/reset-pin", response_model=AuthTokenResponse)
def reset_pin(req: ResetPinRequest):
    """Reset forgotten PIN using 16-character Emergency Recovery Key."""
    return ParentalService.reset_pin(req)


@parental_router.post("/auth/logout", response_model=LogoutResponse)
def logout(token: str = Depends(require_parent_session)):
    """Terminate the active parental session token."""
    revoke_session(token)
    return LogoutResponse(success=True, message="Session terminated successfully.")


# ------------------------------------------------------------------------------
# Overview & Metrics Endpoints
# ------------------------------------------------------------------------------

@parental_router.get("/overview", response_model=OverviewResponse)
def get_overview(token: str = Depends(require_parent_session)):
    """Fetch high-level student activity and safety metrics for guardian dashboard."""
    return ParentalService.get_overview()


def _unwrap_arg(val: Any, default: Any = None) -> Any:
    if hasattr(val, "default"):
        return val.default
    return val if val is not None else default


# ------------------------------------------------------------------------------
# Student Chat History Endpoints
# ------------------------------------------------------------------------------

@parental_router.get("/history", response_model=ChatHistoryResponse)
def get_history(
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    grade: int | None = Query(default=None),
    subject: str | None = Query(default=None),
    flagged_only: bool = Query(default=False),
    search: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    token: str = Depends(require_parent_session),
):
    """Query and filter student conversation history with search and pagination."""
    return ParentalService.get_history(
        limit=_unwrap_arg(limit, 25),
        offset=_unwrap_arg(offset, 0),
        grade=_unwrap_arg(grade, None),
        subject=_unwrap_arg(subject, None),
        flagged_only=_unwrap_arg(flagged_only, False),
        search=_unwrap_arg(search, None),
        date_from=_unwrap_arg(date_from, None),
        date_to=_unwrap_arg(date_to, None),
    )


@parental_router.delete("/history")
def clear_history(token: str = Depends(require_parent_session)):
    """Clear historical student conversation records."""
    return ParentalService.clear_history()


# ------------------------------------------------------------------------------
# Flagged Queries & Review Endpoints
# ------------------------------------------------------------------------------

@parental_router.get("/flagged", response_model=FlaggedAlertsResponse)
def get_flagged(
    status: str = Query(default="PENDING"),
    category: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    token: str = Depends(require_parent_session),
):
    """Retrieve logged safety events and blocked queries with review status."""
    return ParentalService.get_flagged(
        status=_unwrap_arg(status, "PENDING"),
        category=_unwrap_arg(category, None),
        limit=_unwrap_arg(limit, 50),
    )


@parental_router.post("/flagged/{event_id}/review", response_model=ReviewFlagResponse)
def review_flag(
    event_id: str,
    req: ReviewFlagRequest,
    token: str = Depends(require_parent_session),
):
    """Acknowledge or dismiss a flagged query alert with parent notes."""
    return ParentalService.review_flag(event_id=event_id, action=req.action, notes=req.notes)


# ------------------------------------------------------------------------------
# Content Filtering Settings Endpoints
# ------------------------------------------------------------------------------

@parental_router.get("/settings", response_model=SettingsResponse)
def get_settings(token: str = Depends(require_parent_session)):
    """Fetch current category toggles and custom blocked keywords."""
    return ParentalService.get_settings()


@parental_router.put("/settings", response_model=SettingsResponse)
def update_settings(
    update: ParentalSettingsUpdate,
    token: str = Depends(require_parent_session),
):
    """Persist updated filtering preferences, strictness profiles, and keyword blacklists."""
    return ParentalService.update_settings(update)


# ------------------------------------------------------------------------------
# Textbook Upload & Vector Ingestion (Parental Governance)
# ------------------------------------------------------------------------------

@parental_router.post("/textbook/upload")
def upload_textbook(
    file: UploadFile = File(...),
    grade: int = Form(...),
    subject: str = Form(...),
    book_title: str = Form(...),
    chapter_number: int = Form(1),
    chapter_title: str | None = Form(None),
    pin: str | None = Form(None),
    credentials: HTTPAuthorizationCredentials | None = Security(security_bearer),
):
    """
    Parent-authorized textbook upload, chunking, and embedding into vector space.
    Requires either a valid Bearer session token or a verified Parental PIN.
    """
    from app.textbook_upload import process_and_ingest_textbook, verify_parental_authorization

    token = credentials.credentials if credentials else None
    verify_parental_authorization(token=token, pin=pin)

    # Lazy-import get_rag from app.main to avoid circular imports
    from app.main import get_rag
    try:
        rag = get_rag()
    except Exception:
        rag = None

    return process_and_ingest_textbook(
        file=file,
        grade=grade,
        subject=subject,
        book_title=book_title,
        chapter_number=chapter_number,
        chapter_title=chapter_title,
        rag_instance=rag,
    )


@parental_router.get("/textbooks")
def list_textbooks(token: str = Depends(require_parent_session)):
    """List all parent-uploaded custom textbooks."""
    from app.textbook_upload import load_uploaded_metadata
    return {"textbooks": load_uploaded_metadata()}


@parental_router.delete("/textbook/{book_code}")
def delete_textbook(book_code: str, token: str = Depends(require_parent_session)):
    """Delete an uploaded custom textbook from disk, catalog, and vector space."""
    from app.textbook_upload import delete_uploaded_textbook
    from app.main import get_rag
    try:
        rag = get_rag()
    except Exception:
        rag = None
    return delete_uploaded_textbook(book_code, rag_instance=rag)

