"""
Pydantic request/response schemas for the auth endpoints.
"""

from pydantic import BaseModel, Field


# ──────────────────────────────────────────────────────────────────────────────
# Requests
# ──────────────────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    """Register a new student, lecturer (faculty), or admin account."""
    username: str = Field(min_length=3, max_length=30, pattern=r"^[a-zA-Z0-9_]+$")
    password: str = Field(min_length=6, max_length=128)
    role: str = Field(default="student", description="'student', 'lecturer', or 'org_admin'")
    grade: int | None = Field(default=None, ge=1, le=12, description="Student's class (1-12); optional for admins/faculty")
    full_name: str | None = Field(default=None, max_length=100)
    subject_tags: list[str] | None = Field(default=None, description="Faculty taught subjects")


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=30)
    password: str = Field(min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


# ──────────────────────────────────────────────────────────────────────────────
# Responses
# ──────────────────────────────────────────────────────────────────────────────

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in_minutes: int
    user: dict


class UserResponse(BaseModel):
    id: str
    username: str
    full_name: str | None = None
    role: str = "student"
    grade: int | None = None
    institution_id: str | None = None
    institution_name: str | None = None
    class_id: str | None = None
    section_id: str | None = None
    subject_tags: list[str] = []
    is_active: bool = True
    created_at: str


class MessageResponse(BaseModel):
    success: bool
    message: str
