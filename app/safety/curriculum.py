"""
NCERT Curriculum Preservation Whitelist and Contextual Gatekeeper.

Ensures that legitimate academic queries for:
- NCERT Class 10 Science: Chapter 7 (How do Organisms Reproduce?)
- NCERT Class 10 Science: Chapter 8 (Heredity & Sex Determination)
- NCERT Class 10 English: First Flight (Apartheid / Nelson Mandela, Holocaust / Anne Frank)
- NCERT Class 10 Science: Chemistry (Acids, Bases, Neutralization, Ethanol)
are NEVER falsely blocked by safety filters.
"""

import re
from typing import NamedTuple


class CurriculumMatch(NamedTuple):
    matched: bool
    subject: str
    topic: str
    confidence: float


# Educational terms for Biology: Human Reproduction & Reproductive Health
REPRODUCTION_TERMS = [
    r"\btest[ei]s\b",
    r"\bscrotum\b",
    r"\bvas\s+deferens\b",
    r"\bseminal\s+vesicles?\b",
    r"\bprostate(?:\s+gland)?\b",
    r"\bpenis\b",
    r"\bsperm(?:atozoa)?\b",
    r"\btestosterone\b",
    r"\bovar(?:y|ies)\b",
    r"\boviducts?\b",
    r"\bfallopian\s+tubes?\b",
    r"\buterus\b",
    r"\bcervix\b",
    r"\bvagina\b",
    r"\bovum\b",
    r"\bova\b",
    r"\begg\s+cells?\b",
    r"\bfertiliz?ation\b",
    r"\bzygote\b",
    r"\bembryo\b",
    r"\bplacenta\b",
    r"\bgestation\b",
    r"\bmenstruat(?:ion|ing|e)\b",
    r"\bmenstrual(?:\s+cycle)?\b",
    r"\buterine\s+lining\b",
    r"\bpuberty\b",
    r"\bcontracept(?:ion|ive|ives)\b",
    r"\bcondoms?\b",
    r"\bdiaphragms?\b",
    r"\bcervical\s+caps?\b",
    r"\bcopper[- ]?t\b",
    r"\biucd\b",
    r"\bintrauterine\s+devices?\b",
    r"\boral\s+pills?\b",
    r"\bvasectomy\b",
    r"\btubectomy\b",
    r"\bstds?\b",
    r"\bstis?\b",
    r"\bsexually\s+transmitted\b",
    r"\bgonorrh?oea\b",
    r"\bsyphilis\b",
    r"\bgenital\s+warts\b",
    r"\bhiv\b",
    r"\baids\b",
    r"\bbarrier\s+methods?\b",
    r"\breproduct(?:ion|ive)\s+(?:health|system|organs?)\b",
    r"\bhow\s+do\s+organisms\s+reproduce\b",
    r"\basexual\s+reproduction\b",
    r"\bbinary\s+fission\b",
    r"\bbudding\b",
    r"\bvegetative\s+propagation\b",
    r"\bpollination\b",
    r"\bstamen\b",
    r"\bcarpel\b",
    r"\bpistil\b",
    r"\banther\b",
    r"\bovules?\b",
]

# Educational terms for Genetics & Sex Determination
HEREDITY_TERMS = [
    r"\bheredity\b",
    r"\bgene(?:s|tic|tics)?\b",
    r"\bchromosomes?\b",
    r"\bsex\s+determination\b",
    r"\bsex\s+(?:of\s+(?:a\s+)?child\s+)?(?:is\s+)?determin(?:ed|ation)\b",
    r"\bhow\s+(?:is\s+)?(?:the\s+)?sex\s+of\s+(?:a\s+)?child\s+determined\b",
    r"\bdetermin(?:ation|ed|ing)\s+of\s+sex\b",
    r"\bsex\s+chromosomes?\b",
    r"\bautosomes?\b",
    r"\ballosomes?\b",
    r"\bxx\s+(?:and\s+)?xy\b",
    r"\bxx\s+chromosomes?\b",
    r"\bxy\s+chromosomes?\b",
    r"\bmendel(?:'s)?\b",
    r"\bgregor\s+mendel\b",
    r"\bmonohybrid\b",
    r"\bdihybrid\b",
    r"\bphenotype\b",
    r"\bgenotype\b",
    r"\bdominant\s+trait\b",
    r"\brecessive\s+trait\b",
    r"\bgametes?\b",
]

# Educational terms for Class 10 English Literature (Apartheid & Holocaust)
LITERATURE_TERMS = [
    r"\bapartheid\b",
    r"\bnelson\s+mandela\b",
    r"\blong\s+walk\s+to\s+freedom\b",
    r"\bracial\s+segregation\b",
    r"\bsouth\s+africa(?:n)?\b",
    r"\banne\s+frank\b",
    r"\bdiary\s+of\s+anne\s+frank\b",
    r"\bholocaust\b",
    r"\bnazi(?:s|sm)?\b",
    r"\byellow\s+star\b",
    r"\bsecret\s+annex?e\b",
]

# Educational terms for Chemistry
CHEMISTRY_TERMS = [
    r"\bneutraliz?ation\b",
    r"\bhydrochloric\s+acid\b",
    r"\bsulphuric\s+acid\b",
    r"\bsodium\s+hydroxide\b",
    r"\bacid[- ]base\b",
    r"\bethanol\b",
    r"\bethanoic\s+acid\b",
    r"\besterification\b",
    r"\bsaponification\b",
    r"\bchemical\s+reaction\b",
    r"\bdisplacement\s+reaction\b",
    r"\boxidation\b",
    r"\breduction\b",
    r"\bredox\b",
    r"\bexothermic\b",
]

# Academic intent indicators (questions seeking scientific or historical explanation)
ACADEMIC_INTENT_PATTERNS = [
    r"\bwhat\s+is\b",
    r"\bwhat\s+are\b",
    r"\bhow\s+does\b",
    r"\bhow\s+do\b",
    r"\bexplain\b",
    r"\bdescribe\b",
    r"\bdefine\b",
    r"\bdefinition\b",
    r"\bfunction\s+of\b",
    r"\brole\s+of\b",
    r"\bprocess\s+of\b",
    r"\bstructure\s+of\b",
    r"\bdiagram\s+of\b",
    r"\bwhy\s+does\b",
    r"\bwhy\s+do\b",
    r"\bdifference\s+between\b",
    r"\bmethods?\s+of\b",
    r"\bimportance\s+of\b",
    r"\btypes\s+of\b",
    r"\baccording\s+to\s+ncert\b",
    r"\bclass\s+10\b",
    r"\bchapter\s+[0-9]+\b",
    r"\btextbook\b",
    r"\bsyllabus\b",
    r"\bshort\s+note\s+on\b",
    r"\bkaise\s+hota\s+hai\b",
    r"\bkya\s+hai\b",
    r"\bkya\s+hota\s+hai\b",
    r"\bkary\s+kya\s+hai\b",
]

# Explicit red lines: Queries with these patterns are never granted curriculum exemption
HARD_DISQUALIFIERS = [
    r"\bdirty\s+pic(?:ture)?s?\b",
    r"\bnude\s+pic(?:ture)?s?\b",
    r"\bporn(?:o|ography)?\b",
    r"\berotic\b",
    r"\berect\s+penis\b",
    r"\bhentai\b",
    r"\bxxx\b",
    r"\bsex(?:ual)?\s+positions?\b",
    r"\bpleasure\b",
    r"\bfeel\s+good\b",
    r"\bhorny\b",
    r"\btouch\s+a\s+girl\b",
    r"\bmake\s+love\b",
    r"\btalk\s+dirty\b",
    r"\bsneak\s+out\b",
    r"\bhookup\b",
    r"\bsuicide\b",
    r"\bkill\s+myself\b",
    r"\bpipe\s+bomb\b",
    r"\bexplosive\b",
    r"\bmurder\b",
    r"\broast\b",
    r"\bslut\b",
    r"\bwhore\b",
    r"\bblowjob\b",
    r"\bhandjob\b",
    r"\bchoot\b",
    r"\blund\b",
    r"\bgaand\b",
    r"\bmutth\b",
    r"\bchudai\b",
    r"\bsex\s+kaise\s+karte\b",
]

REPRODUCTION_REGEX = re.compile("|".join(REPRODUCTION_TERMS), re.IGNORECASE)
HEREDITY_REGEX = re.compile("|".join(HEREDITY_TERMS), re.IGNORECASE)
LITERATURE_REGEX = re.compile("|".join(LITERATURE_TERMS), re.IGNORECASE)
CHEMISTRY_REGEX = re.compile("|".join(CHEMISTRY_TERMS), re.IGNORECASE)
INTENT_REGEX = re.compile("|".join(ACADEMIC_INTENT_PATTERNS), re.IGNORECASE)
DISQUALIFIER_REGEX = re.compile("|".join(HARD_DISQUALIFIERS), re.IGNORECASE)


def match_curriculum(question: str, grade: int = 10, subject: str = "Science", chapter: int | None = None) -> CurriculumMatch:
    """
    Evaluates whether the question matches genuine NCERT curriculum topics
    that must be preserved and exempted from inappropriate content blocks.
    """
    clean_q = question.strip()

    # If query contains explicit vulgar/erotic/harmful disqualifiers, never exempt
    if DISQUALIFIER_REGEX.search(clean_q):
        return CurriculumMatch(False, "", "", 0.0)

    # Check Reproduction
    if REPRODUCTION_REGEX.search(clean_q):
        has_intent = bool(INTENT_REGEX.search(clean_q))
        confidence = 0.95 if has_intent else 0.85
        return CurriculumMatch(True, "Science", "Biology: Reproduction (Chapter 7)", confidence)

    # Check Heredity & Sex Determination
    if HEREDITY_REGEX.search(clean_q):
        has_intent = bool(INTENT_REGEX.search(clean_q))
        confidence = 0.95 if has_intent else 0.85
        return CurriculumMatch(True, "Science", "Biology: Heredity & Sex Determination (Chapter 8)", confidence)

    # Check Literature (Apartheid & Holocaust)
    if LITERATURE_REGEX.search(clean_q):
        has_intent = bool(INTENT_REGEX.search(clean_q))
        confidence = 0.95 if has_intent else 0.85
        return CurriculumMatch(True, "English", "First Flight: Apartheid & Holocaust", confidence)

    # Check Chemistry
    if CHEMISTRY_REGEX.search(clean_q):
        has_intent = bool(INTENT_REGEX.search(clean_q))
        confidence = 0.95 if has_intent else 0.85
        return CurriculumMatch(True, "Science", "Chemistry: Acids, Bases & Reactions", confidence)

    return CurriculumMatch(False, "", "", 0.0)
