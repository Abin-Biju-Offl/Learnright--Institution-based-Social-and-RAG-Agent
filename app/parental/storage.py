"""
Thread-safe atomic JSON & JSONL storage manager for Parental Controls.

Manages:
- storage/parental_config.json
- storage/student_chat_history.jsonl
- storage/safety_events.jsonl
"""

import copy
import json
import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import settings

log = logging.getLogger("app.parental.storage")

# Thread locks
parental_config_lock = threading.Lock()
chat_history_lock = threading.Lock()
safety_events_lock = threading.Lock()

DEFAULT_PARENTAL_CONFIG: dict[str, Any] = {
    "version": 1,
    "security": {
        "pin_configured": False,
        "pin_hash": None,
        "pin_salt": None,
        "recovery_key_hash": None,
        "recovery_key_salt": None,
        "failed_attempts": 0,
        "locked_until": None,
        "session_timeout_minutes": 15,
    },
    "filtering": {
        "strictness_profile": "curriculum_standard",
        "categories": {
            "adult_sexual": True,
            "violence_gore": True,
            "self_harm": True,
            "hate_speech": True,
            "illegal_acts_weapons_drugs": True,
            "cyberbullying": True,
            "other_inappropriate": True,
        },
        "allow_ncert_biology_reproduction": True,
        "custom_blocked_keywords": [],
        "custom_blocked_topics": [],
        "safe_search_level": "strict",
    },
    "notifications": {
        "show_sidebar_badge": True,
        "alert_on_critical_severity": True,
    },
    "updated_at": None,
}


def get_parental_config_path(override_path: Path | None = None) -> Path:
    if override_path is not None:
        return override_path
    return settings.storage_dir / "parental_config.json"


def get_student_chat_history_path(override_path: Path | None = None) -> Path:
    if override_path is not None:
        return override_path
    return settings.storage_dir / "student_chat_history.jsonl"


def get_safety_events_path(override_path: Path | None = None) -> Path:
    if override_path is not None:
        return override_path
    return settings.storage_dir / "safety_events.jsonl"


# ------------------------------------------------------------------------------
# Parental Config JSON Operations (Atomic)
# ------------------------------------------------------------------------------

def load_parental_config(override_path: Path | None = None) -> dict[str, Any]:
    """
    Load parental configuration JSON with thread safety.
    Returns a copy of DEFAULT_PARENTAL_CONFIG merged if file does not exist.
    """
    path = get_parental_config_path(override_path)
    with parental_config_lock:
        if not path.exists():
            return copy.deepcopy(DEFAULT_PARENTAL_CONFIG)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Deep merge defaults for any newly introduced keys
                merged = copy.deepcopy(DEFAULT_PARENTAL_CONFIG)
                for k, v in data.items():
                    if isinstance(v, dict) and k in merged and isinstance(merged[k], dict):
                        merged[k].update(v)
                    else:
                        merged[k] = v
                return merged
        except Exception as e:
            log.warning("Failed to parse parental config from %s: %s. Using defaults.", path, e)
            return copy.deepcopy(DEFAULT_PARENTAL_CONFIG)


def save_parental_config(config: dict[str, Any], override_path: Path | None = None) -> None:
    """
    Atomically save parental configuration to disk using a temporary file and os.replace.
    """
    path = get_parental_config_path(override_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")

    with parental_config_lock:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)


# ------------------------------------------------------------------------------
# Student Chat History JSONL Operations
# ------------------------------------------------------------------------------

def log_chat_turn(turn_record: dict[str, Any], override_path: Path | None = None) -> None:
    """
    Thread-safe append of a student conversation turn to student_chat_history.jsonl.
    """
    path = get_student_chat_history_path(override_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    line = json.dumps(turn_record, ensure_ascii=False) + "\n"
    with chat_history_lock:
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)
            f.flush()


def read_chat_history(override_path: Path | None = None) -> list[dict[str, Any]]:
    """
    Thread-safe reading of student chat history turns from student_chat_history.jsonl.
    """
    path = get_student_chat_history_path(override_path)
    if not path.exists():
        return []

    records = []
    with chat_history_lock:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped:
                    try:
                        records.append(json.loads(stripped))
                    except json.JSONDecodeError:
                        continue
    return records


def clear_chat_history(override_path: Path | None = None) -> None:
    """
    Thread-safe truncation of student_chat_history.jsonl.
    """
    path = get_student_chat_history_path(override_path)
    with chat_history_lock:
        if path.exists():
            with open(path, "w", encoding="utf-8") as f:
                f.truncate(0)


# ------------------------------------------------------------------------------
# Safety Events JSONL Operations
# ------------------------------------------------------------------------------

def read_safety_events(override_path: Path | None = None) -> list[dict[str, Any]]:
    """
    Thread-safe reading of safety events from safety_events.jsonl.
    """
    path = get_safety_events_path(override_path)
    if not path.exists():
        return []

    events = []
    with safety_events_lock:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped:
                    try:
                        events.append(json.loads(stripped))
                    except json.JSONDecodeError:
                        continue
    return events


def update_safety_event_review(
    event_id: str,
    action: str,
    notes: str,
    override_path: Path | None = None,
) -> dict[str, Any] | None:
    """
    Atomically update the review status and notes for a safety event in safety_events.jsonl.
    """
    path = get_safety_events_path(override_path)
    if not path.exists():
        return None

    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    updated_record: dict[str, Any] | None = None

    with safety_events_lock:
        all_events: list[dict[str, Any]] = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped:
                    try:
                        rec = json.loads(stripped)
                        if rec.get("event_id") == event_id:
                            rec["parent_review_status"] = action.upper()
                            rec["parent_notes"] = notes
                            rec["reviewed_at"] = now_iso
                            updated_record = rec
                        all_events.append(rec)
                    except json.JSONDecodeError:
                        continue

        if updated_record is None:
            return None

        # Rewrite file atomically
        tmp_path = path.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            for rec in all_events:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)

    return updated_record
