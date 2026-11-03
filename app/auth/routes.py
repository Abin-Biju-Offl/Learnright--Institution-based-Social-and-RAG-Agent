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

from pydantic import BaseModel, Field

from app.auth.dependencies import get_current_student
from app.auth.jwt_handler import (
    TokenError,
    create_token_pair,
    decode_refresh_token,
)
from app.auth.models import authenticate_user, create_user, get_user_by_id, get_user_by_username
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
    role = req.role if req.role in ("student", "lecturer", "org_admin") else "student"
    if role == "student" and req.grade is None:
        raise HTTPException(status_code=400, detail="Student registration requires a valid class grade (1-12).")

    try:
        user = create_user(
            username=req.username,
            password=req.password,
            grade=req.grade if role == "student" else None,
            role=role,
            full_name=req.full_name,
            subject_tags=req.subject_tags if role == "lecturer" else None,
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


class DemoSwitchRequest(BaseModel):
    role: str = Field(default="student", description="student | org_admin | lecturer")
    grade: int | None = Field(default=10, description="Grade for student role")


@auth_router.post("/demo-switch", response_model=TokenResponse)
def demo_switch(req: DemoSwitchRequest):
    """
    Seamlessly issues a real signed JWT token for demo role switching
    (student, org_admin, or lecturer), ensuring the user has a valid access
    token with full claims in localStorage.
    """
    target_role = req.role if req.role in ("student", "org_admin", "lecturer") else "student"

    if target_role == "org_admin":
        username = "demo_principal"
        user = get_user_by_username(username)
        if not user:
            user = create_user(
                username=username,
                password="password123",
                role="org_admin",
                full_name="Principal Sharma",
            )
    elif target_role == "lecturer":
        username = "demo_lecturer"
        user = get_user_by_username(username)
        if not user:
            user = create_user(
                username=username,
                password="password123",
                role="lecturer",
                full_name="Dr. Homi Bhabha (Faculty)",
                subject_tags=["Science", "Physics"],
            )
    else:
        username = "demo_student"
        user = get_user_by_username(username)
        if not user:
            user = create_user(
                username=username,
                password="password123",
                role="student",
                grade=req.grade or 10,
                full_name="Abin Biju",
            )

    # If demo institution exists in DB and demo user lacks institution link, link seamlessly
    if user and not user.get("institution_id"):
        try:
            from app.db.engine import SessionLocal
            from app.db.models import Classroom as SqlClass, Institution as SqlInst, Section as SqlSec, User as SqlUser
            db = SessionLocal()
            try:
                demo_inst = db.query(SqlInst).filter(SqlInst.id == "inst_demo_dps2026").first()
                if demo_inst:
                    su = db.query(SqlUser).filter(SqlUser.username == username).first()
                    if su:
                        su.institution_id = demo_inst.id
                        if target_role == "student":
                            cls_10 = db.query(SqlClass).filter(SqlClass.institution_id == demo_inst.id, SqlClass.grade == 10).first()
                            sec_10a = db.query(SqlSec).filter(SqlSec.class_id == cls_10.id, SqlSec.section_name == "A").first() if cls_10 else None
                            if cls_10:
                                su.class_id = cls_10.id
                            if sec_10a:
                                su.section_id = sec_10a.id
                        db.commit()
                        user = get_user_by_username(username)
            finally:
                db.close()
        except Exception:
            pass

    tokens = create_token_pair(
        user_id=user["id"],
        username=user["username"],
        role=user.get("role", "student"),
        grade=user.get("grade"),
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

