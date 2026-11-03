"""
Business Logic Service for Institutions, Academic Hierarchy, Invites, and RBAC.
"""

import json
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.auth.jwt_handler import create_token_pair
from app.auth.models import _write_users, _read_users, _users_lock
from app.db.models import (
    Classroom,
    Institution,
    InviteLink,
    Section,
    User as SqlUser,
    generate_uuid,
)
from app.institution.schemas import (
    ClassAdvisorAssignRequest,
    ClassCreateRequest,
    ClassResponse,
    FacultyMemberResponse,
    InstitutionCreateRequest,
    InstitutionJoinRequest,
    InstitutionResponse,
    InviteCreateRequest,
    InviteResponse,
    InviteVerifyResponse,
    LecturerProfileUpdateRequest,
    SectionCreateRequest,
    SectionResponse,
    StudentRosterItem,
)


class InstitutionService:

    @staticmethod
    def _sync_user_to_file(user_id: str, updates: dict):
        """Update user record in storage/users.json atomically."""
        with _users_lock:
            users = _read_users()
            for u in users:
                if u.get("id") == user_id:
                    u.update(updates)
                    u["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
                    break
            _write_users(users)

    @classmethod
    def _to_institution_response(cls, inst: Institution) -> InstitutionResponse:
        levels = None
        if inst.education_levels:
            try:
                levels = json.loads(inst.education_levels)
            except Exception:
                levels = None

        return InstitutionResponse(
            id=inst.id,
            name=inst.name,
            school_code=inst.school_code or inst.demo_verification_id,
            demo_verification_id=inst.demo_verification_id,
            location=inst.location,
            academic_year=inst.academic_year,
            website=inst.website,
            affiliation_number=inst.affiliation_number,
            medium_of_instruction=inst.medium_of_instruction,
            education_levels=levels,
            available_classes=inst.available_classes,
            is_active=inst.is_active,
            created_at=inst.created_at,
        )

    # ── Institution Lifecycle ──

    @classmethod
    def create_institution(
        cls, db: Session, current_user: dict, req: InstitutionCreateRequest
    ) -> InstitutionResponse:
        """Create a new institution and designate the creator as org_admin."""
        code = (req.school_code or req.demo_verification_id or "").strip()
        if not code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="School Code / ID is required to identify the school.",
            )

        existing = db.query(Institution).filter(
            or_(
                Institution.school_code == code,
                Institution.demo_verification_id == code,
            )
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"School Code / ID '{code}' is already registered.",
            )

        levels_json = json.dumps(req.education_levels) if req.education_levels else None

        inst = Institution(
            id=generate_uuid("inst"),
            name=req.name.strip(),
            school_code=code,
            demo_verification_id=code,
            location=(req.location or "").strip() or None,
            academic_year=(req.academic_year or "2026-2027").strip(),
            website=(req.website or "").strip() or None,
            affiliation_number=(req.affiliation_number or "").strip() or None,
            medium_of_instruction=(req.medium_of_instruction or "English").strip(),
            education_levels=levels_json,
            available_classes=(req.available_classes or "LKG–Grade 12").strip(),
            is_active=True,
        )
        db.add(inst)
        db.flush()

        # Update creator in SQLite
        sql_u = db.query(SqlUser).filter(SqlUser.id == current_user["id"]).first()
        if not sql_u:
            sql_u = SqlUser(
                id=current_user["id"],
                username=current_user["username"],
                password_salt="",
                password_hash="",
                role="org_admin",
                institution_id=inst.id,
            )
            db.add(sql_u)
        else:
            sql_u.role = "org_admin"
            sql_u.institution_id = inst.id

        db.commit()
        db.refresh(inst)

        cls._sync_user_to_file(
            current_user["id"],
            {"role": "org_admin", "institution_id": inst.id, "institution_name": inst.name},
        )

        return cls._to_institution_response(inst)

    @classmethod
    def join_institution(
        cls, db: Session, current_user: dict, req: InstitutionJoinRequest
    ) -> InstitutionResponse:
        """Join an institution via its school code / ID or verification code."""
        code = (req.school_code or req.demo_verification_id or "").strip()
        if not code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Please enter a School Code or verification code.",
            )

        inst = db.query(Institution).filter(
            or_(
                Institution.school_code == code,
                Institution.demo_verification_id == code,
            ),
            Institution.is_active == True,
        ).first()
        if not inst:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Institution with code '{code}' not found.",
            )

        sql_u = db.query(SqlUser).filter(SqlUser.id == current_user["id"]).first()
        if sql_u:
            sql_u.institution_id = inst.id
            db.commit()

        cls._sync_user_to_file(
            current_user["id"],
            {"institution_id": inst.id, "institution_name": inst.name},
        )

        return cls._to_institution_response(inst)

    @classmethod
    def get_institution_summary(cls, db: Session, institution_id: str) -> dict:
        """Fetch summary of classes, sections, and faculty for the given institution."""
        inst = db.query(Institution).filter(Institution.id == institution_id).first()
        if not inst:
            raise HTTPException(status_code=404, detail="Institution not found.")

        classes = db.query(Classroom).filter(Classroom.institution_id == institution_id).order_by(Classroom.grade).all()
        class_responses = []

        for c in classes:
            sections = db.query(Section).filter(Section.class_id == c.id).order_by(Section.section_name).all()
            sec_responses = []
            for s in sections:
                advisor_name = s.class_advisor.full_name or s.class_advisor.username if s.class_advisor else None
                student_count = db.query(SqlUser).filter(SqlUser.section_id == s.id).count()
                sec_responses.append(
                    SectionResponse(
                        id=s.id,
                        class_id=s.class_id,
                        section_name=s.section_name,
                        room=s.room,
                        class_advisor_id=s.class_advisor_id,
                        class_advisor_name=advisor_name,
                        student_count=student_count,
                    )
                )

            class_responses.append(
                ClassResponse(
                    id=c.id,
                    institution_id=c.institution_id,
                    grade=c.grade,
                    display_name=c.display_name,
                    sections=sec_responses,
                )
            )

        total_students = db.query(SqlUser).filter(
            SqlUser.institution_id == institution_id, SqlUser.role == "student"
        ).count()
        total_faculty = db.query(SqlUser).filter(
            SqlUser.institution_id == institution_id, SqlUser.role.in_(["org_admin", "lecturer"])
        ).count()

        return {
            "institution": cls._to_institution_response(inst),
            "total_students": total_students,
            "total_faculty": total_faculty,
            "classes": class_responses,
        }

    # ── Classes & Sections Management ──

    @staticmethod
    def create_class(
        db: Session, institution_id: str, req: ClassCreateRequest
    ) -> ClassResponse:
        """Create a new class (grade level) under the institution."""
        existing = db.query(Classroom).filter(
            Classroom.institution_id == institution_id,
            Classroom.grade == req.grade,
        ).first()
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Class {req.grade} is already created for this institution.",
            )

        c = Classroom(
            id=generate_uuid("cls"),
            institution_id=institution_id,
            grade=req.grade,
            display_name=(req.display_name or f"Class {req.grade}").strip(),
        )
        db.add(c)
        db.commit()
        db.refresh(c)

        return ClassResponse(
            id=c.id,
            institution_id=c.institution_id,
            grade=c.grade,
            display_name=c.display_name,
            sections=[],
        )

    @staticmethod
    def create_section(
        db: Session, institution_id: str, class_id: str, req: SectionCreateRequest
    ) -> SectionResponse:
        """Create a section (e.g. 'A') under the designated class."""
        classroom = db.query(Classroom).filter(
            Classroom.id == class_id,
            Classroom.institution_id == institution_id,
        ).first()
        if not classroom:
            raise HTTPException(status_code=404, detail="Class not found under this institution.")

        existing = db.query(Section).filter(
            Section.class_id == class_id,
            Section.section_name == req.section_name.strip().upper(),
        ).first()
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Section '{req.section_name.strip().upper()}' already exists in {classroom.display_name}.",
            )

        s = Section(
            id=generate_uuid("sec"),
            class_id=class_id,
            section_name=req.section_name.strip().upper(),
            room=req.room.strip() if req.room else None,
        )
        db.add(s)
        db.commit()
        db.refresh(s)

        return SectionResponse(
            id=s.id,
            class_id=s.class_id,
            section_name=s.section_name,
            room=s.room,
            class_advisor_id=None,
            class_advisor_name=None,
            student_count=0,
        )

    # ── Role-Specific Invites ──

    @staticmethod
    def create_invite(
        db: Session,
        institution_id: str,
        current_user: dict,
        req: InviteCreateRequest,
    ) -> InviteResponse:
        """Generate a role-specific invite link (Lecturer or Student)."""
        inst = db.query(Institution).filter(Institution.id == institution_id).first()
        if not inst:
            raise HTTPException(status_code=404, detail="Institution not found.")

        classroom = None
        section = None

        if req.target_role == "student":
            if not req.class_id or not req.section_id:
                raise HTTPException(
                    status_code=400,
                    detail="Student invites require selecting both a Class and a Section.",
                )
            classroom = db.query(Classroom).filter(
                Classroom.id == req.class_id, Classroom.institution_id == institution_id
            ).first()
            if not classroom:
                raise HTTPException(status_code=404, detail="Class not found.")

            section = db.query(Section).filter(
                Section.id == req.section_id, Section.class_id == req.class_id
            ).first()
            if not section:
                raise HTTPException(status_code=404, detail="Section not found.")

        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(days=req.expires_days)

        invite = InviteLink(
            id=generate_uuid("inv"),
            token=token,
            institution_id=institution_id,
            target_role=req.target_role,
            class_id=req.class_id,
            section_id=req.section_id,
            max_uses=req.max_uses,
            uses_count=0,
            expires_at=expires_at,
            created_by=current_user.get("id"),
            is_revoked=False,
        )
        db.add(invite)
        db.commit()
        db.refresh(invite)

        return InviteResponse(
            id=invite.id,
            token=invite.token,
            invite_url=f"/#join?invite={invite.token}",
            target_role=invite.target_role,
            institution_id=inst.id,
            institution_name=inst.name,
            class_id=classroom.id if classroom else None,
            class_display_name=classroom.display_name if classroom else None,
            section_id=section.id if section else None,
            section_name=section.section_name if section else None,
            max_uses=invite.max_uses,
            uses_count=invite.uses_count,
            expires_at=invite.expires_at,
        )

    @staticmethod
    def verify_invite(db: Session, token: str) -> InviteVerifyResponse:
        """Inspect and validate an invite token without consuming it."""
        invite = db.query(InviteLink).filter(InviteLink.token == token.strip()).first()
        if not invite:
            raise HTTPException(status_code=404, detail="Invalid invite link.")

        if invite.is_revoked:
            raise HTTPException(status_code=400, detail="This invite link has been revoked.")

        now = datetime.now(timezone.utc)
        exp = invite.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)

        if now > exp:
            raise HTTPException(status_code=400, detail="This invite link has expired.")

        if invite.uses_count >= invite.max_uses:
            raise HTTPException(status_code=400, detail="This invite link has reached its maximum uses.")

        inst = invite.institution
        classroom = invite.classroom
        section = invite.section

        return InviteVerifyResponse(
            valid=True,
            institution_id=inst.id,
            institution_name=inst.name,
            target_role=invite.target_role,
            grade=classroom.grade if classroom else None,
            class_display_name=classroom.display_name if classroom else None,
            section_name=section.section_name if section else None,
        )

    @classmethod
    def accept_invite(cls, db: Session, current_user: dict, token: str) -> dict:
        """Consume an invite link, enroll the user, and issue fresh JWT credentials."""
        invite = db.query(InviteLink).filter(InviteLink.token == token.strip()).first()
        if not invite:
            raise HTTPException(status_code=404, detail="Invalid invite token.")

        if invite.is_revoked:
            raise HTTPException(status_code=400, detail="This invite link has been revoked.")

        now = datetime.now(timezone.utc)
        exp = invite.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)

        if now > exp:
            raise HTTPException(status_code=400, detail="This invite link has expired.")

        if invite.uses_count >= invite.max_uses:
            raise HTTPException(status_code=400, detail="This invite link has reached its maximum enrollment capacity.")

        sql_u = db.query(SqlUser).filter(SqlUser.id == current_user["id"]).first()
        if not sql_u:
            sql_u = SqlUser(
                id=current_user["id"],
                username=current_user["username"],
                password_salt="",
                password_hash="",
            )
            db.add(sql_u)

        inst = invite.institution
        role = invite.target_role

        sql_u.institution_id = inst.id
        sql_u.role = role

        if role == "student":
            sql_u.class_id = invite.class_id
            sql_u.section_id = invite.section_id
            if invite.classroom:
                sql_u.grade = invite.classroom.grade
        elif role == "lecturer":
            # Lecturers have multi-grade access
            pass

        invite.uses_count += 1
        db.commit()

        # Update JSON file
        cls._sync_user_to_file(
            current_user["id"],
            {
                "institution_id": inst.id,
                "institution_name": inst.name,
                "role": role,
                "class_id": sql_u.class_id,
                "section_id": sql_u.section_id,
                "grade": sql_u.grade,
            },
        )

        tokens = create_token_pair(
            user_id=sql_u.id,
            username=sql_u.username,
            grade=sql_u.grade,
            role=sql_u.role,
            institution_id=inst.id,
            institution_name=inst.name,
            class_id=sql_u.class_id,
            section_id=sql_u.section_id,
            subject_tags=sql_u.subject_tags,
        )

        return {
            "success": True,
            "message": f"Successfully joined {inst.name} as a {role.capitalize()}!",
            "tokens": tokens,
            "user": {
                "id": sql_u.id,
                "username": sql_u.username,
                "role": sql_u.role,
                "grade": sql_u.grade,
                "institution_id": inst.id,
                "institution_name": inst.name,
                "class_id": sql_u.class_id,
                "section_id": sql_u.section_id,
                "subject_tags": sql_u.subject_tags,
            },
        }

    # ── Faculty & Class Advisor Designation ──

    @staticmethod
    def assign_class_advisor(
        db: Session,
        institution_id: str,
        section_id: str,
        req: ClassAdvisorAssignRequest,
    ) -> SectionResponse:
        """Assign or unassign a faculty member as the Class Advisor for a section."""
        section = db.query(Section).join(Classroom).filter(
            Section.id == section_id,
            Classroom.institution_id == institution_id,
        ).first()
        if not section:
            raise HTTPException(status_code=404, detail="Section not found in this institution.")

        if req.advisor_user_id:
            advisor = db.query(SqlUser).filter(
                SqlUser.id == req.advisor_user_id,
                SqlUser.institution_id == institution_id,
                SqlUser.role.in_(["lecturer", "org_admin"]),
            ).first()
            if not advisor:
                raise HTTPException(
                    status_code=400,
                    detail="Selected user is not a faculty member of this institution.",
                )
            section.class_advisor_id = advisor.id
        else:
            section.class_advisor_id = None

        db.commit()
        db.refresh(section)

        advisor_name = section.class_advisor.full_name or section.class_advisor.username if section.class_advisor else None
        student_count = db.query(SqlUser).filter(SqlUser.section_id == section.id).count()

        return SectionResponse(
            id=section.id,
            class_id=section.class_id,
            section_name=section.section_name,
            room=section.room,
            class_advisor_id=section.class_advisor_id,
            class_advisor_name=advisor_name,
            student_count=student_count,
        )

    @classmethod
    def update_lecturer_subjects(
        cls, db: Session, current_user: dict, req: LecturerProfileUpdateRequest
    ) -> dict:
        """Update subject tags for a lecturer (e.g. ['Science', 'Mathematics'])."""
        sql_u = db.query(SqlUser).filter(SqlUser.id == current_user["id"]).first()
        if not sql_u:
            raise HTTPException(status_code=404, detail="User not found.")

        cleaned_tags = [t.strip() for t in req.subject_tags if t.strip()]
        sql_u.subject_tags = cleaned_tags
        db.commit()

        cls._sync_user_to_file(current_user["id"], {"subject_tags": cleaned_tags})

        return {"success": True, "subject_tags": cleaned_tags}

    @staticmethod
    def list_faculty(db: Session, institution_id: str) -> list[FacultyMemberResponse]:
        """List all faculty members (Admins and Lecturers) in the institution."""
        faculty = db.query(SqlUser).filter(
            SqlUser.institution_id == institution_id,
            SqlUser.role.in_(["org_admin", "lecturer"]),
        ).all()

        responses = []
        for f in faculty:
            # Check which sections this faculty member advises
            advised = db.query(Section).join(Classroom).filter(
                Section.class_advisor_id == f.id
            ).all()

            advised_sections = [
                {
                    "section_id": s.id,
                    "class_name": s.classroom.display_name,
                    "section_name": s.section_name,
                }
                for s in advised
            ]

            responses.append(
                FacultyMemberResponse(
                    id=f.id,
                    username=f.username,
                    full_name=f.full_name,
                    role=f.role,
                    subject_tags=f.subject_tags,
                    advised_sections=advised_sections,
                )
            )
        return responses

    @staticmethod
    def list_students(
        db: Session, institution_id: str, class_id: str | None = None, section_id: str | None = None
    ) -> list[StudentRosterItem]:
        """List enrolled students in the institution."""
        query = db.query(SqlUser).filter(
            SqlUser.institution_id == institution_id,
            SqlUser.role == "student",
        )
        if class_id:
            query = query.filter(SqlUser.class_id == class_id)
        if section_id:
            query = query.filter(SqlUser.section_id == section_id)

        students = query.order_by(SqlUser.username).all()
        roster = []
        for s in students:
            sec_name = s.section.section_name if s.section else None
            cls_name = s.section.classroom.display_name if s.section and s.section.classroom else None
            roster.append(
                StudentRosterItem(
                    id=s.id,
                    username=s.username,
                    full_name=s.full_name,
                    grade=s.grade,
                    class_name=cls_name,
                    section_name=sec_name,
                    created_at=s.created_at,
                )
            )
        return roster

