"""
Business logic and service orchestration for Parental Controls.
"""

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException

from app.parental.auth import (
    calculate_lockout,
    create_session,
    generate_recovery_key,
    hash_pin,
    hash_recovery_key,
    update_lockout_on_failure,
    verify_pin_hash,
    verify_recovery_key_hash,
)
from app.parental.schemas import (
    AuthStatusResponse,
    AuthTokenResponse,
    CategorySettings,
    ChangePinRequest,
    ChatHistoryResponse,
    ChatTurnRecord,
    FlaggedAlertsResponse,
    OverviewResponse,
    ParentalSettingsUpdate,
    PinSetupRequest,
    PinVerifyRequest,
    ResetPinRequest,
    ReviewFlagResponse,
    SettingsResponse,
)
from app.parental.storage import (
    clear_chat_history,
    load_parental_config,
    read_chat_history,
    read_safety_events,
    save_parental_config,
    update_safety_event_review,
)


class ParentalService:
    @staticmethod
    def get_auth_status() -> AuthStatusResponse:
        """Check whether PIN is set up and if the portal is under brute-force lockout."""
        config = load_parental_config()
        sec = config.get("security", {})
        pin_configured = bool(sec.get("pin_configured", False))
        failed_attempts = int(sec.get("failed_attempts", 0))
        locked_until = sec.get("locked_until")

        is_locked, remaining = calculate_lockout(failed_attempts, locked_until)
        return AuthStatusResponse(
            pin_configured=pin_configured,
            is_locked=is_locked,
            lockout_remaining_seconds=remaining,
            session_active=False,
        )

    @staticmethod
    def setup_pin(req: PinSetupRequest) -> AuthTokenResponse:
        """Initial configuration of parental PIN and generation of emergency recovery key."""
        if req.pin != req.confirm_pin:
            raise HTTPException(400, "PIN and confirmation PIN do not match.")

        config = load_parental_config()
        if config.get("security", {}).get("pin_configured"):
            raise HTTPException(400, "Parental PIN is already configured. Use change-pin or reset-pin.")

        pin_salt, pin_hash = hash_pin(req.pin)
        recovery_key = generate_recovery_key()
        rec_salt, rec_hash = hash_recovery_key(recovery_key)

        timeout_minutes = config.get("security", {}).get("session_timeout_minutes", 15)

        config["security"]["pin_configured"] = True
        config["security"]["pin_salt"] = pin_salt
        config["security"]["pin_hash"] = pin_hash
        config["security"]["recovery_key_salt"] = rec_salt
        config["security"]["recovery_key_hash"] = rec_hash
        config["security"]["failed_attempts"] = 0
        config["security"]["locked_until"] = None
        config["updated_at"] = datetime.now(timezone.utc).isoformat()

        save_parental_config(config)

        token = create_session(timeout_seconds=timeout_minutes * 60)
        return AuthTokenResponse(
            success=True,
            token=token,
            expires_in_seconds=timeout_minutes * 60,
            recovery_key=recovery_key,
        )

    @staticmethod
    def verify_pin(req: PinVerifyRequest) -> AuthTokenResponse:
        """Authenticate parent with 4-6 digit PIN, enforcing progressive lockout on failure."""
        config = load_parental_config()
        sec = config.get("security", {})

        if not sec.get("pin_configured"):
            raise HTTPException(400, "Parental PIN has not been configured yet.")

        failed_attempts = int(sec.get("failed_attempts", 0))
        locked_until = sec.get("locked_until")
        is_locked, remaining = calculate_lockout(failed_attempts, locked_until)
        if is_locked:
            raise HTTPException(
                429,
                f"Parental portal locked due to repeated incorrect PIN entries. Try again in {remaining} seconds.",
            )

        pin_salt = sec.get("pin_salt", "")
        pin_hash = sec.get("pin_hash", "")

        if not verify_pin_hash(req.pin, pin_salt, pin_hash):
            new_fails, new_locked_until, lockout_seconds = update_lockout_on_failure(failed_attempts)
            config["security"]["failed_attempts"] = new_fails
            config["security"]["locked_until"] = new_locked_until
            save_parental_config(config)

            if new_locked_until is not None:
                raise HTTPException(
                    429,
                    f"Parental portal locked due to repeated incorrect PIN entries. Try again in {lockout_seconds} seconds.",
                )
            else:
                attempts_left = max(0, 5 - new_fails)
                raise HTTPException(401, f"Incorrect PIN. {attempts_left} attempts remaining.")

        # Successful verification: reset lockout state
        config["security"]["failed_attempts"] = 0
        config["security"]["locked_until"] = None
        save_parental_config(config)

        timeout_minutes = config.get("security", {}).get("session_timeout_minutes", 15)
        token = create_session(timeout_seconds=timeout_minutes * 60)
        return AuthTokenResponse(
            success=True,
            token=token,
            expires_in_seconds=timeout_minutes * 60,
        )

    @staticmethod
    def change_pin(req: ChangePinRequest) -> dict[str, Any]:
        """Update existing PIN after validating current PIN."""
        if req.new_pin != req.confirm_new_pin:
            raise HTTPException(400, "New PIN and confirmation PIN do not match.")

        config = load_parental_config()
        sec = config.get("security", {})
        if not sec.get("pin_configured"):
            raise HTTPException(400, "Parental PIN has not been configured yet.")

        if not verify_pin_hash(req.current_pin, sec.get("pin_salt", ""), sec.get("pin_hash", "")):
            raise HTTPException(401, "Current PIN is incorrect.")

        new_salt, new_hash = hash_pin(req.new_pin)
        config["security"]["pin_salt"] = new_salt
        config["security"]["pin_hash"] = new_hash
        config["security"]["failed_attempts"] = 0
        config["security"]["locked_until"] = None
        config["updated_at"] = datetime.now(timezone.utc).isoformat()
        save_parental_config(config)

        return {"success": True, "message": "Parental PIN changed successfully."}

    @staticmethod
    def reset_pin(req: ResetPinRequest) -> AuthTokenResponse:
        """Reset forgotten PIN using 16-character Emergency Recovery Key."""
        if req.new_pin != req.confirm_new_pin:
            raise HTTPException(400, "New PIN and confirmation PIN do not match.")

        config = load_parental_config()
        sec = config.get("security", {})
        rec_salt = sec.get("recovery_key_salt", "")
        rec_hash = sec.get("recovery_key_hash", "")

        if not rec_salt or not rec_hash or not verify_recovery_key_hash(req.recovery_key, rec_salt, rec_hash):
            raise HTTPException(401, "Invalid emergency recovery key.")

        new_salt, new_hash = hash_pin(req.new_pin)
        timeout_minutes = sec.get("session_timeout_minutes", 15)

        config["security"]["pin_configured"] = True
        config["security"]["pin_salt"] = new_salt
        config["security"]["pin_hash"] = new_hash
        config["security"]["failed_attempts"] = 0
        config["security"]["locked_until"] = None
        config["updated_at"] = datetime.now(timezone.utc).isoformat()
        save_parental_config(config)

        token = create_session(timeout_seconds=timeout_minutes * 60)
        return AuthTokenResponse(
            success=True,
            token=token,
            expires_in_seconds=timeout_minutes * 60,
        )

    @staticmethod
    def get_overview() -> OverviewResponse:
        """Calculate high-level student study activity and safety compliance metrics."""
        history = read_chat_history()
        events = read_safety_events()
        config = load_parental_config()

        total_queries = len(history)
        flagged_in_history = sum(1 for h in history if h.get("flagged", False))
        # Total flagged accounts for any blocked turns plus logged safety events
        flagged_count = max(flagged_in_history, len(events))
        clean_count = max(0, total_queries - flagged_in_history)

        unreviewed_alerts = sum(1 for e in events if e.get("parent_review_status", "PENDING") == "PENDING")

        compliance_rate = (
            round((clean_count / total_queries) * 100.0, 1) if total_queries > 0 else 100.0
        )

        # Calculate distinct active study days
        active_days = set()
        for turn in history:
            ts = turn.get("timestamp")
            if ts and len(ts) >= 10:
                active_days.add(ts[:10])

        # Top studied subjects
        subject_counts: dict[tuple[str, int], int] = {}
        for turn in history:
            subj = turn.get("subject", "Science")
            grade = int(turn.get("student_grade", 10))
            key = (subj, grade)
            subject_counts[key] = subject_counts.get(key, 0) + 1

        top_studied = [
            {"subject": k[0], "grade": k[1], "queries": v}
            for k, v in sorted(subject_counts.items(), key=lambda item: item[1], reverse=True)
        ]

        # Flagged category breakdown
        category_breakdown: dict[str, int] = {
            "adult_sexual": 0,
            "violence_gore": 0,
            "self_harm": 0,
            "hate_speech": 0,
            "illegal_acts_weapons_drugs": 0,
            "cyberbullying": 0,
            "other_inappropriate": 0,
            "custom_blocked": 0,
        }
        for e in events:
            cat = str(e.get("category", "")).lower()
            if cat in category_breakdown:
                category_breakdown[cat] += 1
            elif "weapon" in cat or "illegal" in cat:
                category_breakdown["illegal_acts_weapons_drugs"] += 1
            elif "adult" in cat or "sex" in cat:
                category_breakdown["adult_sexual"] += 1
            elif "harm" in cat or "suicide" in cat:
                category_breakdown["self_harm"] += 1
            elif "custom" in cat:
                category_breakdown["custom_blocked"] += 1
            else:
                category_breakdown["other_inappropriate"] += 1

        profile = config.get("filtering", {}).get("strictness_profile", "curriculum_standard")
        last_activity = history[-1].get("timestamp") if history else None

        return OverviewResponse(
            total_student_queries=total_queries,
            clean_queries=clean_count,
            flagged_queries=flagged_count,
            unreviewed_alerts=unreviewed_alerts,
            safety_compliance_rate_percent=compliance_rate,
            active_days_count=len(active_days),
            top_studied_subjects=top_studied,
            flagged_category_breakdown=category_breakdown,
            current_strictness_profile=profile,
            last_student_activity=last_activity,
        )

    @staticmethod
    def get_history(
        limit: int = 25,
        offset: int = 0,
        grade: int | None = None,
        subject: str | None = None,
        flagged_only: bool = False,
        search: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> ChatHistoryResponse:
        """Query and filter student conversation history with search and pagination."""
        history = read_chat_history()

        limit_val = int(getattr(limit, "default", limit) or 25)
        offset_val = int(getattr(offset, "default", offset) or 0)
        grade_val = getattr(grade, "default", grade)
        subject_val = getattr(subject, "default", subject)
        flagged_only_val = bool(getattr(flagged_only, "default", flagged_only))
        search_val = getattr(search, "default", search)
        date_from_val = getattr(date_from, "default", date_from)
        date_to_val = getattr(date_to, "default", date_to)

        filtered = []
        search_lower = str(search_val).strip().lower() if search_val else None

        for turn in history:
            if grade_val is not None and int(turn.get("student_grade", 0)) != grade_val:
                continue
            if subject_val and turn.get("subject", "").lower() != str(subject_val).strip().lower():
                continue
            if flagged_only_val and not turn.get("flagged", False):
                continue
            if search_lower:
                q_text = turn.get("question", "").lower()
                a_text = turn.get("answer", "").lower()
                if search_lower not in q_text and search_lower not in a_text:
                    continue
            ts = turn.get("timestamp", "")
            if date_from_val and ts and ts < str(date_from_val):
                continue
            if date_to_val and ts and ts > str(date_to_val):
                continue
            filtered.append(turn)

        # Most recent first
        filtered.reverse()
        total = len(filtered)
        paginated = filtered[offset_val : offset_val + limit_val]

        records = [ChatTurnRecord(**rec) for rec in paginated]
        return ChatHistoryResponse(
            total=total,
            offset=offset_val,
            limit=limit_val,
            records=records,
        )

    @staticmethod
    def clear_history() -> dict[str, Any]:
        """Clear all student conversation records."""
        clear_chat_history()
        return {"success": True, "message": "Student chat history cleared."}

    @staticmethod
    def get_flagged(
        status: str = "PENDING",
        category: str | None = None,
        limit: int = 50,
    ) -> FlaggedAlertsResponse:
        """Retrieve flagged and blocked query alerts with review status."""
        events = read_safety_events()
        status_val = getattr(status, "default", status) or "PENDING"
        category_val = getattr(category, "default", category)
        limit_val = int(getattr(limit, "default", limit) or 50)

        status_upper = str(status_val).strip().upper()
        category_lower = str(category_val).strip().lower() if category_val else None

        filtered = []
        unreviewed = 0
        for e in events:
            rev_status = str(e.get("parent_review_status", "PENDING")).upper()
            if rev_status == "PENDING":
                unreviewed += 1

            if status_upper != "ALL":
                if status_upper == "PENDING" and rev_status != "PENDING":
                    continue
                if status_upper == "REVIEWED" and rev_status == "PENDING":
                    continue

            if category_lower:
                cat = str(e.get("category", "")).lower()
                if category_lower not in cat:
                    continue

            filtered.append(e)

        filtered.reverse()
        total = len(filtered)
        limited = filtered[:limit]

        return FlaggedAlertsResponse(
            total=total,
            unreviewed_count=unreviewed,
            events=limited,
        )

    @staticmethod
    def review_flag(event_id: str, action: str, notes: str) -> ReviewFlagResponse:
        """Mark a flagged safety event as reviewed, acknowledged, or dismissed with notes."""
        updated = update_safety_event_review(event_id, action=action, notes=notes)
        if not updated:
            raise HTTPException(404, f"Safety event with ID '{event_id}' not found.")

        return ReviewFlagResponse(
            success=True,
            event_id=event_id,
            parent_review_status=updated.get("parent_review_status", action.upper()),
            reviewed_at=updated.get("reviewed_at", datetime.now(timezone.utc).isoformat()),
            parent_notes=updated.get("parent_notes", notes),
        )

    @staticmethod
    def get_settings() -> SettingsResponse:
        """Fetch active content filtering preferences, categories, and keyword blacklists."""
        config = load_parental_config()
        filt = config.get("filtering", {})
        sec = config.get("security", {})

        return SettingsResponse(
            strictness_profile=filt.get("strictness_profile", "curriculum_standard"),
            categories=filt.get("categories", CategorySettings().model_dump()),
            allow_ncert_biology_reproduction=filt.get("allow_ncert_biology_reproduction", True),
            custom_blocked_keywords=filt.get("custom_blocked_keywords", []),
            custom_blocked_topics=filt.get("custom_blocked_topics", []),
            session_timeout_minutes=sec.get("session_timeout_minutes", 15),
            updated_at=config.get("updated_at"),
        )

    @staticmethod
    def update_settings(update: ParentalSettingsUpdate) -> SettingsResponse:
        """Persist updated filtering preferences while preserving non-negotiable safety rules."""
        config = load_parental_config()

        # Enforce non-negotiable categories
        cats = update.categories.model_dump()
        cats["self_harm"] = True
        cats["illegal_acts_weapons_drugs"] = True

        # Normalize keywords (lowercase, trimmed, deduplicated)
        clean_keywords = []
        seen = set()
        for kw in update.custom_blocked_keywords:
            c = kw.strip().lower()
            if c and c not in seen:
                seen.add(c)
                clean_keywords.append(c)

        clean_topics = []
        seen_topics = set()
        for tp in update.custom_blocked_topics:
            c = tp.strip().lower()
            if c and c not in seen_topics:
                seen_topics.add(c)
                clean_topics.append(c)

        config["filtering"]["strictness_profile"] = update.strictness_profile
        config["filtering"]["categories"] = cats
        config["filtering"]["allow_ncert_biology_reproduction"] = update.allow_ncert_biology_reproduction
        config["filtering"]["custom_blocked_keywords"] = clean_keywords
        config["filtering"]["custom_blocked_topics"] = clean_topics
        config["filtering"]["session_timeout_minutes"] = update.session_timeout_minutes
        config["security"]["session_timeout_minutes"] = update.session_timeout_minutes
        config["updated_at"] = datetime.now(timezone.utc).isoformat()

        save_parental_config(config)

        return SettingsResponse(
            strictness_profile=update.strictness_profile,
            categories=cats,
            allow_ncert_biology_reproduction=update.allow_ncert_biology_reproduction,
            custom_blocked_keywords=clean_keywords,
            custom_blocked_topics=clean_topics,
            session_timeout_minutes=update.session_timeout_minutes,
            updated_at=config["updated_at"],
        )


def get_active_parental_filtering_config() -> dict[str, Any]:
    """
    Helper providing the active filtering config formatted for evaluate_content in app/safety/.
    """
    config = load_parental_config()
    filt = config.get("filtering", {})
    categories = filt.get("categories", {})
    keywords = filt.get("custom_blocked_keywords", [])

    return {
        "custom_blacklist": keywords,
        "custom_blocked_keywords": keywords,
        "category_filters": categories,
        "categories": categories,
        "allow_ncert_biology_reproduction": filt.get("allow_ncert_biology_reproduction", True),
        "strictness_profile": filt.get("strictness_profile", "curriculum_standard"),
    }
