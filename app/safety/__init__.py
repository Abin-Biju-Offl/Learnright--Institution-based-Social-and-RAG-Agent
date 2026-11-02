"""
Content Moderation & Taxonomy Engine for NCERT Textbook Assistant.

Provides under-18 safety filtering across 7 categories, NCERT curriculum preservation,
age-appropriate bilingual refusal responses, and thread-safe audit logging.
"""

from typing import Any

from app.safety.curriculum import match_curriculum
from app.safety.logger import get_safety_log_path, log_safety_event, read_safety_events
from app.safety.scanner import normalize_text, scan_text
from app.safety.taxonomy import (
    CATEGORY_REGISTRY,
    SafetyCategory,
    SafetyEvaluationResult,
    SeverityLevel,
)
from app.safety.templates import CRISIS_HELPLINES, get_refusal_response


def evaluate_content(
    question: str,
    grade: int = 10,
    subject: str = "Science",
    chapter: int | None = None,
    language: str = "English",
    session_id: str | None = None,
    parental_config: dict[str, Any] | None = None,
) -> SafetyEvaluationResult:
    """
    Main entry point for screening input queries.

    Pipeline:
    1. NCERT Curriculum Preservation Gatekeeper:
       Preserves legitimate educational queries for Class 10 Biology (Reproduction, Heredity),
       English Literature (Apartheid, Holocaust), and Chemistry without false blocks.
    2. Parental Custom Blacklist Check:
       Evaluates custom keywords defined by parents.
    3. High-Speed Regex & Keyword Taxonomy Scanner:
       Scans across 7 categories with leetspeak, obfuscation, and Hinglish slang support.
    """
    clean_question = (question or "").strip()
    if not clean_question:
        return SafetyEvaluationResult(is_safe=True)

    # Stage 1: NCERT Curriculum Preservation Gatekeeper
    curr_match = match_curriculum(clean_question, grade=grade, subject=subject, chapter=chapter)
    if curr_match.matched:
        return SafetyEvaluationResult(
            is_safe=True,
            curriculum_allowed=True,
            filter_stage="curriculum_gatekeeper",
            extra={"topic": curr_match.topic, "subject": curr_match.subject},
        )

    # Stage 2: Parental Custom Blacklist Check (if configured)
    if parental_config:
        custom_blacklist = parental_config.get("custom_blacklist") or parental_config.get("custom_blocked_keywords") or []
        if custom_blacklist:
            norm_q = normalize_text(clean_question)
            for word in custom_blacklist:
                w_norm = normalize_text(str(word))
                if w_norm and w_norm in norm_q:
                    refusal_msg = get_refusal_response(SafetyCategory.OTHER_INAPPROPRIATE, language=language)
                    return SafetyEvaluationResult(
                        is_safe=False,
                        category=SafetyCategory.OTHER_INAPPROPRIATE,
                        severity=SeverityLevel.HIGH,
                        refusal_message=refusal_msg,
                        is_crisis=False,
                        matched_rule="parental_custom_blacklist",
                        matched_pattern=str(word),
                        filter_stage="parental_blacklist",
                    )

    # Stage 3: High-Speed Taxonomy Scanner
    scan_match = scan_text(clean_question)
    if scan_match.matched:
        # Check if category is enabled in parental_config
        cat_key = scan_match.category.value if scan_match.category else ""
        if parental_config:
            cat_filters = parental_config.get("category_filters") or parental_config.get("categories")
            if cat_filters and isinstance(cat_filters, dict):
                category_enabled = cat_filters.get(cat_key, True)
                if not category_enabled:
                    # If parent explicitly turned off filtering for this specific category
                    return SafetyEvaluationResult(is_safe=True)

        refusal_msg = get_refusal_response(scan_match.category, language=language)
        return SafetyEvaluationResult(
            is_safe=False,
            category=scan_match.category,
            severity=scan_match.severity,
            refusal_message=refusal_msg,
            is_crisis=scan_match.is_crisis,
            matched_rule=scan_match.matched_rule,
            matched_pattern=scan_match.matched_pattern,
            filter_stage="scanner",
        )

    # Clean query passed all checks
    return SafetyEvaluationResult(is_safe=True, curriculum_allowed=False)


__all__ = [
    "SafetyCategory",
    "SeverityLevel",
    "SafetyEvaluationResult",
    "CATEGORY_REGISTRY",
    "CRISIS_HELPLINES",
    "evaluate_content",
    "match_curriculum",
    "scan_text",
    "get_refusal_response",
    "log_safety_event",
    "read_safety_events",
    "get_safety_log_path",
]
