"""
SQLAlchemy Declarative Models for Multi-Tenant School Organizations, Classes, Sections, Users, and Invites.
"""

import json
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from app.db.engine import Base


def generate_uuid(prefix: str = "") -> str:
    """Generate a clean URL-safe prefixed identifier."""
    token = uuid.uuid4().hex[:12]
    return f"{prefix}_{token}" if prefix else token


class Institution(Base):
    __tablename__ = "institutions"

    id = Column(String(32), primary_key=True, default=lambda: generate_uuid("inst"))
    name = Column(String(150), nullable=False, index=True)
    school_code = Column(String(64), nullable=True, unique=True, index=True)
    demo_verification_id = Column(String(64), nullable=True, index=True)
    location = Column(String(200), nullable=True)
    academic_year = Column(String(32), nullable=True, default="2026-2027")
    website = Column(String(255), nullable=True)
    affiliation_number = Column(String(100), nullable=True)
    medium_of_instruction = Column(String(64), nullable=True, default="English")
    education_levels = Column(Text, nullable=True)  # JSON-serialized list
    available_classes = Column(String(100), nullable=True, default="LKG–Grade 12")
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    classes = relationship("Classroom", back_populates="institution", cascade="all, delete-orphan")
    users = relationship("User", back_populates="institution", foreign_keys="User.institution_id")
    invite_links = relationship("InviteLink", back_populates="institution", cascade="all, delete-orphan")


class Classroom(Base):
    __tablename__ = "classes"

    id = Column(String(32), primary_key=True, default=lambda: generate_uuid("cls"))
    institution_id = Column(
        String(32), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    grade = Column(Integer, nullable=False)  # 1 to 12
    display_name = Column(String(60), nullable=False)  # e.g. "Class 10"
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        UniqueConstraint("institution_id", "grade", name="uq_institution_grade"),
    )

    institution = relationship("Institution", back_populates="classes")
    sections = relationship("Section", back_populates="classroom", cascade="all, delete-orphan")


class Section(Base):
    __tablename__ = "sections"

    id = Column(String(32), primary_key=True, default=lambda: generate_uuid("sec"))
    class_id = Column(
        String(32), ForeignKey("classes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    section_name = Column(String(20), nullable=False)  # e.g. "A", "B", "Rose"
    room = Column(String(50), nullable=True)
    class_advisor_id = Column(String(32), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        UniqueConstraint("class_id", "section_name", name="uq_class_section"),
    )

    classroom = relationship("Classroom", back_populates="sections")
    class_advisor = relationship("User", foreign_keys=[class_advisor_id], post_update=True)
    students = relationship("User", foreign_keys="User.section_id", back_populates="section")


class User(Base):
    __tablename__ = "users"

    id = Column(String(32), primary_key=True, default=lambda: generate_uuid("usr"))
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_salt = Column(String(64), nullable=False)
    password_hash = Column(String(128), nullable=False)
    full_name = Column(String(100), nullable=True)
    role = Column(String(20), default="student", nullable=False)  # "org_admin", "lecturer", "student"
    
    # Institution context (nullable for self-study students and independent users)
    institution_id = Column(
        String(32), ForeignKey("institutions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    class_id = Column(String(32), ForeignKey("classes.id", ondelete="SET NULL"), nullable=True)
    section_id = Column(String(32), ForeignKey("sections.id", ondelete="SET NULL"), nullable=True)
    grade = Column(Integer, nullable=True)  # Mandatory for students; optional for teachers/admins
    
    # Lecturer-specific metadata stored as JSON string (e.g. '["Science", "Mathematics"]')
    _subject_tags = Column("subject_tags", Text, default="[]", nullable=False)
    
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    institution = relationship("Institution", back_populates="users", foreign_keys=[institution_id])
    section = relationship("Section", back_populates="students", foreign_keys=[section_id])

    @property
    def subject_tags(self) -> list[str]:
        if not self._subject_tags:
            return []
        try:
            return json.loads(self._subject_tags)
        except Exception:
            return []

    @subject_tags.setter
    def subject_tags(self, tags: list[str]) -> None:
        self._subject_tags = json.dumps(tags if isinstance(tags, list) else [])


class InviteLink(Base):
    __tablename__ = "invite_links"

    id = Column(String(32), primary_key=True, default=lambda: generate_uuid("inv"))
    token = Column(String(64), unique=True, nullable=False, index=True)
    institution_id = Column(
        String(32), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_role = Column(String(20), nullable=False)  # "lecturer" or "student"
    class_id = Column(String(32), ForeignKey("classes.id", ondelete="CASCADE"), nullable=True)
    section_id = Column(String(32), ForeignKey("sections.id", ondelete="CASCADE"), nullable=True)
    max_uses = Column(Integer, default=50, nullable=False)
    uses_count = Column(Integer, default=0, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_by = Column(String(32), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    is_revoked = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    institution = relationship("Institution", back_populates="invite_links")
    classroom = relationship("Classroom")
    section = relationship("Section")
