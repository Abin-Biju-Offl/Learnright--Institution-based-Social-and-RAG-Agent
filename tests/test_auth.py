"""
Unit and integration tests for JWT Authentication and Class-based Authorization.
"""

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.main
from app.auth.dependencies import enforce_grade
from app.auth.jwt_handler import create_token_pair, decode_access_token, decode_refresh_token
from app.auth.models import USERS_FILE, authenticate_user, create_user, get_user_by_id
from app.auth.routes import DemoSwitchRequest, demo_switch, login, me, refresh, register
from app.auth.schemas import LoginRequest, RefreshRequest, RegisterRequest
from app.db.engine import Base
from app.main import subjects


@pytest.fixture(autouse=True)
def clean_users_file(tmp_path, monkeypatch):
    """Isolate users.json and SQLite database for every test."""
    test_db_file = tmp_path / "test_ncert_auth.db"
    test_db_url = f"sqlite:///{test_db_file}"
    engine = create_engine(test_db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    monkeypatch.setattr("app.db.engine.SessionLocal", TestingSessionLocal)
    test_users_file = tmp_path / "test_users.json"
    monkeypatch.setattr("app.auth.models.USERS_FILE", test_users_file)
    monkeypatch.setattr("app.auth.passwords.PBKDF2_ITERATIONS", 1000)
    yield


def test_student_registration():
    """Registering a student stores their grade and returns an access token with grade claim."""
    req = RegisterRequest(
        username="student_ten",
        password="securepassword123",
        grade=10,
        full_name="Student Ten",
    )
    res = register(req)

    assert res.user["username"] == "student_ten"
    assert res.user["grade"] == 10
    assert res.access_token is not None
    assert res.refresh_token is not None

    # Verify JWT payload
    payload = decode_access_token(res.access_token)
    assert payload["username"] == "student_ten"
    assert payload["grade"] == 10


def test_duplicate_registration_rejected():
    """Registering the same username twice must raise HTTP 400."""
    req = RegisterRequest(username="dupe_user", password="password123", grade=5)
    register(req)

    with pytest.raises(HTTPException) as exc_info:
        register(req)
    assert exc_info.value.status_code == 400
    assert "already taken" in str(exc_info.value.detail).lower()


def test_student_login():
    """Valid login succeeds with JWT, invalid login raises 401."""
    create_user(username="charlie", password="charlie_pass", grade=10)

    # Valid login
    res = login(LoginRequest(username="charlie", password="charlie_pass"))
    assert res.user["grade"] == 10
    assert "access_token" in res.model_dump()

    # Invalid login
    with pytest.raises(HTTPException) as exc_info:
        login(LoginRequest(username="charlie", password="wrong_pass"))
    assert exc_info.value.status_code == 401


def test_token_refresh():
    """Refresh token can be exchanged for a fresh access token."""
    user = create_user(username="refresher", password="pass123456", grade=10)
    tokens = create_token_pair(user_id=user["id"], username=user["username"], grade=10)

    res = refresh(RefreshRequest(refresh_token=tokens["refresh_token"]))
    assert res.access_token is not None
    assert res.user["grade"] == 10


def test_auth_me():
    """GET /api/auth/me returns the active student's profile."""
    user = create_user(username="bob", password="password123", grade=10, full_name="Bob Kumar")
    profile = me(student=user)
    assert profile.username == "bob"
    assert profile.grade == 10
    assert profile.full_name == "Bob Kumar"


def test_class_10_student_only_sees_class_10_subjects(monkeypatch):
    """
    Authorization requirement:
    Class 10 student can ONLY see Class 10 textbooks in /api/subjects.
    """
    class FakeRAG:
        def subjects(self):
            return [
                {"grade": 5, "subject": "Science", "book": "Looking Around"},
                {"grade": 5, "subject": "English", "book": "Marigold"},
                {"grade": 10, "subject": "Science", "book": "Science 10"},
                {"grade": 10, "subject": "English", "book": "First Flight"},
            ]

    monkeypatch.setattr(app.main, "get_rag", lambda: FakeRAG())

    # 1. Anonymous visitor sees all textbooks
    anon_view = subjects(user=None)
    assert len(anon_view) == 4

    # 2. Class 10 student sees ONLY Class 10 textbooks
    student_10 = {"id": "usr_10", "username": "student10", "grade": 10, "is_parent": False}
    class_10_view = subjects(user=student_10)
    assert len(class_10_view) == 2
    assert all(s["grade"] == 10 for s in class_10_view)
    assert not any(s["grade"] == 5 for s in class_10_view)

    # 3. Class 5 student sees ONLY Class 5 textbooks
    student_5 = {"id": "usr_5", "username": "student5", "grade": 5, "is_parent": False}
    class_5_view = subjects(user=student_5)
    assert len(class_5_view) == 2
    assert all(s["grade"] == 5 for s in class_5_view)
    assert not any(s["grade"] == 10 for s in class_5_view)

    # 4. Parent has oversight across all classes
    parent_user = {"id": "parent", "username": "parent", "grade": None, "is_parent": True}
    parent_view = subjects(user=parent_user)
    assert len(parent_view) == 4


def test_grade_enforcement_blocks_cross_class_access():
    """
    A Class 10 student attempting to query Class 5 textbooks is blocked with 403 Forbidden.
    """
    student_10 = {"username": "student10", "grade": 10, "is_parent": False}

    # Querying own class: OK
    enforce_grade(student_10, requested_grade=10)

    # Querying another class: 403 Forbidden
    with pytest.raises(HTTPException) as exc_info:
        enforce_grade(student_10, requested_grade=5)
    assert exc_info.value.status_code == 403
    assert "authorized for Class 10 textbooks only" in exc_info.value.detail
    assert "cannot access Class 5" in exc_info.value.detail


def test_demo_role_switch():
    """Demo switch must return valid signed tokens for admin, lecturer, and student."""
    # 1. Org admin switch
    res_admin = demo_switch(DemoSwitchRequest(role="org_admin"))
    assert res_admin.user["role"] == "org_admin"
    payload_admin = decode_access_token(res_admin.access_token)
    assert payload_admin["role"] == "org_admin"

    # 2. Lecturer switch
    res_lect = demo_switch(DemoSwitchRequest(role="lecturer"))
    assert res_lect.user["role"] == "lecturer"
    payload_lect = decode_access_token(res_lect.access_token)
    assert payload_lect["role"] == "lecturer"

    # 3. Student switch
    res_stud = demo_switch(DemoSwitchRequest(role="student", grade=10))
    assert res_stud.user["role"] == "student"
    payload_stud = decode_access_token(res_stud.access_token)
    assert payload_stud["role"] == "student"
    assert payload_stud["grade"] == 10
