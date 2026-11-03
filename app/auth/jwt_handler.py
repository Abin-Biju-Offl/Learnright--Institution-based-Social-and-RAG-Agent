"""
JWT token creation, verification, and refresh.

Uses PyJWT (lightweight, pure-Python, zero extra dependencies).
Issues two tokens per login:

    access_token  — short-lived (30 min default), carries the student's grade
    refresh_token — long-lived (7 days default), used to get a new access token

Both are HS256-signed JWTs with standard claims (sub, grade, exp, iat, jti, type).
"""

import secrets
from datetime import datetime, timedelta, timezone

import jwt  # PyJWT

from app.config import settings

ALGORITHM = "HS256"


def _secret() -> str:
    """Return the JWT signing secret, generating one if not configured."""
    secret = settings.jwt_secret
    if not secret:
        raise RuntimeError(
            "JWT_SECRET is not set. Add a strong random value to your .env file. "
            "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
        )
    return secret


# ──────────────────────────────────────────────────────────────────────────────
# Token creation
# ──────────────────────────────────────────────────────────────────────────────

def create_access_token(
    user_id: str,
    username: str,
    grade: int | None = None,
    role: str = "student",
    institution_id: str | None = None,
    institution_name: str | None = None,
    class_id: str | None = None,
    section_id: str | None = None,
    subject_tags: list[str] | None = None,
    expires_minutes: int | None = None,
) -> str:
    """
    Create a short-lived access token carrying identity, role, grade, and institutional claims.
    """
    lifetime = expires_minutes or settings.jwt_access_expire_minutes
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "grade": grade,
        "institution_id": institution_id,
        "institution_name": institution_name,
        "class_id": class_id,
        "section_id": section_id,
        "subject_tags": subject_tags or [],
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=lifetime),
        "jti": f"acc_{secrets.token_hex(8)}",
    }
    return jwt.encode(payload, _secret(), algorithm=ALGORITHM)


def create_refresh_token(
    user_id: str,
    expires_days: int | None = None,
) -> str:
    """
    Create a long-lived refresh token (contains only sub + type, no grade).
    """
    lifetime = expires_days or settings.jwt_refresh_expire_days
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "type": "refresh",
        "iat": now,
        "exp": now + timedelta(days=lifetime),
        "jti": f"ref_{secrets.token_hex(8)}",
    }
    return jwt.encode(payload, _secret(), algorithm=ALGORITHM)


def create_token_pair(
    user_id: str,
    username: str,
    grade: int | None = None,
    role: str = "student",
    institution_id: str | None = None,
    institution_name: str | None = None,
    class_id: str | None = None,
    section_id: str | None = None,
    subject_tags: list[str] | None = None,
) -> dict[str, str]:
    """Convenience: create both tokens at once with full institutional claims."""
    return {
        "access_token": create_access_token(
            user_id=user_id,
            username=username,
            grade=grade,
            role=role,
            institution_id=institution_id,
            institution_name=institution_name,
            class_id=class_id,
            section_id=section_id,
            subject_tags=subject_tags,
        ),
        "refresh_token": create_refresh_token(user_id),
    }


# ──────────────────────────────────────────────────────────────────────────────
# Token verification
# ──────────────────────────────────────────────────────────────────────────────

class TokenError(Exception):
    """Raised when a JWT is invalid, expired, or of the wrong type."""


def decode_access_token(token: str) -> dict:
    """
    Decode and validate an access token.

    Returns the full payload dict (with "sub", "username", "grade", "role", etc.).
    Raises TokenError on any problem.
    """
    if not token or not isinstance(token, str) or token.strip().lower() in ("null", "undefined", "none", ""):
        raise TokenError("Access token is missing or empty.")

    clean_token = token.strip()
    if clean_token.count(".") != 2:
        raise TokenError("Malformed access token: JWT must contain exactly 3 dot-separated segments.")

    try:
        payload = jwt.decode(clean_token, _secret(), algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise TokenError("Access token has expired. Please log in again or use your refresh token.")
    except jwt.InvalidTokenError as exc:
        raise TokenError(f"Invalid access token: {exc}")

    if payload.get("type") != "access":
        raise TokenError("Expected an access token, got a different token type.")
    if not payload.get("sub"):
        raise TokenError("Token is missing the user identifier (sub claim).")
    
    # Ensure role defaults to 'student' if absent for legacy tokens
    if not payload.get("role"):
        payload["role"] = "student"
        
    return payload


def decode_refresh_token(token: str) -> dict:
    """
    Decode and validate a refresh token.

    Returns the full payload dict.
    Raises TokenError on any problem.
    """
    try:
        payload = jwt.decode(token, _secret(), algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise TokenError("Refresh token has expired. Please log in again.")
    except jwt.InvalidTokenError as exc:
        raise TokenError(f"Invalid refresh token: {exc}")

    if payload.get("type") != "refresh":
        raise TokenError("Expected a refresh token, got a different token type.")
    if not payload.get("sub"):
        raise TokenError("Token is missing the user identifier (sub claim).")
    return payload
