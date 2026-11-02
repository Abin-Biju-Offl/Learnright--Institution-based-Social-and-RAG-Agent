"""
User model and persistent storage supporting SQLite with backward-compatible JSON file synchronization.
"""

import json
import logging
import os
import secrets
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.auth.passwords import hash_password, verify_password
from app.config import settings

log = logging.getLogger(__name__)

USERS_FILE: Path = settings.storage_dir / "users.json"
_users_lock = threading.Lock()


def _read_users() -> list[dict[str, Any]]:
    """Read users from disk. Returns [] if the file doesn't exist yet."""
    if not USERS_FILE.exists():
        return []
    try:
        return json.loads(USERS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        log.warning("Could not read %s: %s", USERS_FILE, exc)
        return []


def _write_users(users: list[dict[str, Any]]) -> None:
    """Atomically write the users list to disk."""
    USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = USERS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(users, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(str(tmp), str(USERS_FILE))


def _sync_to_sqlite(user_dict: dict[str, Any]) -> None:
    """Non-blocking sync of user record to SQLite database if engine is available."""
    try:
        from app.db.engine import SessionLocal
        from app.db.models import User as SqlUser

        db = SessionLocal()
        try:
            sql_user = db.query(SqlUser).filter(SqlUser.username == user_dict["username"]).first()
            if not sql_user:
                sql_user = SqlUser(
                    id=user_dict["id"],
                    username=user_dict["username"],
                    password_salt=user_dict.get("password_salt", ""),
                    password_hash=user_dict.get("password_hash", ""),
                    full_name=user_dict.get("full_name"),
                    role=user_dict.get("role", "student"),
                    grade=user_dict.get("grade"),
                    institution_id=user_dict.get("institution_id"),
                    class_id=user_dict.get("class_id"),
                    section_id=user_dict.get("section_id"),
                    is_active=user_dict.get("is_active", True),
                )
                if user_dict.get("subject_tags"):
                    sql_user.subject_tags = user_dict["subject_tags"]
                db.add(sql_user)
            else:
                sql_user.password_salt = user_dict.get("password_salt", sql_user.password_salt)
                sql_user.password_hash = user_dict.get("password_hash", sql_user.password_hash)
                sql_user.full_name = user_dict.get("full_name", sql_user.full_name)
                sql_user.role = user_dict.get("role", sql_user.role)
                sql_user.grade = user_dict.get("grade", sql_user.grade)
                sql_user.institution_id = user_dict.get("institution_id", sql_user.institution_id)
                sql_user.class_id = user_dict.get("class_id", sql_user.class_id)
                sql_user.section_id = user_dict.get("section_id", sql_user.section_id)
                if "subject_tags" in user_dict:
                    sql_user.subject_tags = user_dict["subject_tags"]
                sql_user.is_active = user_dict.get("is_active", sql_user.is_active)
            db.commit()
        finally:
            db.close()
    except Exception as e:
        log.debug("SQLite sync skipped: %s", e)


def create_user(
    username: str,
    password: str,
    grade: int | None = None,
    full_name: str | None = None,
    role: str = "student",
    institution_id: str | None = None,
    class_id: str | None = None,
    section_id: str | None = None,
    subject_tags: list[str] | None = None,
) -> dict[str, Any]:
    """
    Register a new user (Student, Org Admin, or Lecturer).
    """
    if role == "student":
        if grade is None or not (1 <= int(grade) <= 12):
            raise ValueError("Student grade must be between 1 and 12.")
    elif grade is not None and not (1 <= int(grade) <= 12):
        raise ValueError("Grade must be between 1 and 12.")

    with _users_lock:
        users = _read_users()
        if any(u["username"].lower() == username.strip().lower() for u in users):
            raise ValueError(f"Username '{username}' is already taken.")

        salt_hex, hash_hex = hash_password(password)
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")

        user = {
            "id": f"usr_{secrets.token_hex(4)}",
            "username": username.strip().lower(),
            "full_name": (full_name or "").strip() or None,
            "role": role,
            "grade": int(grade) if grade is not None else None,
            "institution_id": institution_id,
            "class_id": class_id,
            "section_id": section_id,
            "subject_tags": subject_tags or [],
            "password_salt": salt_hex,
            "password_hash": hash_hex,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }
        users.append(user)
        _write_users(users)

    _sync_to_sqlite(user)
    return _public_user(user)


def authenticate_user(username: str, password: str) -> dict[str, Any] | None:
    """Verify credentials. Returns public user dict on success, None on failure."""
    with _users_lock:
        users = _read_users()

    user = next((u for u in users if u["username"].lower() == username.strip().lower()), None)
    if user is None:
        return None
    if not user.get("is_active", True):
        return None
    if not verify_password(password, user["password_salt"], user["password_hash"]):
        return None

    # Merge fresh institutional details from SQLite if available
    try:
        from app.db.engine import SessionLocal
        from app.db.models import User as SqlUser, Institution as SqlInst

        db = SessionLocal()
        try:
            sql_u = db.query(SqlUser).filter(SqlUser.username == user["username"]).first()
            if sql_u:
                user["role"] = sql_u.role
                user["institution_id"] = sql_u.institution_id
                user["class_id"] = sql_u.class_id
                user["section_id"] = sql_u.section_id
                user["grade"] = sql_u.grade
                user["subject_tags"] = sql_u.subject_tags
                if sql_u.institution_id:
                    inst = db.query(SqlInst).filter(SqlInst.id == sql_u.institution_id).first()
                    if inst:
                        user["institution_name"] = inst.name
        finally:
            db.close()
    except Exception:
        pass

    return _public_user(user)


def get_user_by_id(user_id: str) -> dict[str, Any] | None:
    """Look up a user by ID. Returns None if not found or deactivated."""
    with _users_lock:
        users = _read_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if user is None or not user.get("is_active", True):
        return None

    try:
        from app.db.engine import SessionLocal
        from app.db.models import User as SqlUser, Institution as SqlInst

        db = SessionLocal()
        try:
            sql_u = db.query(SqlUser).filter(SqlUser.id == user_id).first()
            if sql_u:
                user["role"] = sql_u.role
                user["institution_id"] = sql_u.institution_id
                user["class_id"] = sql_u.class_id
                user["section_id"] = sql_u.section_id
                user["grade"] = sql_u.grade
                user["subject_tags"] = sql_u.subject_tags
                if sql_u.institution_id:
                    inst = db.query(SqlInst).filter(SqlInst.id == sql_u.institution_id).first()
                    if inst:
                        user["institution_name"] = inst.name
        finally:
            db.close()
    except Exception:
        pass

    return _public_user(user)


def get_user_by_username(username: str) -> dict[str, Any] | None:
    """Look up a user by username."""
    with _users_lock:
        users = _read_users()
    user = next((u for u in users if u["username"].lower() == username.strip().lower()), None)
    if user is None:
        return None
    return _public_user(user)


def list_users() -> list[dict[str, Any]]:
    """Return all users (public fields only)."""
    with _users_lock:
        users = _read_users()
    return [_public_user(u) for u in users]


def deactivate_user(user_id: str) -> bool:
    """Soft-delete: mark user as inactive."""
    with _users_lock:
        users = _read_users()
        user = next((u for u in users if u["id"] == user_id), None)
        if user is None:
            return False
        user["is_active"] = False
        user["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        _write_users(users)
    return True


def _public_user(user: dict[str, Any]) -> dict[str, Any]:
    """Strip sensitive fields before returning a user dict."""
    return {k: v for k, v in user.items() if k not in ("password_salt", "password_hash")}
