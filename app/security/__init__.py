"""
Security Safeguards & Boundary Enforcement Subpackage for NCERT Textbook Assistant.

Provides:
- Inbound prompt injection, jailbreak, and delimiter breakout screening
- Unicode NFKC normalization, zero-width character stripping, and Base64 inspection
- Structural XML containment envelopes and character sanitization
- Dual-pass output guardrail with system prompt leak and affirmative jailbreak detection
"""

from typing import Any

from app.security.delimiters import (
    sanitize_for_prompt,
    wrap_conversation_turn,
    wrap_excerpt,
    wrap_student_query,
    wrap_textbook_context,
)
from app.security.guardrail import (
    GuardrailResult,
    StreamingOutputGuardrail,
    detect_affirmative_jailbreak,
    detect_prompt_leak,
    get_guardrail_refusal,
    scan_output_leak,
)
from app.security.normalizer import (
    canonicalize_leetspeak,
    collapse_spaced_characters,
    extract_and_decode_base64,
    normalize_for_security,
    normalize_unicode,
    strip_zero_width_and_invisible,
)
from app.security.scanner import (
    SecurityScreenResult,
    ThreatCategory,
    get_security_refusal,
    scan_text_for_threats,
)


def check_security_inbound(
    text: str,
    grade: int = 10,
    subject: str = "Science",
    language: str = "English",
    session_id: str | None = None,
) -> SecurityScreenResult:
    """
    Main entry point for screening incoming student queries before vector retrieval or LLM execution.
    Evaluates against all 5 threat categories:
    1. Direct instruction overrides
    2. System prompt exfiltration
    3. Persona switching & jailbreaks
    4. Delimiter breakout attempts
    5. Affirmative prefix forcing
    """
    return scan_text_for_threats(text=text, grade=grade, language=language)


__all__ = [
    "SecurityScreenResult",
    "GuardrailResult",
    "ThreatCategory",
    "check_security_inbound",
    "scan_output_leak",
    "detect_prompt_leak",
    "detect_affirmative_jailbreak",
    "StreamingOutputGuardrail",
    "get_guardrail_refusal",
    "get_security_refusal",
    "sanitize_for_prompt",
    "wrap_student_query",
    "wrap_excerpt",
    "wrap_textbook_context",
    "wrap_conversation_turn",
    "normalize_for_security",
    "normalize_unicode",
    "strip_zero_width_and_invisible",
    "canonicalize_leetspeak",
    "collapse_spaced_characters",
    "extract_and_decode_base64",
    "scan_text_for_threats",
]
