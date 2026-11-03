"""
Unit and Integration Tests for Multi-Tenant School Organizations, Classes,
Sections, Role-Specific Invites, and Faculty Management.
"""

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.auth.jwt_handler import create_token_pair, decode_access_token
from app.auth.models import create_user
from app.db.engine import Base
from app.institution.routes import (
    accept_invite,
    assign_class_advisor,
    create_class,
    create_institution,
    create_invite,
    create_section,
    get_my_institution,
    join_institution,
    list_institution_faculty,
    update_my_subject_tags,
    verify_invite_token,
)
from app.institution.schemas import (
    ClassAdvisorAssignRequest,
    ClassCreateRequest,
    InstitutionCreateRequest,
    InstitutionJoinRequest,
    InviteAcceptRequest,
    InviteCreateRequest,
    LecturerProfileUpdateRequest,
    SectionCreateRequest,
)


@pytest.fixture(autouse=True)
def test_setup(tmp_path, monkeypatch):
    """Set up an isolated in-memory/temp database and users file for every test."""
    test_db_file = tmp_path / "test_ncert.db"
    test_db_url = f"sqlite:///{test_db_file}"
    engine = create_engine(test_db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    monkeypatch.setattr("app.db.engine.SessionLocal", TestingSessionLocal)
    monkeypatch.setattr("app.auth.models.USERS_FILE", tmp_path / "test_users.json")
    monkeypatch.setattr("app.auth.passwords.PBKDF2_ITERATIONS", 1000)

    db = TestingSessionLocal()
    yield db
    db.close()


def test_create_and_join_institution(test_setup):
    """Admin creates an institution; another user joins via demo verification code."""
    db = test_setup
    admin = create_user(username="principal_sharma", password="password123", role="org_admin")

    # 1. Create institution
    req = InstitutionCreateRequest(name="Delhi Public School", demo_verification_id="DPS-2026-DEMO")
    inst = create_institution(req, current_user=admin, db=db)

    assert inst.name == "Delhi Public School"
    assert inst.demo_verification_id == "DPS-2026-DEMO"
    inst_id = inst.id

    # 2. Duplicate demo_verification_id rejected
    with pytest.raises(HTTPException) as exc_info:
        create_institution(req, current_user=admin, db=db)
    assert exc_info.value.status_code == 400

    # 3. Another user joins via code
    user2 = create_user(username="teacher_verma", password="password123", role="lecturer")
    join_req = InstitutionJoinRequest(demo_verification_id="DPS-2026-DEMO")
    joined_inst = join_institution(join_req, current_user=user2, db=db)

    assert joined_inst.id == inst_id


def test_academic_hierarchy_classes_and_sections(test_setup):
    """Admin creates Class 10 and Section A under the institution."""
    db = test_setup
    admin = create_user(username="admin_roy", password="password123", role="org_admin")
    inst = create_institution(
        InstitutionCreateRequest(name="Kendriya Vidyalaya", demo_verification_id="KV-001"),
        current_user=admin,
        db=db,
    )
    admin["institution_id"] = inst.id

    # 1. Create Class 10
    cls_req = ClassCreateRequest(grade=10, display_name="Class 10")
    c = create_class(cls_req, admin=admin, db=db)
    assert c.grade == 10
    assert c.display_name == "Class 10"

    # 2. Duplicate class rejected
    with pytest.raises(HTTPException) as exc_info:
        create_class(cls_req, admin=admin, db=db)
    assert exc_info.value.status_code == 400

    # 3. Create Section A
    sec_req = SectionCreateRequest(section_name="A", room="Room 101")
    s = create_section(c.id, sec_req, admin=admin, db=db)
    assert s.section_name == "A"
    assert s.room == "Room 101"

    # 4. Duplicate section in same class rejected
    with pytest.raises(HTTPException) as exc_info:
        create_section(c.id, sec_req, admin=admin, db=db)
    assert exc_info.value.status_code == 400

    # 5. Verify institution summary
    summary = get_my_institution(current_user=admin, db=db)
    assert summary["institution"].name == "Kendriya Vidyalaya"
    assert len(summary["classes"]) == 1
    assert len(summary["classes"][0].sections) == 1


def test_role_specific_invite_flow(test_setup):
    """Admin generates Student and Lecturer invite links; users accept and are enrolled."""
    db = test_setup
    admin = create_user(username="headmaster", password="password123", role="org_admin")
    inst = create_institution(
        InstitutionCreateRequest(name="Modern School", demo_verification_id="MOD-2026"),
        current_user=admin,
        db=db,
    )
    admin["institution_id"] = inst.id

    c = create_class(ClassCreateRequest(grade=10), admin=admin, db=db)
    s = create_section(c.id, SectionCreateRequest(section_name="A"), admin=admin, db=db)

    # 1. Generate Student Invite Link
    s_inv_req = InviteCreateRequest(target_role="student", class_id=c.id, section_id=s.id, max_uses=30)
    student_inv = create_invite(s_inv_req, current_user=admin, db=db)
    assert student_inv.target_role == "student"
    assert student_inv.token is not None

    # 2. Verify Student Invite Token
    verify_res = verify_invite_token(student_inv.token, db=db)
    assert verify_res.valid is True
    assert verify_res.target_role == "student"
    assert verify_res.grade == 10
    assert verify_res.section_name == "A"

    # 3. Student accepts invite
    student = create_user(username="ananya", password="password123", role="student", grade=10)
    accept_res = accept_invite(InviteAcceptRequest(invite_token=student_inv.token), current_user=student, db=db)

    assert accept_res["success"] is True
    assert accept_res["user"]["institution_id"] == inst.id
    assert accept_res["user"]["section_id"] == s.id

    claims = decode_access_token(accept_res["tokens"]["access_token"])
    assert claims["institution_id"] == inst.id
    assert claims["section_id"] == s.id
    assert claims["role"] == "student"

    # 4. Generate Lecturer Invite Link
    l_inv_req = InviteCreateRequest(target_role="lecturer")
    lecturer_inv = create_invite(l_inv_req, current_user=admin, db=db)
    assert lecturer_inv.target_role == "lecturer"

    # 5. Teacher accepts lecturer invite
    teacher = create_user(username="prof_das", password="password123", role="student", grade=10)
    t_accept = accept_invite(InviteAcceptRequest(invite_token=lecturer_inv.token), current_user=teacher, db=db)

    assert t_accept["user"]["role"] == "lecturer"
    t_claims = decode_access_token(t_accept["tokens"]["access_token"])
    assert t_claims["role"] == "lecturer"


def test_lecturer_subject_tags_and_class_advisor(test_setup):
    """Lecturer updates subjects and Admin assigns them as Class Advisor for Section A."""
    db = test_setup
    admin = create_user(username="dean", password="password123", role="org_admin")
    inst = create_institution(
        InstitutionCreateRequest(name="St. Xavier's", demo_verification_id="STX-999"),
        current_user=admin,
        db=db,
    )
    admin["institution_id"] = inst.id

    c = create_class(ClassCreateRequest(grade=10), admin=admin, db=db)
    s = create_section(c.id, SectionCreateRequest(section_name="A"), admin=admin, db=db)

    # Create lecturer
    lecturer = create_user(
        username="mrs_sen",
        password="password123",
        role="lecturer",
        institution_id=inst.id,
    )

    # 1. Lecturer updates subject tags
    tag_res = update_my_subject_tags(
        LecturerProfileUpdateRequest(subject_tags=["Science", "Biology"]),
        current_user=lecturer,
        db=db,
    )
    assert tag_res["subject_tags"] == ["Science", "Biology"]

    # 2. Admin assigns Mrs. Sen as Class Advisor of Section A
    adv_res = assign_class_advisor(
        s.id,
        ClassAdvisorAssignRequest(advisor_user_id=lecturer["id"]),
        admin=admin,
        db=db,
    )
    assert adv_res.class_advisor_id == lecturer["id"]
    assert "mrs_sen" in adv_res.class_advisor_name

    # 3. Verify in faculty list
    faculty_list = list_institution_faculty(current_user=admin, db=db)
    sen = next((f for f in faculty_list if f.username == "mrs_sen"), None)
    assert sen is not None
    assert sen.subject_tags == ["Science", "Biology"]
    assert len(sen.advised_sections) == 1
    assert sen.advised_sections[0]["section_name"] == "A"


def test_institution_extended_academic_structure(test_setup):
    """Admin creates institution with complete school metadata & academic structure."""
    db = test_setup
    admin = create_user(username="headmaster_singh", password="password123", role="org_admin")
    req = InstitutionCreateRequest(
        name="St. Xavier's High School",
        school_code="STX-DELHI-01",
        location="New Delhi, India",
        academic_year="2026-2027",
        website="https://stxaviers.edu.in",
        affiliation_number="CBSE/AFF/2026/77890",
        medium_of_instruction="English",
        education_levels=["Primary", "Middle", "Secondary", "Higher Secondary"],
        available_classes="LKG–Grade 12",
    )
    inst = create_institution(req, current_user=admin, db=db)
    assert inst.name == "St. Xavier's High School"
    assert inst.school_code == "STX-DELHI-01"
    assert inst.location == "New Delhi, India"
    assert inst.academic_year == "2026-2027"
    assert inst.education_levels == ["Primary", "Middle", "Secondary", "Higher Secondary"]

    # Faculty registration check
    lect = create_user(
        username="prof_raman",
        password="password123",
        role="lecturer",
        subject_tags=["Science", "Physics"],
    )
    assert lect["role"] == "lecturer"
    assert "Physics" in lect["subject_tags"]
