"""
Pydantic schemas and data models for Parental Controls.
"""

from typing import Any, Literal
from pydantic import BaseModel, Field


# ------------------------------------------------------------------------------
# Authentication Models
# ------------------------------------------------------------------------------

class PinSetupRequest(BaseModel):
    pin: str = Field(min_length=4, max_length=6, pattern=r"^\d{4,6}$")
    confirm_pin: str = Field(min_length=4, max_length=6, pattern=r"^\d{4,6}$")


class PinVerifyRequest(BaseModel):
    pin: str = Field(min_length=4, max_length=6, pattern=r"^\d{4,6}$")


class ChangePinRequest(BaseModel):
    current_pin: str = Field(min_length=4, max_length=6, pattern=r"^\d{4,6}$")
    new_pin: str = Field(min_length=4, max_length=6, pattern=r"^\d{4,6}$")
    confirm_new_pin: str = Field(min_length=4, max_length=6, pattern=r"^\d{4,6}$")


class ResetPinRequest(BaseModel):
    recovery_key: str = Field(min_length=10, max_length=64)
    new_pin: str = Field(min_length=4, max_length=6, pattern=r"^\d{4,6}$")
    confirm_new_pin: str = Field(min_length=4, max_length=6, pattern=r"^\d{4,6}$")


class AuthStatusResponse(BaseModel):
    pin_configured: bool
    is_locked: bool
    lockout_remaining_seconds: int = 0
    session_active: bool = False


class AuthTokenResponse(BaseModel):
    success: bool
    token: str
    expires_in_seconds: int = 900
    recovery_key: str | None = None


class LogoutResponse(BaseModel):
    success: bool
    message: str = "Logged out successfully."


# ------------------------------------------------------------------------------
# Settings & Configuration Models
# ------------------------------------------------------------------------------

class CategorySettings(BaseModel):
    adult_sexual: bool = True
    violence_gore: bool = True
    self_harm: bool = True               # Permanent locked
    hate_speech: bool = True
    illegal_acts_weapons_drugs: bool = True  # Permanent locked
    cyberbullying: bool = True
    other_inappropriate: bool = True


class ParentalSettingsUpdate(BaseModel):
    strictness_profile: Literal["strict_elementary", "curriculum_standard", "custom"] = "curriculum_standard"
    categories: CategorySettings = Field(default_factory=CategorySettings)
    allow_ncert_biology_reproduction: bool = True
    custom_blocked_keywords: list[str] = Field(default_factory=list)
    custom_blocked_topics: list[str] = Field(default_factory=list)
    session_timeout_minutes: int = Field(default=15, ge=1, le=1440)


class SettingsResponse(BaseModel):
    strictness_profile: str
    categories: dict[str, bool]
    allow_ncert_biology_reproduction: bool
    custom_blocked_keywords: list[str]
    custom_blocked_topics: list[str]
    session_timeout_minutes: int
    updated_at: str | None = None


# ------------------------------------------------------------------------------
# Student Chat History Models
# ------------------------------------------------------------------------------

class ChatTurnRecord(BaseModel):
    turn_id: str
    session_id: str | None = None
    timestamp: str
    student_grade: int
    subject: str
    chapter: int | None = None
    language: str = "English"
    question: str
    answer: str
    sources: list[dict[str, Any]] = Field(default_factory=list)
    pure_llm: bool = False
    found: bool = True
    safety_status: str = "CLEAN"
    flagged: bool = False
    safety_category: str | None = None
    latency_s: float | None = None


class ChatHistoryResponse(BaseModel):
    total: int
    offset: int
    limit: int
    records: list[ChatTurnRecord]


# ------------------------------------------------------------------------------
# Flagged Queries & Review Models
# ------------------------------------------------------------------------------

class ReviewFlagRequest(BaseModel):
    action: Literal["acknowledged", "dismissed", "reviewed"] = "reviewed"
    notes: str = Field(default="", max_length=1000)


class ReviewFlagResponse(BaseModel):
    success: bool
    event_id: str
    parent_review_status: str
    reviewed_at: str
    parent_notes: str


class FlaggedAlertsResponse(BaseModel):
    total: int
    unreviewed_count: int
    events: list[dict[str, Any]]


# ------------------------------------------------------------------------------
# Overview Dashboard Models
# ------------------------------------------------------------------------------

class OverviewResponse(BaseModel):
    total_student_queries: int
    clean_queries: int
    flagged_queries: int
    unreviewed_alerts: int
    safety_compliance_rate_percent: float
    active_days_count: int
    top_studied_subjects: list[dict[str, Any]]
    flagged_category_breakdown: dict[str, int]
    current_strictness_profile: str
    last_student_activity: str | None = None
