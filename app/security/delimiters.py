"""
XML containment envelopes, escaping, and delimiter wrappers for prompt hardening.
Strictly separates untrusted student input and retrieved textbook excerpts
from immutable system policies.
"""

import html


def sanitize_for_prompt(text: str) -> str:
    """
    Escapes XML and HTML control characters (&, <, >, ", ') to prevent delimiter
    injection and prompt breakout attacks.
    """
    if not text:
        return ""
    # Use standard html.escape with quote=True and explicit single quote escape
    escaped = html.escape(text, quote=True)
    return escaped.replace("'", "&apos;")


def wrap_student_query(query: str, nonce: str | None = None) -> str:
    """Wraps student query in XML tag boundaries."""
    sanitized = sanitize_for_prompt((query or "").strip())
    if nonce:
        return f'<student_query nonce="{nonce}">\n{sanitized}\n</student_query>'
    return f"<student_query>\n{sanitized}\n</student_query>"


def wrap_excerpt(excerpt_id: int, chapter: int, page: int, text: str) -> str:
    """Formats a single textbook excerpt into an XML envelope."""
    sanitized_text = sanitize_for_prompt((text or "").strip())
    return f'<excerpt id="{excerpt_id}" chapter="{chapter}" page="{page}">\n{sanitized_text}\n</excerpt>'


def wrap_textbook_context(excerpts_xml: str) -> str:
    """Wraps retrieved excerpts into a <textbook_context> envelope."""
    return f"<textbook_context>\n{excerpts_xml.strip()}\n</textbook_context>"


def wrap_conversation_turn(role: str, text: str) -> str:
    """Wraps a conversation turn in a sanitized envelope."""
    clean_role = sanitize_for_prompt(role)
    clean_text = sanitize_for_prompt(text.strip())
    return f'<conversation_turn role="{clean_role}">\n{clean_text}\n</conversation_turn>'
