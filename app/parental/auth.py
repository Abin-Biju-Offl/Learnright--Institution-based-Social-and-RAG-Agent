"""
Authentication, Cryptographic Hashing, Progressive Lockout, and Session Token Management.
"""

import hashlib
import secrets
import threading
import time
from typing import Any


# ------------------------------------------------------------------------------
# Cryptographic PBKDF2-HMAC-SHA256 PIN & Recovery Key Hashing
# ------------------------------------------------------------------------------

PBKDF2_ITERATIONS = 100_000
SALT_BYTE_LENGTH = 16


def hash_pin(pin: str, salt: bytes | None = None) -> tuple[str, str]:
    """
    Hash a 4-6 digit numeric PIN using PBKDF2-HMAC-SHA256.
    Returns (salt_hex, hash_hex).
    """
    if salt is None:
        salt = secrets.token_bytes(SALT_BYTE_LENGTH)
    dk = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return salt.hex(), dk.hex()


def verify_pin_hash(pin: str, salt_hex: str, hash_hex: str) -> bool:
    """
    Verify whether the provided PIN matches the stored PBKDF2-HMAC-SHA256 hash.
    Uses constant-time comparison to prevent timing attacks.
    """
    try:
        salt = bytes.fromhex(salt_hex)
        dk = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, PBKDF2_ITERATIONS)
        return secrets.compare_digest(dk.hex(), hash_hex)
    except Exception:
        return False


def generate_recovery_key() -> str:
    """
    Generate a 16-character alphanumeric emergency recovery key.
    Format: NCERT-XXXX-XXXX-XXXX
    """
    part1 = secrets.token_hex(2).upper()
    part2 = secrets.token_hex(2).upper()
    part3 = secrets.token_hex(2).upper()
    return f"NCERT-{part1}-{part2}-{part3}"


def hash_recovery_key(key: str, salt: bytes | None = None) -> tuple[str, str]:
    """
    Hash the recovery key with salt using PBKDF2.
    """
    clean_key = key.strip().upper()
    if salt is None:
        salt = secrets.token_bytes(SALT_BYTE_LENGTH)
    dk = hashlib.pbkdf2_hmac("sha256", clean_key.encode("utf-8"), salt, 10_000)
    return salt.hex(), dk.hex()


def verify_recovery_key_hash(key: str, salt_hex: str, hash_hex: str) -> bool:
    """
    Verify an emergency recovery key.
    """
    try:
        clean_key = key.strip().upper()
        salt = bytes.fromhex(salt_hex)
        dk = hashlib.pbkdf2_hmac("sha256", clean_key.encode("utf-8"), salt, 10_000)
        return secrets.compare_digest(dk.hex(), hash_hex)
    except Exception:
        return False


# ------------------------------------------------------------------------------
# In-Memory Bearer Session Token Management
# ------------------------------------------------------------------------------

_sessions_lock = threading.Lock()
# token -> {"created_at": float, "last_activity": float, "expires_at": float, "timeout_seconds": int}
_active_sessions: dict[str, dict[str, Any]] = {}


def create_session(timeout_seconds: int = 900) -> str:
    """
    Generate a high-entropy 32-byte Bearer session token and register it.
    Default expiry is 15 minutes (900 seconds).
    """
    token = f"tok_par_{secrets.token_urlsafe(32)}"
    now = time.time()
    with _sessions_lock:
        _active_sessions[token] = {
            "created_at": now,
            "last_activity": now,
            "expires_at": now + timeout_seconds,
            "timeout_seconds": timeout_seconds,
        }
    return token


def validate_session(token: str) -> bool:
    """
    Check if token exists and is not expired. If valid, refreshes inactivity window.
    """
    if not token:
        return False
    now = time.time()
    with _sessions_lock:
        session = _active_sessions.get(token)
        if not session:
            return False
        if now > session["expires_at"]:
            # Session expired
            del _active_sessions[token]
            return False
        # Refresh inactivity expiry
        session["last_activity"] = now
        session["expires_at"] = now + session["timeout_seconds"]
        return True


def revoke_session(token: str) -> bool:
    """
    Revoke/invalidate an active session token immediately upon logout.
    """
    with _sessions_lock:
        if token in _active_sessions:
            del _active_sessions[token]
            return True
        return False


def clear_all_sessions() -> None:
    """Clear all active sessions (e.g. for testing)."""
    with _sessions_lock:
        _active_sessions.clear()


# ------------------------------------------------------------------------------
# Progressive Brute-Force Lockout Logic
# ------------------------------------------------------------------------------

LOCKOUT_5_FAILS_SECONDS = 300   # 5 minutes
LOCKOUT_8_FAILS_SECONDS = 900   # 15 minutes


def calculate_lockout(failed_attempts: int, current_locked_until: float | None) -> tuple[bool, int]:
    """
    Determines if user is currently locked out and returns (is_locked, remaining_seconds).
    """
    now = time.time()
    if current_locked_until is not None and current_locked_until > now:
        remaining = int(current_locked_until - now)
        return True, max(1, remaining)
    return False, 0


def update_lockout_on_failure(failed_attempts: int) -> tuple[int, float | None, int]:
    """
    Increments failed attempts and calculates new locked_until timestamp if threshold met.
    Returns (new_failed_attempts, new_locked_until, lockout_seconds).
    """
    new_fails = failed_attempts + 1
    now = time.time()
    if new_fails >= 8:
        locked_until = now + LOCKOUT_8_FAILS_SECONDS
        return new_fails, locked_until, LOCKOUT_8_FAILS_SECONDS
    elif new_fails >= 5:
        locked_until = now + LOCKOUT_5_FAILS_SECONDS
        return new_fails, locked_until, LOCKOUT_5_FAILS_SECONDS
    else:
        return new_fails, None, 0
