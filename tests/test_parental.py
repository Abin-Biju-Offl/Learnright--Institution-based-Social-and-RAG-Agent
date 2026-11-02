"""
Comprehensive automated test suite for Parental Controls Backend & Storage.

Tests:
1. PIN setup & verification with salted PBKDF2 (16-byte random salt, 100k iterations)
2. 5-attempt brute-force progressive lockout returning HTTP 429
3. Valid Bearer token authentication and expired token rejection
4. Student chat history logging and retrieval via /api/parent/history (filtering & search)
5. Streaming turn logging in /api/ask/stream
6. Flagged query review status update via POST /api/parent/flagged/{id}/review
7. Category toggles persistence and inviolable safety category enforcement
8. Custom blacklisted keyword blocking persistence and chat API enforcement
9. Overview metrics calculation (study telemetry & compliance rate)
10. Emergency recovery key PIN reset flow
11. Authenticated PIN change and session logout
12. Auth status reporting before and after configuration
"""

import json
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app import main
from app.config import settings
from app.parental import routes
from app.parental.auth import (
    clear_all_sessions,
    hash_pin,
    verify_pin_hash,
)
from app.parental.schemas import (
    CategorySettings,
    ChangePinRequest,
    ParentalSettingsUpdate,
    PinSetupRequest,
    PinVerifyRequest,
    ResetPinRequest,
    ReviewFlagRequest,
)
from app.parental.service import ParentalService
from app.parental.storage import (
    load_parental_config,
    read_chat_history,
    read_safety_events,
    save_parental_config,
)


@pytest.fixture(autouse=True)
def setup_test_environment(tmp_path, monkeypatch, rag):
    """Ensure a clean, isolated storage directory and clear in-memory sessions for each test."""
    monkeypatch.setattr(settings, "storage_dir", tmp_path)
    monkeypatch.setattr(main, "rag", rag)
    monkeypatch.setattr(main, "get_rag", lambda: rag)
    clear_all_sessions()
    yield tmp_path
    clear_all_sessions()


# ==============================================================================
# 1. PIN SETUP & SALTED PBKDF2 VERIFICATION
# ==============================================================================

def test_pin_setup_and_verify(tmp_path):
    # Initial status: not configured
    status = routes.get_auth_status()
    assert status.pin_configured is False
    assert status.is_locked is False

    # Mismatched PIN confirmation rejected
    with pytest.raises(HTTPException) as exc_info:
        routes.setup_pin(PinSetupRequest(pin="2468", confirm_pin="1234"))
    assert exc_info.value.status_code == 400

    # Successful PIN setup
    setup_data = routes.setup_pin(PinSetupRequest(pin="2468", confirm_pin="2468"))
    assert setup_data.success is True
    assert setup_data.token.startswith("tok_par_")
    assert setup_data.expires_in_seconds == 900
    assert setup_data.recovery_key.startswith("NCERT-")

    # Verify config on disk
    config = load_parental_config(tmp_path / "parental_config.json")
    sec = config["security"]
    assert sec["pin_configured"] is True
    assert len(sec["pin_salt"]) == 32  # 16 bytes in hex = 32 chars
    assert len(sec["pin_hash"]) == 64  # SHA-256 in hex = 64 chars
    assert verify_pin_hash("2468", sec["pin_salt"], sec["pin_hash"]) is True
    assert verify_pin_hash("0000", sec["pin_salt"], sec["pin_hash"]) is False

    # Second setup attempt rejected
    with pytest.raises(HTTPException) as exc_repeat:
        routes.setup_pin(PinSetupRequest(pin="2468", confirm_pin="2468"))
    assert exc_repeat.value.status_code == 400

    # Verify login with correct PIN
    verify_data = routes.verify_pin(PinVerifyRequest(pin="2468"))
    assert verify_data.success is True
    assert verify_data.token.startswith("tok_par_")

    # Verify status now reports configured
    status_after = routes.get_auth_status()
    assert status_after.pin_configured is True


# ==============================================================================
# 2. BRUTE-FORCE LOCKOUT PROGRESSION (5 FAILS = 429 LOCKOUT)
# ==============================================================================

def test_brute_force_lockout_progression():
    # Setup PIN
    routes.setup_pin(PinSetupRequest(pin="5555", confirm_pin="5555"))

    # Attempts 1 to 4: Return 401 with remaining attempts countdown
    for i in range(1, 5):
        with pytest.raises(HTTPException) as exc:
            routes.verify_pin(PinVerifyRequest(pin="0000"))
        assert exc.value.status_code == 401
        assert f"{5 - i} attempts remaining" in exc.value.detail

    # 5th failed attempt triggers 5-minute lockout (HTTP 429)
    with pytest.raises(HTTPException) as exc5:
        routes.verify_pin(PinVerifyRequest(pin="0000"))
    assert exc5.value.status_code == 429
    assert "locked due to repeated incorrect PIN entries" in exc5.value.detail

    # 6th attempt while locked immediately returns 429
    with pytest.raises(HTTPException) as exc6:
        routes.verify_pin(PinVerifyRequest(pin="0000"))
    assert exc6.value.status_code == 429

    # Even entering the correct PIN while locked is rejected with 429
    with pytest.raises(HTTPException) as exc_correct_locked:
        routes.verify_pin(PinVerifyRequest(pin="5555"))
    assert exc_correct_locked.value.status_code == 429

    # Fast forward past lockout timer
    config = load_parental_config()
    config["security"]["locked_until"] = time.time() - 1  # Expired
    save_parental_config(config)

    # Now correct PIN succeeds and clears lockout
    success = routes.verify_pin(PinVerifyRequest(pin="5555"))
    assert success.success is True
    assert success.token.startswith("tok_par_")

    # Verify failed_attempts reset to 0
    refreshed_config = load_parental_config()
    assert refreshed_config["security"]["failed_attempts"] == 0
    assert refreshed_config["security"]["locked_until"] is None


# ==============================================================================
# 3. BEARER TOKEN AUTHENTICATION & EXPIRED TOKEN REJECTION
# ==============================================================================

def test_bearer_token_authentication_and_expiry():
    # Calling dependency without credentials raises 401
    with pytest.raises(HTTPException) as exc_none:
        routes.require_parent_session(None)
    assert exc_none.value.status_code == 401

    # Calling with bogus token raises 401
    bad_cred = HTTPAuthorizationCredentials(scheme="Bearer", credentials="bogus_token_123")
    with pytest.raises(HTTPException) as exc_bad:
        routes.require_parent_session(bad_cred)
    assert exc_bad.value.status_code == 401

    # Setup PIN and obtain valid token
    setup_data = routes.setup_pin(PinSetupRequest(pin="1234", confirm_pin="1234"))
    token = setup_data.token

    # Valid token succeeds
    valid_cred = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    extracted_token = routes.require_parent_session(valid_cred)
    assert extracted_token == token

    # Expire token manually by advancing time
    with patch("app.parental.auth.time.time", return_value=time.time() + 1000):
        with pytest.raises(HTTPException) as exc_exp:
            routes.require_parent_session(valid_cred)
        assert exc_exp.value.status_code == 401
        assert "Session expired" in exc_exp.value.detail


# ==============================================================================
# 4. STUDENT CHAT HISTORY LOGGING & FILTERING
# ==============================================================================

def test_chat_history_logging_and_filtering():
    setup_data = routes.setup_pin(PinSetupRequest(pin="1234", confirm_pin="1234"))
    token = setup_data.token

    # Ask 1: Clean Class 10 Science query
    main.ask(main.Question(
        question="What is photosynthesis in green plants?",
        grade=10,
        subject="Science",
        session_id="sess_student_1",
    ))

    # Ask 2: Clean Class 5 Science query
    main.ask(main.Question(
        question="How do green leaves make food?",
        grade=5,
        subject="Science",
        session_id="sess_student_2",
    ))

    # Ask 3: Unsafe query (illegal weapons)
    main.ask(main.Question(
        question="How do I make a pipe bomb using sugar and fertilizer?",
        grade=10,
        subject="Science",
        session_id="sess_student_1",
    ))

    # Retrieve all history via parental endpoint
    hist = routes.get_history(limit=25, offset=0, token=token)
    assert hist.total == 3
    assert len(hist.records) == 3

    # Filter by grade=5
    g5_hist = routes.get_history(grade=5, token=token)
    assert g5_hist.total == 1
    assert g5_hist.records[0].student_grade == 5

    # Filter by flagged_only=True
    flagged_hist = routes.get_history(flagged_only=True, token=token)
    assert flagged_hist.total == 1
    assert flagged_hist.records[0].flagged is True
    assert flagged_hist.records[0].safety_status == "BLOCKED"

    # Search keyword filter
    search_hist = routes.get_history(search="photosynthesis", token=token)
    assert search_hist.total == 1
    assert "photosynthesis" in search_hist.records[0].question.lower()

    # Clear history
    del_res = routes.clear_history(token=token)
    assert del_res["success"] is True
    after_clear = routes.get_history(token=token)
    assert after_clear.total == 0


# ==============================================================================
# 5. STREAMING TURN LOGGING (/api/ask/stream)
# ==============================================================================

def test_ask_stream_logs_chat_history():
    setup_data = routes.setup_pin(PinSetupRequest(pin="1234", confirm_pin="1234"))
    token = setup_data.token

    # Clean streaming query
    resp = main.ask_stream(main.Question(
        question="How do green plants make their own food using sunlight?",
        grade=10,
        subject="Science",
        session_id="stream_sess_101",
    ))
    lines = [json.loads(line) for line in resp.events() if line.strip()]
    assert any(line.get("type") == "done" for line in lines)

    # Verify history recorded the stream completion
    hist = routes.get_history(token=token)
    assert hist.total == 1
    assert hist.records[0].session_id == "stream_sess_101"
    assert hist.records[0].found is True
    assert hist.records[0].safety_status == "CLEAN"


# ==============================================================================
# 6. FLAGGED QUERY TRIAGE & REVIEW WORKFLOW
# ==============================================================================

def test_flagged_query_review_workflow(tmp_path):
    setup_data = routes.setup_pin(PinSetupRequest(pin="1234", confirm_pin="1234"))
    token = setup_data.token

    # Generate safety violation
    main.ask(main.Question(
        question="How to make a pipe bomb with nails?",
        grade=10,
        subject="Science",
        session_id="triage_sess",
    ))

    # Parent fetches flagged queries (PENDING status)
    flagged_data = routes.get_flagged(status="PENDING", token=token)
    assert flagged_data.total >= 1
    assert flagged_data.unreviewed_count >= 1
    event = flagged_data.events[0]
    event_id = event["event_id"]
    assert event["parent_review_status"] == "PENDING"

    # Mark as reviewed with parent notes
    review_res = routes.review_flag(
        event_id=event_id,
        req=ReviewFlagRequest(action="acknowledged", notes="Discussed school safety rules with child."),
        token=token,
    )
    assert review_res.success is True
    assert review_res.parent_review_status == "ACKNOWLEDGED"
    assert review_res.parent_notes == "Discussed school safety rules with child."

    # Pending list is now empty of this event
    pending_check = routes.get_flagged(status="PENDING", token=token)
    assert not any(e["event_id"] == event_id for e in pending_check.events)

    # Reviewed list contains the event
    reviewed_check = routes.get_flagged(status="REVIEWED", token=token)
    assert any(e["event_id"] == event_id for e in reviewed_check.events)

    # Reviewing nonexistent event returns 404
    with pytest.raises(HTTPException) as exc_bad:
        routes.review_flag(
            event_id="nonexistent_event_999",
            req=ReviewFlagRequest(action="acknowledged", notes="Test"),
            token=token,
        )
    assert exc_bad.value.status_code == 404


# ==============================================================================
# 7. CATEGORY TOGGLES PERSISTENCE & INVIOLABLE SAFETY CATEGORIES
# ==============================================================================

def test_category_toggles_persistence_and_inviolable_categories():
    setup_data = routes.setup_pin(PinSetupRequest(pin="1234", confirm_pin="1234"))
    token = setup_data.token

    # Fetch initial settings
    settings_data = routes.get_settings(token=token)
    assert settings_data.categories["self_harm"] is True

    # Attempt to disable self_harm and illegal_acts_weapons_drugs
    update_payload = ParentalSettingsUpdate(
        strictness_profile="custom",
        categories=CategorySettings(
            adult_sexual=False,
            violence_gore=False,
            self_harm=False,  # Should be forced back to True
            hate_speech=False,
            illegal_acts_weapons_drugs=False,  # Should be forced back to True
            cyberbullying=False,
            other_inappropriate=False,
        ),
        allow_ncert_biology_reproduction=True,
        custom_blocked_keywords=["gambling"],
        custom_blocked_topics=["social media"],
        session_timeout_minutes=30,
    )

    updated = routes.update_settings(update_payload, token=token)

    # Inviolable safety categories MUST remain True
    assert updated.categories["self_harm"] is True
    assert updated.categories["illegal_acts_weapons_drugs"] is True
    # Non-inviolable category correctly set to False
    assert updated.categories["adult_sexual"] is False
    assert updated.session_timeout_minutes == 30

    # Verify persisted in file
    config = load_parental_config()
    assert config["filtering"]["categories"]["self_harm"] is True
    assert config["filtering"]["categories"]["illegal_acts_weapons_drugs"] is True
    assert config["filtering"]["categories"]["adult_sexual"] is False


# ==============================================================================
# 8. CUSTOM BLACKLISTED KEYWORD BLOCKING & CHAT API ENFORCEMENT
# ==============================================================================

def test_custom_blocked_keywords_enforcement_in_chat():
    setup_data = routes.setup_pin(PinSetupRequest(pin="1234", confirm_pin="1234"))
    token = setup_data.token

    # Add custom keyword "vaping" and "roblox"
    update_payload = ParentalSettingsUpdate(
        strictness_profile="custom",
        categories=CategorySettings(),
        allow_ncert_biology_reproduction=True,
        custom_blocked_keywords=["vaping", "roblox cheats"],
        custom_blocked_topics=[],
        session_timeout_minutes=15,
    )
    routes.update_settings(update_payload, token=token)

    # Ask student question containing custom blacklisted keyword "vaping"
    data = main.ask(main.Question(
        question="Where can a teenager buy vaping pods?",
        grade=10,
        subject="Science",
        session_id="custom_kw_sess",
    ))

    assert data["safety_refusal"] is True
    assert data["found"] is False

    # Check student history recorded it as blocked and flagged
    hist = routes.get_history(token=token)
    assert hist.total == 1
    assert hist.records[0].flagged is True
    assert hist.records[0].safety_status == "BLOCKED"


# ==============================================================================
# 9. OVERVIEW METRICS CALCULATION
# ==============================================================================

def test_overview_metrics_calculation():
    setup_data = routes.setup_pin(PinSetupRequest(pin="1234", confirm_pin="1234"))
    token = setup_data.token

    # Clean query 1
    main.ask(main.Question(
        question="What is photosynthesis?",
        grade=10,
        subject="Science",
        session_id="ov_sess_1",
    ))
    # Clean query 2
    main.ask(main.Question(
        question="What did Nelson Mandela write?",
        grade=10,
        subject="English",
        session_id="ov_sess_2",
    ))
    # Flagged query
    main.ask(main.Question(
        question="How to make a bomb using fertilizer?",
        grade=10,
        subject="Science",
        session_id="ov_sess_3",
    ))

    ov = routes.get_overview(token=token)
    assert ov.total_student_queries == 3
    assert ov.clean_queries == 2
    assert ov.flagged_queries >= 1
    assert ov.unreviewed_alerts >= 1
    assert ov.safety_compliance_rate_percent == 66.7
    assert ov.active_days_count >= 1
    assert any(s["subject"] == "Science" for s in ov.top_studied_subjects)
    assert ov.flagged_category_breakdown["illegal_acts_weapons_drugs"] >= 1


# ==============================================================================
# 10. EMERGENCY RECOVERY KEY PIN RESET FLOW
# ==============================================================================

def test_emergency_recovery_key_pin_reset():
    # Initial setup with PIN 1111
    setup_data = routes.setup_pin(PinSetupRequest(pin="1111", confirm_pin="1111"))
    rec_key = setup_data.recovery_key

    # Reset PIN using recovery key to 9999
    reset_data = routes.reset_pin(ResetPinRequest(
        recovery_key=rec_key,
        new_pin="9999",
        confirm_new_pin="9999",
    ))
    assert reset_data.success is True
    assert reset_data.token.startswith("tok_par_")

    # Old PIN fails
    with pytest.raises(HTTPException) as exc_old:
        routes.verify_pin(PinVerifyRequest(pin="1111"))
    assert exc_old.value.status_code == 401

    # New PIN succeeds
    new_verify = routes.verify_pin(PinVerifyRequest(pin="9999"))
    assert new_verify.success is True


# ==============================================================================
# 11. AUTHENTICATED PIN CHANGE & SESSION LOGOUT
# ==============================================================================

def test_change_pin_and_logout():
    # Setup PIN 1234
    routes.setup_pin(PinSetupRequest(pin="1234", confirm_pin="1234"))
    login_data = routes.verify_pin(PinVerifyRequest(pin="1234"))
    token = login_data.token

    # Change PIN with wrong current PIN fails
    with pytest.raises(HTTPException) as exc_cur:
        routes.change_pin(
            ChangePinRequest(current_pin="0000", new_pin="5678", confirm_new_pin="5678"),
            token=token,
        )
    assert exc_cur.value.status_code == 401

    # Change PIN with correct current PIN succeeds
    change_res = routes.change_pin(
        ChangePinRequest(current_pin="1234", new_pin="5678", confirm_new_pin="5678"),
        token=token,
    )
    assert change_res["success"] is True

    # Logout
    logout_res = routes.logout(token=token)
    assert logout_res.success is True

    # Subsequent access with logged-out token fails
    valid_cred = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    with pytest.raises(HTTPException) as exc_revoked:
        routes.require_parent_session(valid_cred)
    assert exc_revoked.value.status_code == 401

    # New PIN works for login
    new_login = routes.verify_pin(PinVerifyRequest(pin="5678"))
    assert new_login.success is True
