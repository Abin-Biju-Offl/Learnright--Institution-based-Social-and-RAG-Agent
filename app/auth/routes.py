"""
Auth API routes — student registration, login, token refresh, and profile.

    POST /api/auth/register   — create a new student account (with grade)
    POST /api/auth/login      — verify credentials, get JWT token pair
    POST /api/auth/refresh    — exchange a refresh token for a new access token
    GET  /api/auth/me         — get the current student's profile
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.auth.dependencies import get_current_student
from app.auth.jwt_handler import (
    TokenError,
    create_token_pair,
    decode_refresh_token,
)
from app.auth.models import authenticate_user, create_user, get_user_by_id
from app.auth.schemas import (
    LoginRequest,
    MessageResponse,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.config import ROOT, settings

log = logging.getLogger(__name__)

auth_router = APIRouter()


@auth_router.post("/register", response_model=TokenResponse)
def register(req: RegisterRequest):
    """
    Register a new student or organization administrator account.
    """
    role = req.role if req.role in ("student", "org_admin") else "student"
    if role == "student" and req.grade is None:
        raise HTTPException(status_code=400, detail="Student registration requires a valid class grade (1-12).")

    try:
        user = create_user(
            username=req.username,
            password=req.password,
            grade=req.grade,
            role=role,
            full_name=req.full_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    tokens = create_token_pair(
        user_id=user["id"],
        username=user["username"],
        grade=user.get("grade"),
        role=user.get("role", "student"),
        institution_id=user.get("institution_id"),
        institution_name=user.get("institution_name"),
        class_id=user.get("class_id"),
        section_id=user.get("section_id"),
        subject_tags=user.get("subject_tags", []),
    )
    log.info("New user registered: %s (Role: %s, Grade: %s)", user["username"], user.get("role"), user.get("grade"))

    return TokenResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        expires_in_minutes=settings.jwt_access_expire_minutes,
        user=user,
    )


@auth_router.get("/login")
def get_login_view():
    """Serves the login page or JSON API instructions."""
    login_html = ROOT / "frontend" / "login.html"
    if login_html.exists():
        return FileResponse(login_html)
    return {
        "message": "Student Login Endpoint. Submit a POST request with {'username', 'password'} to receive a JWT access token.",
        "ui_url": "/login",
    }


@auth_router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest):
    """
    Authenticate with username and password.

    Returns an access token carrying role, grade, and institutional context claims.
    """
    user = authenticate_user(req.username, req.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    tokens = create_token_pair(
        user_id=user["id"],
        username=user["username"],
        grade=user.get("grade"),
        role=user.get("role", "student"),
        institution_id=user.get("institution_id"),
        institution_name=user.get("institution_name"),
        class_id=user.get("class_id"),
        section_id=user.get("section_id"),
        subject_tags=user.get("subject_tags", []),
    )
    log.info("User logged in: %s (Role: %s)", user["username"], user.get("role"))

    return TokenResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        expires_in_minutes=settings.jwt_access_expire_minutes,
        user=user,
    )


@auth_router.post("/refresh", response_model=TokenResponse)
def refresh(req: RefreshRequest):
    """
    Exchange a valid refresh token for a fresh access token.
    """
    try:
        payload = decode_refresh_token(req.refresh_token)
    except TokenError as exc:
        raise HTTPException(status_code=401, detail=str(exc))

    user = get_user_by_id(payload["sub"])
    if user is None:
        raise HTTPException(status_code=401, detail="User account not found or deactivated.")

    tokens = create_token_pair(
        user_id=user["id"],
        username=user["username"],
        grade=user.get("grade"),
        role=user.get("role", "student"),
        institution_id=user.get("institution_id"),
        institution_name=user.get("institution_name"),
        class_id=user.get("class_id"),
        section_id=user.get("section_id"),
        subject_tags=user.get("subject_tags", []),
    )

    return TokenResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        expires_in_minutes=settings.jwt_access_expire_minutes,
        user=user,
    )


@auth_router.get("/me", response_model=UserResponse)
def me(student: dict = Depends(get_current_student)):
    """Return the currently authenticated user's profile."""
    return UserResponse(
        id=student["id"],
        username=student["username"],
        full_name=student.get("full_name"),
        role=student.get("role", "student"),
        grade=student.get("grade"),
        institution_id=student.get("institution_id"),
        institution_name=student.get("institution_name"),
        class_id=student.get("class_id"),
        section_id=student.get("section_id"),
        subject_tags=student.get("subject_tags", []),
        is_active=student.get("is_active", True),
        created_at=student["created_at"],
    )

