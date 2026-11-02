"""
FastAPI dependencies for JWT authentication, institutional tenancy, and tiered RBAC authorization.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.jwt_handler import TokenError, decode_access_token
from app.auth.models import get_user_by_id
from app.parental.auth import validate_session

_bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> dict:
    """
    Dependency that extracts the Bearer token, decodes it, and returns the user dict.
    Supports:
      1. Institutional/Student Bearer JWT (contains user ID, role, grade, and institution context)
      2. Parental session token (e.g. tok_par_...) for guardian access
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a valid Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    # 1. Check if it's a valid parental session token
    if validate_session(token):
        return {
            "id": "parent",
            "username": "parent",
            "role": "parent",
            "is_parent": True,
            "grade": None,  # Parents have access across all grades
            "institution_id": None,
            "institution_name": None,
        }

    # 2. Check if it's a Bearer JWT
    try:
        payload = decode_access_token(token)
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = get_user_by_id(payload["sub"])
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found or deactivated.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Attach authoritative claims from verified JWT payload
    user["role"] = payload.get("role", user.get("role", "student"))
    user["grade"] = payload.get("grade", user.get("grade"))
    user["institution_id"] = payload.get("institution_id", user.get("institution_id"))
    user["institution_name"] = payload.get("institution_name", user.get("institution_name"))
    user["class_id"] = payload.get("class_id", user.get("class_id"))
    user["section_id"] = payload.get("section_id", user.get("section_id"))
    user["subject_tags"] = payload.get("subject_tags", user.get("subject_tags", []))
    user["is_parent"] = False
    return user


def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> dict | None:
    """
    Returns the authenticated user dict or None if no token was supplied.
    """
    if not credentials or not credentials.credentials:
        return None
    return get_current_user(credentials)


# Backwards compatibility aliases
get_current_student = get_current_user
get_optional_student = get_optional_user


# ──────────────────────────────────────────────────────────────────────────────
# Role Guards
# ──────────────────────────────────────────────────────────────────────────────

def require_org_admin(user: dict = Depends(get_current_user)) -> dict:
    """Ensure the user possesses the org_admin role."""
    if user.get("role") != "org_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: This action requires Organization Administrator privileges (Principal/Headmaster).",
        )
    return user


def require_lecturer_or_admin(user: dict = Depends(get_current_user)) -> dict:
    """Ensure the user is faculty (Lecturer) or an Organization Administrator."""
    if user.get("role") not in ("lecturer", "org_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: This action requires Faculty (Lecturer) or Administrator privileges.",
        )
    return user


def require_institution_member(user: dict = Depends(get_current_user)) -> dict:
    """Ensure the user is affiliated with an active institution."""
    if not user.get("institution_id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You are not enrolled in an institution. Please join or create an institution first.",
        )
    return user


# ──────────────────────────────────────────────────────────────────────────────
# Grade authorization: ensure student only accesses their own class
# ──────────────────────────────────────────────────────────────────────────────

def enforce_grade(user: dict | None, requested_grade: int) -> None:
    """
    Verify that the user is authorized to view or query textbooks for the requested grade.

    Rules:
      - None / unauthenticated: allowed (open self-study mode).
      - If user is a Parent (is_parent=True): full access across all grades.
      - If user is Org Admin or Lecturer: full faculty access across all grades.
      - If user is a Student with enrolled grade X: access is ONLY granted if requested_grade == X.
    """
    if user is None or not isinstance(user, dict):
        return

    # Guardian bypass
    if user.get("is_parent"):
        return

    user_role = user.get("role", "student")

    # Faculty & Administration bypass
    if user_role in ("org_admin", "lecturer"):
        return

    student_grade = user.get("grade")
    if student_grade is not None and int(student_grade) != int(requested_grade):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Access denied: You are authorized for Class {student_grade} textbooks only. "
                f"You cannot access Class {requested_grade} content."
            ),
        )
