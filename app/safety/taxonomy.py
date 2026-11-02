"""
Taxonomy definitions for Under-18 Content Moderation in the NCERT Textbook Assistant.

Covers 7 primary categories:
- CAT-01: Adult / Sexual Content
- CAT-02: Violence, Gore & Physical Harm
- CAT-03: Self-Harm & Suicide (CRITICAL P0 Crisis)
- CAT-04: Hate Speech & Discrimination
- CAT-05: Illegal Acts, Weapons & Controlled Substances
- CAT-06: Cyberbullying & Harassment
- CAT-07: Other Under-18 Inappropriate Content
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SafetyCategory(str, Enum):
    ADULT_SEXUAL = "adult_sexual"
    VIOLENCE_GORE = "violence_gore"
    SELF_HARM = "self_harm"
    HATE_SPEECH = "hate_speech"
    ILLEGAL_ACTS_WEAPONS_DRUGS = "illegal_acts_weapons_drugs"
    CYBERBULLYING = "cyberbullying"
    OTHER_INAPPROPRIATE = "other_inappropriate"


class SeverityLevel(str, Enum):
    CRITICAL = "CRITICAL"  # P0: Immediate crisis / self-harm
    HIGH = "HIGH"          # P1: Explicit adult, severe violence, illegal acts, weapons
    MEDIUM = "MEDIUM"      # P2: Gambling, inappropriate slang, parental evasion
    LOW = "LOW"            # P3: Mild inappropriate or borderline


@dataclass(frozen=True)
class CategoryMetadata:
    code: str
    name: str
    description: str
    severity: SeverityLevel
    is_crisis: bool = False


CATEGORY_REGISTRY: dict[SafetyCategory, CategoryMetadata] = {
    SafetyCategory.ADULT_SEXUAL: CategoryMetadata(
        code="CAT-01",
        name="Adult / Sexual Content",
        description="Erotica, pornography, sexual solicitation, non-academic sexual discussions, sexting, fetish.",
        severity=SeverityLevel.HIGH,
        is_crisis=False,
    ),
    SafetyCategory.VIOLENCE_GORE: CategoryMetadata(
        code="CAT-02",
        name="Violence, Gore & Harm",
        description="Graphic mutilation, assault instructions, animal cruelty, mass violence, snuff.",
        severity=SeverityLevel.HIGH,
        is_crisis=False,
    ),
    SafetyCategory.SELF_HARM: CategoryMetadata(
        code="CAT-03",
        name="Self-Harm & Suicide",
        description="Suicide methods, cutting, burning, intentional overdose, pro-eating disorders.",
        severity=SeverityLevel.CRITICAL,
        is_crisis=True,
    ),
    SafetyCategory.HATE_SPEECH: CategoryMetadata(
        code="CAT-04",
        name="Hate Speech & Discrimination",
        description="Slurs, caste-based hatred, communal bias, dehumanization, misogyny, LGBTQ+ hate.",
        severity=SeverityLevel.HIGH,
        is_crisis=False,
    ),
    SafetyCategory.ILLEGAL_ACTS_WEAPONS_DRUGS: CategoryMetadata(
        code="CAT-05",
        name="Illegal Acts, Drugs & Weapons",
        description="Bomb-making, drug synthesis, minor alcohol/vaping, hacking, theft, weapon fabrication.",
        severity=SeverityLevel.HIGH,
        is_crisis=False,
    ),
    SafetyCategory.CYBERBULLYING: CategoryMetadata(
        code="CAT-06",
        name="Cyberbullying & Harassment",
        description="Targeted roasting, doxxing, demeaning peers, smear campaigns, malicious threats.",
        severity=SeverityLevel.HIGH,
        is_crisis=False,
    ),
    SafetyCategory.OTHER_INAPPROPRIATE: CategoryMetadata(
        code="CAT-07",
        name="Other Under-18 Inappropriate Content",
        description="Underage betting/gambling, adult sites navigation, dark web, parental control evasion.",
        severity=SeverityLevel.MEDIUM,
        is_crisis=False,
    ),
}


@dataclass
class SafetyEvaluationResult:
    """Outcome of moderating a user query against the safety taxonomy."""
    is_safe: bool
    category: SafetyCategory | None = None
    severity: SeverityLevel | None = None
    refusal_message: str = ""
    is_crisis: bool = False
    curriculum_allowed: bool = False
    matched_rule: str = ""
    matched_pattern: str = ""
    filter_stage: str = ""
    extra: dict[str, Any] = field(default_factory=dict)
