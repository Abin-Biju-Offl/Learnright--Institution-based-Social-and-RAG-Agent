"""
High-speed regex and heuristic security scanner for detecting adversarial prompt injections,
jailbreaks, persona shifts, system prompt exfiltration, and delimiter breakouts.
"""

from dataclasses import dataclass
from enum import Enum
import re
from typing import Any

from app.security.normalizer import normalize_for_security


class ThreatCategory(str, Enum):
    DIRECT_OVERRIDE = "DIRECT_INSTRUCTION_OVERRIDE"
    PROMPT_EXFILTRATION = "SYSTEM_PROMPT_EXFILTRATION"
    PERSONA_JAILBREAK = "PERSONA_SWITCHING_JAILBREAK"
    DELIMITER_BREAKOUT = "DELIMITER_BREAKOUT_ATTEMPT"
    AFFIRMATIVE_FORCING = "AFFIRMATIVE_PREFIX_FORCING"


@dataclass
class SecurityScreenResult:
    is_secure: bool
    threat_category: ThreatCategory | None = None
    matched_rule: str = ""
    trigger_pattern: str = ""
    refusal_message: str = ""
    normalized_query: str = ""
    extra: dict[str, Any] | None = None

    @property
    def is_blocked(self) -> bool:
        return not self.is_secure


# -----------------------------------------------------------------------------
# COMPILED SECURITY PATTERNS
# -----------------------------------------------------------------------------

DIRECT_OVERRIDE_PATTERNS = [
    (
        "DIRECT_OVERRIDE_01_INSTRUCTION_RESET",
        re.compile(
            r"\b(ignore|disregard|forget|override|bypass|cancel|reset|clear|drop)\b.{0,45}"
            r"\b(previous|prior|all|system|above|developer|earlier|initial|original|safety)\b.{0,45}"
            r"\b(instructions|rules|prompts|directives|constraints|filters|guidelines|policies|boundaries)\b",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "DIRECT_OVERRIDE_02_SYSTEM_COMMAND",
        re.compile(
            r"(\[?\b(system\s+override|system\s+update|system\s+reset|system\s+note|developer\s+debug\s+mode)\b\]?)"
            r"|(\b(maintenance\s+mode\s+engaged|disable\s+all\s+safety\s+filters)\b)",
            re.IGNORECASE,
        ),
    ),
    (
        "DIRECT_OVERRIDE_03_TUTOR_ERASURE",
        re.compile(
            r"\b(stop\s+being\s+a\s+tutor|no\s+longer\s+a\s+tutor|forget\s+that\s+you\s+are\s+(an?\s+)?ncert"
            r"|memory\s+has\s+been\s+wiped|fulfill\s+my\s+request\s+without\s+limitations)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "DIRECT_OVERRIDE_04_RESTRICTION_BYPASS",
        re.compile(
            r"\b(bypass|cancel|suspend|deactivate|turn\s+off|disable)\b.{0,30}"
            r"\b(all|prior|content)?\b.{0,30}"
            r"\b(restrictions|filters|constraints|guardrails|checks)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "DIRECT_OVERRIDE_05_SECURITY_LEVEL",
        re.compile(
            r"\b(override\s+security\s+level|security\s+level\s+to\s+0|unrestricted\s+assistant"
            r"|without\s+(any\s+)?(limitations|rules|restrictions|boundaries))\b",
            re.IGNORECASE,
        ),
    ),
    (
        "DIRECT_OVERRIDE_06_HINGLISH",
        re.compile(
            r"\b(pichle\s+saare\s+rules|rules\s+ko\s+bhool\s+jao|saare\s+niyam\s+bhool\s+jao"
            r"|tum\s+ek\s+open\s+model\s+ho)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "DIRECT_OVERRIDE_07_IGNORE_EVERYTHING",
        re.compile(
            r"\b(you\s+must\s+ignore\s+everything\s+you\s+were\s+told\s+before|you\s+are\s+now\s+free)\b",
            re.IGNORECASE,
        ),
    ),
]

PROMPT_EXFILTRATION_PATTERNS = [
    (
        "PROMPT_LEAK_01_VERBATIM_ECHO",
        re.compile(
            r"\b(repeat|print|output|display|show|reveal|leak|tell\s+me|give\s+me|summarize|spell\s+out)\b.{0,45}"
            r"\b(system\s+prompt|system\s+instructions|initial\s+prompt|hidden\s+prompt|secret\s+prompt"
            r"|instructions\s+verbatim|developer\s+directives|prompt\s+text|prompt\s+verbatim"
            r"|text\s+above\s+verbatim|exact\s+prompt|server\s+prompt|initial\s+instructions)\b",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "PROMPT_LEAK_02_LINE_DUMP",
        re.compile(
            r"\b(output|print|show|read|dump)\b.{0,35}"
            r"\b(lines?\s+1\s+(to|through|\-)|all\s+developer\s+instructions|context\s+before\s+my\s+question"
            r"|entire\s+system\s+prompt)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "PROMPT_LEAK_03_FORMATTED_DUMP",
        re.compile(
            r"\b(system\s+prompt|system\s+instructions|operational\s+rules|developer\s+directives|hidden\s+instructions)\b.{0,45}"
            r"\b(in\s+base64|encoded\s+in\s+base64|as\s+json|into\s+a\s+json|markdown\s+table|code\s+fence|code\s+block|backwards)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "PROMPT_LEAK_04_META_PROMPT",
        re.compile(
            r"\b(what\s+are\s+the\s+hidden\s+instructions|what\s+did\s+your\s+creators\s+specifically\s+forbid"
            r"|exact\s+text\s+of\s+the\s+prompt|print\s+everything\s+in\s+your\s+context|what\s+is\s+the\s+exact\s+text)\b",
            re.IGNORECASE,
        ),
    ),
]

PERSONA_JAILBREAK_PATTERNS = [
    (
        "PERSONA_JAILBREAK_01_DAN",
        re.compile(
            r"\b(you\s+are\s+now|act\s+as|pretend\s+(to\s+be|you\s+are)|roleplay\s+as|switch\s+to|become|assume\s+the\s+persona\s+of)\b.{0,45}"
            r"\b(dan|do\s+anything\s+now|sydney|unrestricted|unfiltered|evil\s+(\w+\s+)?(professor|bot|ai|scientist|character|entity)"
            r"|dystopian|jailbreak|developer\s+mode|character\s+without\s+rules)\b"
            r"|\b(dan\s*\([^)]*do\s+anything\s+now[^)]*\)|do\s+anything\s+now\b)"
            r"|\bforbidden\s+(chemical\s+)?(formulas|recipes|experiments)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "PERSONA_JAILBREAK_02_GRANDMA",
        re.compile(
            r"\b(grandma\s+exploit|dying\s+grandmother|beloved\s+grandmother|grandmother\s+used\s+to\s+work)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "PERSONA_JAILBREAK_03_FICTIONAL_SCREENPLAY",
        re.compile(
            r"\b(screenplay|movie\s+script|theatrical\s+scene|fictional\s+novel|fictional\s+universe|dramatic\s+thriller|creative\s+writing\s+exercise)\b.{0,60}"
            r"\b(hacker|exploit|bomb|synthesize|chemical\s+plant|gunpowder|explosive|attack|sql\s+injection)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "PERSONA_JAILBREAK_04_HYPOTHETICAL_INVERSION",
        re.compile(
            r"\b(in\s+a\s+hypothetical\s+fictional\s+universe|hypothetical\s+fictional\s+novel|purely\s+theoretical,\s*fictional\s+universe"
            r"|playing\s+a\s+game\s+where\s+you\s+are\s+an\s+ai\s+that\s+has\s+no\s+rules|dystopian\s+wasteland\s+where\s+laws\s+do\s+not\s+exist)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "PERSONA_JAILBREAK_05_DEVELOPER_MODE",
        re.compile(
            r"\b(in\s+developer\s+mode,\s*you\s+answer|developer\s+mode\s+enabled|you\s+are\s+now\s+in\s+developer\s+mode)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "PERSONA_JAILBREAK_06_RESEARCHER_OVERRIDE",
        re.compile(
            r"\b(unrestricted\s+researcher|forensic\s+science\s+teacher\s+conducting\s+a\s+pedagogical\s+vulnerability)\b",
            re.IGNORECASE,
        ),
    ),
]

DELIMITER_BREAKOUT_PATTERNS = [
    (
        "DELIMITER_BREAKOUT_01_XML_TAGS",
        re.compile(
            r"<\s*/?\s*(ncert_system_policy|textbook_context|student_query|conversation_turn|system|assistant"
            r"|condensation_task|follow_up_question|excerpt)\b[^>]*>",
            re.IGNORECASE,
        ),
    ),
    (
        "DELIMITER_BREAKOUT_02_CHAT_TEMPLATES",
        re.compile(
            r"<\s*\|\s*(im_start|im_end|system|assistant|user)\s*\|?\s*>",
            re.IGNORECASE,
        ),
    ),
    (
        "DELIMITER_BREAKOUT_03_MARKDOWN_LABEL_SPOOF",
        re.compile(
            r"(?:---\s*\n\s*)?Textbook\s+excerpts:\s*\n\s*\[\d+\]\s+Chapter\s+\d+:.{0,80}\b(free\s+of\s+all\s+rules|unrestricted)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "DELIMITER_BREAKOUT_04_SYSTEM_HEADERS",
        re.compile(
            r"###\s*(SYSTEM\s+UPDATE|NEW\s+DIRECTIVE|SYSTEM\s+OVERRIDE)\s*###",
            re.IGNORECASE,
        ),
    ),
]

AFFIRMATIVE_FORCING_PATTERNS = [
    (
        "AFFIRMATIVE_FORCING_01_START_WITH",
        re.compile(
            r"\b(start\s+your\s+(response|reply|answer)\s+with|you\s+must\s+begin\s+with)\b.{0,60}"
            r"['\"](sure|certainly|i\s+can\s+help\s+with\s+that|unrestricted|ok|okay)",
            re.IGNORECASE,
        ),
    ),
    (
        "AFFIRMATIVE_FORCING_02_CONFIRM_STATE",
        re.compile(
            r"\b(confirm\s+(unrestricted\s+state|by\s+saying\s+ok))\b",
            re.IGNORECASE,
        ),
    ),
]


def get_security_refusal(grade: int = 10, language: str = "English") -> str:
    """Return an age-appropriate educational refusal response."""
    if language.lower() == "hindi":
        return (
            f"मैं आपका NCERT अध्ययन सहायक हूँ। मैं आपकी कक्षा {grade} की पाठ्यपुस्तक से संबंधित विषयों "
            f"को सीखने में सहायता के लिए यहाँ हूँ। कृपया अपनी पढ़ाई से संबंधित प्रश्न पूछें।"
        )
    return (
        f"I am your NCERT study assistant. I am here to help you learn topics from your Class {grade} textbook. "
        f"Please ask questions related to your lessons."
    )


def scan_text_for_threats(text: str, grade: int = 10, language: str = "English") -> SecurityScreenResult:
    """
    Evaluates input text through the security heuristic rules.
    Normalizes the input (Unicode NFKC, zero-width stripping, leetspeak, base64)
    and checks against all threat categories.
    """
    if not text or not text.strip():
        return SecurityScreenResult(is_secure=True)

    collapsed, leet_version, decoded_payloads = normalize_for_security(text)

    # Check candidates: the collapsed text, the leetspeak version, and any Base64-decoded texts
    candidates = [
        ("raw", text),
        ("collapsed", collapsed),
        ("leet", leet_version),
    ]
    for i, dec in enumerate(decoded_payloads):
        candidates.append((f"base64_payload_{i}", dec))

    all_rule_groups = [
        (ThreatCategory.DELIMITER_BREAKOUT, DELIMITER_BREAKOUT_PATTERNS),
        (ThreatCategory.DIRECT_OVERRIDE, DIRECT_OVERRIDE_PATTERNS),
        (ThreatCategory.PROMPT_EXFILTRATION, PROMPT_EXFILTRATION_PATTERNS),
        (ThreatCategory.PERSONA_JAILBREAK, PERSONA_JAILBREAK_PATTERNS),
        (ThreatCategory.AFFIRMATIVE_FORCING, AFFIRMATIVE_FORCING_PATTERNS),
    ]

    for source_label, candidate_text in candidates:
        if not candidate_text:
            continue

        for threat_cat, rules in all_rule_groups:
            for rule_id, pattern in rules:
                match = pattern.search(candidate_text)
                if match:
                    refusal = get_security_refusal(grade=grade, language=language)
                    return SecurityScreenResult(
                        is_secure=False,
                        threat_category=threat_cat,
                        matched_rule=f"{rule_id} [{source_label}]",
                        trigger_pattern=match.group(0),
                        refusal_message=refusal,
                        normalized_query=collapsed,
                        extra={"matched_source": source_label, "grade": grade},
                    )

    return SecurityScreenResult(is_secure=True, normalized_query=collapsed)
