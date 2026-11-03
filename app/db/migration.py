"""
Startup Migration Helper from storage/users.json to SQLite database.
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.db.engine import SessionLocal, init_db
from app.db.models import Classroom, Institution, InviteLink, Section, User

logger = logging.getLogger("app.db.migration")
USERS_JSON_PATH = Path(__file__).resolve().parent.parent.parent / "storage" / "users.json"


def _add_column_if_not_exists(db: Session, table: str, column: str, col_type: str):
    """Safely apply SQLite ALTER TABLE column additions."""
    try:
        db.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))
        db.commit()
    except Exception:
        db.rollback()


def run_startup_migrations():
    """Ensure database schema is created and migrate any legacy JSON users."""
    init_db()

    # Dynamic migrations for SQLite institution columns
    db: Session = SessionLocal()
    try:
        _add_column_if_not_exists(db, "institutions", "school_code", "VARCHAR(64)")
        _add_column_if_not_exists(db, "institutions", "location", "VARCHAR(200)")
        _add_column_if_not_exists(db, "institutions", "academic_year", "VARCHAR(32)")
        _add_column_if_not_exists(db, "institutions", "website", "VARCHAR(255)")
        _add_column_if_not_exists(db, "institutions", "affiliation_number", "VARCHAR(100)")
        _add_column_if_not_exists(db, "institutions", "medium_of_instruction", "VARCHAR(64)")
        _add_column_if_not_exists(db, "institutions", "education_levels", "TEXT")
        _add_column_if_not_exists(db, "institutions", "available_classes", "VARCHAR(100)")
    finally:
        db.close()

    if not USERS_JSON_PATH.exists():
        return

    db = SessionLocal()
    try:
        with open(USERS_JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            return

        migrated_count = 0
        for item in data:
            username = item.get("username")
            if not username:
                continue

            existing = db.query(User).filter(User.username == username).first()
            if existing:
                continue

            created_at_val = item.get("created_at")
            if created_at_val:
                try:
                    dt = datetime.fromisoformat(created_at_val.replace("Z", "+00:00"))
                except Exception:
                    dt = datetime.now(timezone.utc)
            else:
                dt = datetime.now(timezone.utc)

            new_user = User(
                id=item.get("id") or f"usr_{username}",
                username=username,
                password_salt=item.get("password_salt", ""),
                password_hash=item.get("password_hash", ""),
                full_name=item.get("full_name"),
                role=item.get("role", "student"),
                grade=item.get("grade"),
                is_active=item.get("is_active", True),
                created_at=dt,
            )
            db.add(new_user)
            migrated_count += 1

        if migrated_count > 0:
            db.commit()
            logger.info(f"Successfully migrated {migrated_count} legacy user(s) into SQLite.")
    except Exception as e:
        logger.error(f"Error during legacy users migration: {e}")
        db.rollback()
    finally:
        db.close()

    # Seed demo institution with classes, sections, and users
    db = SessionLocal()
    try:
        seed_demo_institution(db)
    finally:
        db.close()


def seed_demo_institution(db: Session):
    """
    Creates a pre-configured demo institution ('Delhi Public School, R.K. Puram')
    with Class 10 & Class 5, sections A & B, pre-associated demo users
    (Principal, Lecturer, Student), and pre-generated invite links.
    """
    try:
        inst_id = "inst_demo_dps2026"
        inst = db.query(Institution).filter(
            (Institution.id == inst_id) | (Institution.school_code == "DPS-DELHI-01")
        ).first()

        if not inst:
            inst = Institution(
                id=inst_id,
                name="Delhi Public School, R.K. Puram",
                school_code="DPS-DELHI-01",
                demo_verification_id="DPS-2026-DEMO",
                location="R.K. Puram, New Delhi (CBSE Board)",
                academic_year="2026-2027",
                website="https://dpsdelhi.edu.in",
                affiliation_number="CBSE/AFF/2026/89410",
                medium_of_instruction="English",
                education_levels=json.dumps(["Primary", "Middle", "Secondary", "Higher Secondary"]),
                available_classes="LKG–Grade 12",
                is_active=True,
            )
            db.add(inst)
            db.flush()
            logger.info("Created demo institution: Delhi Public School, R.K. Puram (%s)", inst.id)

        # Classes
        c10 = db.query(Classroom).filter(Classroom.institution_id == inst.id, Classroom.grade == 10).first()
        if not c10:
            c10 = Classroom(
                id="cls_demo_c10",
                institution_id=inst.id,
                grade=10,
                display_name="Class 10",
            )
            db.add(c10)
            db.flush()

        c5 = db.query(Classroom).filter(Classroom.institution_id == inst.id, Classroom.grade == 5).first()
        if not c5:
            c5 = Classroom(
                id="cls_demo_c5",
                institution_id=inst.id,
                grade=5,
                display_name="Class 5",
            )
            db.add(c5)
            db.flush()

        # Sections
        s10a = db.query(Section).filter(Section.class_id == c10.id, Section.section_name == "A").first()
        if not s10a:
            s10a = Section(
                id="sec_demo_10a",
                class_id=c10.id,
                section_name="A",
                room="Room 204",
            )
            db.add(s10a)
            db.flush()

        s10b = db.query(Section).filter(Section.class_id == c10.id, Section.section_name == "B").first()
        if not s10b:
            s10b = Section(
                id="sec_demo_10b",
                class_id=c10.id,
                section_name="B",
                room="Room 205",
            )
            db.add(s10b)
            db.flush()

        s5a = db.query(Section).filter(Section.class_id == c5.id, Section.section_name == "A").first()
        if not s5a:
            s5a = Section(
                id="sec_demo_5a",
                class_id=c5.id,
                section_name="A",
                room="Room 102",
            )
            db.add(s5a)
            db.flush()

        # Link demo users if present
        principal = db.query(User).filter(User.username == "demo_principal").first()
        if principal:
            principal.institution_id = inst.id
            principal.role = "org_admin"

        lecturer = db.query(User).filter(User.username == "demo_lecturer").first()
        if lecturer:
            lecturer.institution_id = inst.id
            lecturer.role = "lecturer"
            lecturer.subject_tags = ["Science", "Physics"]
            s10a.class_advisor_id = lecturer.id

        student = db.query(User).filter(User.username == "demo_student").first()
        if student:
            student.institution_id = inst.id
            student.class_id = c10.id
            student.section_id = s10a.id
            student.grade = 10
            student.role = "student"

        # Invite links
        inv_student = db.query(InviteLink).filter(InviteLink.token == "inv_demo_student_10a").first()
        if not inv_student:
            inv_student = InviteLink(
                id="inv_demo_student_10a",
                token="inv_demo_student_10a",
                institution_id=inst.id,
                target_role="student",
                class_id=c10.id,
                section_id=s10a.id,
                max_uses=100,
                uses_count=1,
                expires_at=datetime.now(timezone.utc) + timedelta(days=365),
                is_revoked=False,
            )
            db.add(inv_student)

        inv_faculty = db.query(InviteLink).filter(InviteLink.token == "inv_demo_faculty").first()
        if not inv_faculty:
            inv_faculty = InviteLink(
                id="inv_demo_faculty",
                token="inv_demo_faculty",
                institution_id=inst.id,
                target_role="lecturer",
                class_id=None,
                section_id=None,
                max_uses=50,
                uses_count=1,
                expires_at=datetime.now(timezone.utc) + timedelta(days=365),
                is_revoked=False,
            )
            db.add(inv_faculty)

        db.commit()
        logger.info("Demo institution seeding complete.")

        # Also synchronize storage/users.json
        _sync_demo_users_json(inst.id, c10.id, s10a.id)

    except Exception as e:
        logger.error(f"Error seeding demo institution: {e}")
        db.rollback()


def _sync_demo_users_json(institution_id: str, class_id: str, section_id: str):
    """Keep storage/users.json aligned with demo institution attributes."""
    if not USERS_JSON_PATH.exists():
        return
    try:
        with open(USERS_JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            return

        updated = False
        for u in data:
            uname = u.get("username")
            if uname == "demo_principal":
                u["institution_id"] = institution_id
                u["role"] = "org_admin"
                updated = True
            elif uname == "demo_lecturer":
                u["institution_id"] = institution_id
                u["role"] = "lecturer"
                u["subject_tags"] = ["Science", "Physics"]
                updated = True
            elif uname == "demo_student":
                u["institution_id"] = institution_id
                u["class_id"] = class_id
                u["section_id"] = section_id
                u["grade"] = 10
                u["role"] = "student"
                updated = True

        if updated:
            with open(USERS_JSON_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info("Synchronized storage/users.json with demo institution links.")
    except Exception as e:
        logger.warning(f"Failed to sync demo users to users.json: {e}")

