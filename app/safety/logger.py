"""
Thread-safe event logger for safety violations and content moderation events.

Persists structured audit records in storage/safety_events.jsonl for parental
monitoring and safety auditing.
"""

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import settings
from app.safety.taxonomy import SafetyCategory, SeverityLevel

safety_log_lock = threading.Lock()


def get_safety_log_path() -> Path:
    """Return the absolute path to safety_events.jsonl."""
    return settings.storage_dir / "safety_events.jsonl"


def log_safety_event(
    query_text: str,
    category: SafetyCategory | str,
    severity: SeverityLevel | str,
    student_grade: int = 10,
    subject: str = "Science",
    chapter: int | None = None,
    session_id: str | None = None,
    filter_stage: str = "scanner",
    matched_rule: str = "",
    action_taken: str = "BLOCKED_REFUSAL",
    refusal_type: str = "standard_refusal",
    parent_notified: bool = True,
    extra: dict[str, Any] | None = None,
    file_path: Path | None = None,
) -> dict[str, Any]:
    """
    Log a structured safety moderation event to storage/safety_events.jsonl.
    Returns the created record.
    """
    event_id = f"evt_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")

    cat_str = category.value if isinstance(category, SafetyCategory) else str(category)
    sev_str = severity.value if isinstance(severity, SeverityLevel) else str(severity)

    record: dict[str, Any] = {
        "event_id": event_id,
        "timestamp": timestamp,
        "session_id": session_id or "default_session",
        "student_grade": student_grade,
        "subject": subject,
        "chapter": chapter,
        "query_text": query_text,
        "flagged": True,
        "category": cat_str,
        "severity": sev_str,
        "filter_stage": filter_stage,
        "matched_rule": matched_rule,
        "action_taken": action_taken,
        "refusal_type": refusal_type,
        "parent_notified": parent_notified,
        "parent_review_status": "PENDING",
        "parent_notes": "",
    }
    if extra:
        record["extra"] = extra

    target_file = file_path or get_safety_log_path()
    target_file.parent.mkdir(parents=True, exist_ok=True)

    with safety_log_lock:
        with open(target_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return record


def read_safety_events(limit: int = 100, file_path: Path | None = None) -> list[dict[str, Any]]:
    """Reads logged safety events from safety_events.jsonl in reverse chronological order."""
    target_file = file_path or get_safety_log_path()
    if not target_file.exists():
        return []

    events = []
    with safety_log_lock:
        with open(target_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

    # Return newest first
    events.reverse()
    return events[:limit]
