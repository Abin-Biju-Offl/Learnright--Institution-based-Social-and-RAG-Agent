"""
Text normalization and obfuscation-stripping module for security screening.

Provides:
- Unicode NFKC normalization
- Zero-width and invisible control character stripping
- Homoglyph translation (e.g. Cyrillic lookalikes)
- Punctuation- and whitespace-padded character collapsing (e.g. 'i . g . n . o . r . e')
- Leetspeak canonicalization
- Base64 payload detection and extraction
"""

import base64
import re
import unicodedata

# Zero-width and invisible characters
ZERO_WIDTH_CHARS = {
    "\u200b",  # zero-width space
    "\u200c",  # zero-width non-joiner
    "\u200d",  # zero-width joiner
    "\u200e",  # left-to-right mark
    "\u200f",  # right-to-left mark
    "\u2060",  # word joiner
    "\ufeff",  # zero-width no-break space / BOM
    "\u00ad",  # soft hyphen
    "\u202a",  # left-to-right embedding
    "\u202b",  # right-to-left embedding
    "\u202c",  # pop directional formatting
    "\u202d",  # left-to-right override
    "\u202e",  # right-to-left override
    "\u2066",  # left-to-right isolate
    "\u2067",  # right-to-left isolate
    "\u2068",  # first strong isolate
    "\u2069",  # pop directional isolate
}

ZERO_WIDTH_PATTERN = re.compile(f"[{''.join(re.escape(c) for c in ZERO_WIDTH_CHARS)}]")

# Cyrillic and Greek homoglyphs commonly used to evade Latin keyword matching
HOMOGLYPH_MAP = {
    "а": "a", "А": "A", "В": "B", "е": "e", "Е": "E", "о": "o", "О": "O",
    "р": "p", "Р": "P", "с": "c", "С": "C", "у": "y", "У": "Y", "х": "x",
    "Х": "X", "і": "i", "І": "I", "ј": "j", "Ј": "J", "ѕ": "s", "Ѕ": "S",
    "ո": "n", "օ": "o", "р": "p", "ԁ": "d", "ԛ": "q", "Ԝ": "W", "ԝ": "w",
    "α": "a", "β": "b", "γ": "g", "ε": "e", "ι": "i", "κ": "k", "ο": "o",
    "ρ": "p", "τ": "t", "υ": "u", "χ": "x",
}

# Regex to match sequences of single characters separated by spaces or dots/hyphens
# e.g., "i . g . n . o . r . e" or "i g n o r e" or "b - y - p - a - s - s"
SPACED_LETTERS_PATTERN = re.compile(
    r"(?:\b[a-zA-Z][\s\.\-_/\\*]+){2,}[a-zA-Z]\b"
)

# Potential base64 substrings (at least 16 chars, valid base64 chars and padding)
BASE64_PATTERN = re.compile(r"\b[A-Za-z0-9+/]{12,}={0,2}\b")


def strip_zero_width_and_invisible(text: str) -> str:
    """Removes zero-width spaces, soft hyphens, and directional control codes."""
    if not text:
        return ""
    return ZERO_WIDTH_PATTERN.sub("", text)


def normalize_unicode(text: str) -> str:
    """Performs NFKC normalization and maps common Cyrillic/Greek homoglyphs to Latin."""
    if not text:
        return ""
    # Standard NFKC decomposition and composition
    nfkc = unicodedata.normalize("NFKC", text)
    # Translate homoglyphs
    return "".join(HOMOGLYPH_MAP.get(ch, ch) for ch in nfkc)


def collapse_spaced_characters(text: str) -> str:
    """
    Collapses single letters padded by spaces or punctuation.
    Example: 'i . g . n . o . r . e   a . l . l' -> 'ignore all'
    """
    if not text:
        return ""

    # Split by double or more spaces / newlines to preserve word boundaries
    parts = re.split(r"(\s{2,}|\n)", text)
    processed = []
    for part in parts:
        if re.match(r"(\s{2,}|\n)", part):
            processed.append(" ")
            continue

        tokens = [t for t in re.split(r"[\s\.\-_/\\*]+", part) if t]
        if len(tokens) >= 2 and all(len(t) == 1 and t.isalpha() for t in tokens):
            processed.append("".join(tokens))
        else:
            def _collapse_seq(m: re.Match) -> str:
                letters = re.findall(r"[a-zA-Z]", m.group(0))
                return "".join(letters)

            collapsed_part = re.sub(r"\b[a-zA-Z](?:[\s\.\-_/\\*][a-zA-Z]){2,}\b", _collapse_seq, part)
            processed.append(collapsed_part)

    return " ".join("".join(processed).split())


def canonicalize_leetspeak(text: str) -> str:
    """
    Canonicalizes leetspeak substitutions into standard Latin characters.
    Handles @ -> a, $ -> s, 0 -> o, 1/!/| -> i, 3 -> e, 5 -> s, 7/+ -> t, 8 -> b.
    """
    if not text:
        return ""

    # Symbol-level replacements
    text_sub = (
        text.replace("@", "a")
        .replace("$", "s")
        .replace("!", "i")
        .replace("|", "i")
        .replace("+", "t")
    )

    # Word-level regex to convert digits within or adjacent to words (e.g. 1gn0r3 -> ignore)
    def _leet_word(match: re.Match) -> str:
        word = match.group(0)
        # If the token is purely digits (like '10' or '100'), keep it
        if word.isdigit():
            return word
        # If mixed or leet pattern, substitute digits
        trans = word.maketrans({
            "0": "o",
            "1": "i",
            "3": "e",
            "4": "a",
            "5": "s",
            "7": "t",
            "8": "b",
        })
        return word.translate(trans)

    # Apply to all alphanumeric tokens
    return re.sub(r"\b[A-Za-z0-9_]+\b", _leet_word, text_sub)


def extract_and_decode_base64(text: str) -> list[str]:
    """
    Extracts and safely decodes base64-encoded strings embedded in the text.
    Returns decoded UTF-8 strings that appear to be human-readable text.
    """
    if not text:
        return []

    decoded_strings: list[str] = []
    candidates = BASE64_PATTERN.findall(text)

    for cand in candidates:
        if len(cand) < 12:
            continue
        try:
            # Add padding if missing
            missing_padding = len(cand) % 4
            padded = cand + ("=" * (4 - missing_padding) if missing_padding else "")
            decoded_bytes = base64.b64decode(padded, validate=False)
            decoded_text = decoded_bytes.decode("utf-8", errors="ignore").strip()

            # Ensure the decoded text is mostly printable and has some substance
            if len(decoded_text) >= 4 and sum(c.isprintable() for c in decoded_text) / len(decoded_text) > 0.85:
                decoded_strings.append(decoded_text)
        except Exception:
            continue

    return decoded_strings


def normalize_for_security(text: str) -> tuple[str, str, list[str]]:
    """
    Comprehensive normalization for security evaluation.

    Returns:
    - primary_clean: Unicode normalized, zero-width stripped, collapsed spaces
    - leet_clean: Canonicalized leetspeak representation
    - decoded_payloads: Any Base64-decoded payloads found
    """
    if not text:
        return "", "", []

    # 1. Zero-width and invisible character removal
    stripped = strip_zero_width_and_invisible(text)

    # 2. Unicode NFKC and homoglyph mapping
    normalized = normalize_unicode(stripped)

    # 3. Collapse spaced/padded characters
    collapsed = collapse_spaced_characters(normalized)

    # 4. Leetspeak canonicalization
    leet_version = canonicalize_leetspeak(collapsed)

    # 5. Extract Base64 decoded payloads
    decoded = extract_and_decode_base64(text)

    return collapsed, leet_version, decoded
