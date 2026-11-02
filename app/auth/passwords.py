"""
Password hashing using PBKDF2-HMAC-SHA256 (stdlib only — no extra dependencies).

Consistent with the existing parental auth hashing in app/parental/auth.py,
but adapted for user account passwords (longer inputs, same security level).
"""

import hashlib
import secrets

PBKDF2_ITERATIONS = 260_000  # OWASP 2024 recommendation for SHA-256
SALT_BYTES = 16


def hash_password(password: str, salt: bytes | None = None) -> tuple[str, str]:
    """
    Hash a password with PBKDF2-HMAC-SHA256.

    Returns (salt_hex, hash_hex).
    """
    if salt is None:
        salt = secrets.token_bytes(SALT_BYTES)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return salt.hex(), dk.hex()


def verify_password(password: str, salt_hex: str, hash_hex: str) -> bool:
    """
    Verify a password against a stored PBKDF2-HMAC-SHA256 hash.
    Uses constant-time comparison.
    """
    try:
        salt = bytes.fromhex(salt_hex)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
        return secrets.compare_digest(dk.hex(), hash_hex)
    except (ValueError, TypeError):
        return False

