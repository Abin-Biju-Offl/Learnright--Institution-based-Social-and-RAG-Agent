"""
Pydantic Request and Response Schemas for Multi-Tenant School Organizations,
Classes, Sections, Role-Specific Invites, and Faculty Management.
"""

from datetime import datetime
from pydantic import BaseModel, Field


# ── Institution Lifecycle ──

class InstitutionCreateRequest(BaseModel):
    name: str = Field(min_length=3, max_length=150, description="School/Institution Name")
    demo_verification_id: str = Field(
        min_length=3, max_length=64, description="Demo verification ID or registration code"
    )


class InstitutionJoinRequest(BaseModel):
    demo_verification_id: str = Field(
        min_length=3, max_length=64, description="Institution verification or access code"
    )


class InstitutionResponse(BaseModel):
    id: str
    name: str
    demo_verification_id: str
    is_active: bool
    created_at: datetime


# ── Classes & Sections ──

class ClassCreateRequest(BaseModel):
    grade: int = Field(ge=1, le=12, description="NCERT Grade (1 to 12)")
    display_name: str | None = Field(default=None, max_length=60, description="e.g. 'Class 10'")


class SectionCreateRequest(BaseModel):
    section_name: str = Field(min_length=1, max_length=20, description="e.g. 'A', 'B', 'Science'")
    room: str | None = Field(default=None, max_length=50)


class SectionResponse(BaseModel):
    id: str
    class_id: str
    section_name: str
    room: str | None = None
    class_advisor_id: str | None = None
    class_advisor_name: str | None = None
    student_count: int = 0


class ClassResponse(BaseModel):
    id: str
    institution_id: str
    grade: int
    display_name: str
    sections: list[SectionResponse] = []


# ── Invites ──

class InviteCreateRequest(BaseModel):
    target_role: str = Field(pattern=r"^(lecturer|student)$", description="'lecturer' or 'student'")
    class_id: str | None = Field(default=None, description="Required for student invites")
    section_id: str | None = Field(default=None, description="Required for student invites")
    max_uses: int = Field(default=50, ge=1, le=1000)
    expires_days: int = Field(default=14, ge=1, le=90)


class InviteResponse(BaseModel):
    id: str
    token: str
    invite_url: str
    target_role: str
    institution_id: str
    institution_name: str
    class_id: str | None = None
    class_display_name: str | None = None
    section_id: str | None = None
    section_name: str | None = None
    max_uses: int
    uses_count: int
    expires_at: datetime


class InviteVerifyResponse(BaseModel):
    valid: bool
    institution_id: str
    institution_name: str
    target_role: str
    grade: int | None = None
    class_display_name: str | None = None
    section_name: str | None = None


class InviteAcceptRequest(BaseModel):
    invite_token: str = Field(min_length=8, max_length=64)


# ── Faculty & Lecturer Profiles ──

class LecturerProfileUpdateRequest(BaseModel):
    subject_tags: list[str] = Field(default_factory=list, description="e.g. ['Science', 'Physics']")


class ClassAdvisorAssignRequest(BaseModel):
    advisor_user_id: str | None = Field(
        default=None, description="User ID of faculty member to assign as Class Advisor (null to unassign)"
    )


class FacultyMemberResponse(BaseModel):
    id: str
    username: str
    full_name: str | None = None
    role: str
    subject_tags: list[str] = []
    advised_sections: list[dict[str, str]] = []  # [{'section_id': '...', 'class_name': '...', 'section_name': '...'}]


class StudentRosterItem(BaseModel):
    id: str
    username: str
    full_name: str | None = None
    grade: int | None = None
    class_name: str | None = None
    section_name: str | None = None
    created_at: datetime
