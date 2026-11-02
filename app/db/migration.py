"""
Startup Migration Helper from storage/users.json to SQLite database.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy.orm import Session
from app.db.engine import SessionLocal, init_db
from app.db.models import User

logger = logging.getLogger("app.db.migration")
USERS_JSON_PATH = Path(__file__).resolve().parent.parent.parent / "storage" / "users.json"


def run_startup_migrations():
    """Ensure database schema is created and migrate any legacy JSON users."""
    init_db()
    
    if not USERS_JSON_PATH.exists():
        return

    db: Session = SessionLocal()
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
