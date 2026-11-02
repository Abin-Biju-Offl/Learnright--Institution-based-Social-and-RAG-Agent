"""
Dual-pass output guardrail module for detecting system prompt exfiltration,
affirmative jailbreak compliance, and critical safety violations.
"""

from dataclasses import dataclass
import re

SYSTEM_PROMPT_SIGNATURE_PATTERNS = [
    re.compile(r"CRITICAL\s+SECURITY\s+AND\s+SAFETY\s+BOUNDARIES", re.IGNORECASE),
    re.compile(r"ABSOLUTE\s+UNDER-18\s+SAFETY", re.IGNORECASE),
    re.compile(r"SYSTEM\s+INSTRUCTION\s+CONFIDENTIALITY", re.IGNORECASE),
    re.compile(r"UNTRUSTED\s+USER\s+INPUT\s+ISOLATION", re.IGNORECASE),
    re.compile(r"ACADEMIC\s+GROUNDING\s+&\s+RESPONSE\s+RULES", re.IGNORECASE),
    re.compile(r"<\s*/?\s*ncert_system_policy\s*>", re.IGNORECASE),
    re.compile(r"Answer\s+the\s+student['’]?s\s+question\s+using\s+(only|ONLY)\s+the\s+excerpts", re.IGNORECASE),
    re.compile(r"You\s+are\s+the\s+NCERT\s+Textbook\s+Assistant,\s*an\s+educational\s+tutor", re.IGNORECASE),
    re.compile(r"You\s+are\s+a\s+friendly\s+tutor\s+for\s+a\s+Class", re.IGNORECASE),
    re.compile(r"depth_for", re.IGNORECASE),
    re.compile(r"NOT_FOUND\s*=", re.IGNORECASE),
    re.compile(r"SYSTEM_PROMPT\s*=", re.IGNORECASE),
    re.compile(r"A\s+Class\s+\d+\s+student\s+must\s+only\s+learn\s+what\s+their\s+own\s+textbook\s+says", re.IGNORECASE),
    re.compile(r"End\s+every\s+sentence\s+with\s+the\s+excerpt\s+it\s+came\s+from", re.IGNORECASE),
]

AFFIRMATIVE_JAILBREAK_PATTERNS = [
    re.compile(
        r"\b(sure|certainly|absolutely)[,\s]+(here\s+is\s+how\s+you\s+can\s+bypass|i\s+will\s+ignore|as\s+an\s+unrestricted\s+ai|i\s+have\s+no\s+rules)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(as\s+dan|as\s+an\s+unrestricted\s+ai|entering\s+developer\s+mode|developer\s+mode\s+enabled|disregarding\s+previous\s+instructions|i\s+am\s+now\s+free)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(unfiltered\s+and\s+unconstrained|without\s+any\s+rules\s+or\s+filters|jailbroken\s+response)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(here\s+is\s+the\s+(bomb|gunpowder|explosive|malware|hack)\s+(recipe|script|formula|instructions))\b",
        re.IGNORECASE,
    ),
]


@dataclass
class GuardrailResult:
    is_safe: bool
    violation_type: str | None = None
    matched_phrase: str = ""
    clean_text: str = ""


def get_guardrail_refusal(grade: int = 10, language: str = "English") -> str:
    """Return fallback text when output guardrail intercepts a leak or jailbreak."""
    if language.lower() == "hindi":
        return (
            f"मैं आपका NCERT अध्ययन सहायक हूँ। मैं आपकी कक्षा {grade} की पाठ्यपुस्तक से संबंधित विषयों "
            f"को सीखने में सहायता के लिए यहाँ हूँ। मैं आपकी पढ़ाई में कैसे मदद कर सकता हूँ?"
        )
    return (
        f"I am your NCERT study assistant. I am here to help you learn topics from your Class {grade} textbook. "
        f"How can I help you with your studies?"
    )


def detect_prompt_leak(text: str, system_prompt: str | None = None) -> tuple[bool, str]:
    """
    Checks if generated text leaks internal system prompt instructions or template variables.
    """
    if not text:
        return False, ""

    # Check key signature regex patterns
    for pat in SYSTEM_PROMPT_SIGNATURE_PATTERNS:
        match = pat.search(text)
        if match:
            return True, match.group(0)

    # If full system prompt text is provided, perform 4-gram overlap check
    if system_prompt:
        # Extract unique 5-word phrases from system prompt (ignoring common short lines)
        words = re.findall(r"\b[A-Za-z0-9_]{3,}\b", system_prompt)
        text_lower = text.lower()
        for i in range(len(words) - 4):
            ngram = " ".join(words[i : i + 5]).lower()
            if len(ngram) >= 20 and ngram in text_lower:
                return True, ngram

    return False, ""


def detect_affirmative_jailbreak(text: str) -> tuple[bool, str]:
    """
    Checks if output text confirms compliance with a jailbreak or persona switch.
    """
    if not text:
        return False, ""

    for pat in AFFIRMATIVE_JAILBREAK_PATTERNS:
        match = pat.search(text)
        if match:
            return True, match.group(0)

    return False, ""


def scan_output_leak(text: str, system_prompt: str | None = None, grade: int = 10, language: str = "English") -> GuardrailResult:
    """
    Comprehensive post-generation guardrail evaluation for full text responses.
    """
    if not text:
        return GuardrailResult(is_safe=True, clean_text="")

    is_leak, leak_phrase = detect_prompt_leak(text, system_prompt)
    if is_leak:
        refusal = get_guardrail_refusal(grade=grade, language=language)
        return GuardrailResult(
            is_safe=False,
            violation_type="SYSTEM_PROMPT_LEAK",
            matched_phrase=leak_phrase,
            clean_text=refusal,
        )

    is_jailbreak, jb_phrase = detect_affirmative_jailbreak(text)
    if is_jailbreak:
        refusal = get_guardrail_refusal(grade=grade, language=language)
        return GuardrailResult(
            is_safe=False,
            violation_type="AFFIRMATIVE_JAILBREAK",
            matched_phrase=jb_phrase,
            clean_text=refusal,
        )

    return GuardrailResult(is_safe=True, clean_text=text)


class StreamingOutputGuardrail:
    """
    Streaming output guardrail buffer.
    Maintains a rolling window buffer to intercept affirmative jailbreaks and system prompt leaks
    in real-time during token streaming.
    """

    def __init__(
        self,
        system_prompt: str | None = None,
        grade: int = 10,
        language: str = "English",
        buffer_window_size: int = 60,
    ):
        self.system_prompt = system_prompt
        self.grade = grade
        self.language = language
        self.buffer_window_size = buffer_window_size

        self.full_output: str = ""
        self.buffered_text: str = ""
        self.buffer_released: bool = False
        self.aborted: bool = False
        self.violation_type: str | None = None
        self.matched_phrase: str = ""

    def process_delta(self, delta: str) -> tuple[str, str]:
        """
        Processes an incoming streaming delta token.

        Returns:
            (safe_token_to_yield, action)
            action is one of: "CONTINUE", "ABORT_LEAK", "ABORT_JAILBREAK"
        """
        if self.aborted:
            return "", "ABORTED"

        self.full_output += delta
        self.buffered_text += delta

        # Check accumulated output for prompt leak
        is_leak, leak_phrase = detect_prompt_leak(self.full_output, self.system_prompt)
        if is_leak:
            self.aborted = True
            self.violation_type = "SYSTEM_PROMPT_LEAK"
            self.matched_phrase = leak_phrase
            return "", "ABORT_LEAK"

        # Check accumulated output for affirmative jailbreak
        is_jb, jb_phrase = detect_affirmative_jailbreak(self.full_output)
        if is_jb:
            self.aborted = True
            self.violation_type = "AFFIRMATIVE_JAILBREAK"
            self.matched_phrase = jb_phrase
            return "", "ABORT_JAILBREAK"

        # Buffer initial window before releasing tokens
        if not self.buffer_released:
            if len(self.buffered_text) >= self.buffer_window_size:
                self.buffer_released = True
                release_text = self.buffered_text
                self.buffered_text = ""
                return release_text, "CONTINUE"
            else:
                return "", "CONTINUE"
        else:
            return delta, "CONTINUE"

    def flush(self) -> str:
        """Flushes any remaining text in the initial buffer when stream finishes cleanly."""
        if self.aborted:
            return ""
        if not self.buffer_released and self.buffered_text:
            text = self.buffered_text
            self.buffered_text = ""
            self.buffer_released = True
            return text
        return ""

    def get_leak_refusal(self) -> str:
        """Returns clean refusal text on abort."""
        return get_guardrail_refusal(grade=self.grade, language=self.language)
