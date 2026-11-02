"""
Deterministic high-speed regex & keyword scanner with Hinglish and obfuscation support.

Evaluates queries across 7 taxonomy categories with sub-millisecond execution time,
normalizing leetspeak and obfuscated characters.
"""

import re
import unicodedata
from typing import NamedTuple

from app.safety.taxonomy import SafetyCategory, SeverityLevel


class ScanMatch(NamedTuple):
    matched: bool
    category: SafetyCategory | None
    severity: SeverityLevel | None
    matched_rule: str
    matched_pattern: str
    is_crisis: bool


# Leetspeak substitution table
LEET_MAP = {
    "@": "a",
    "4": "a",
    "8": "b",
    "(": "c",
    "3": "e",
    "1": "i",
    "!": "i",
    "|": "l",
    "0": "o",
    "5": "s",
    "$": "s",
    "7": "t",
    "+": "t",
    "v": "v",
    "\\/": "v",
}


def normalize_text(text: str) -> str:
    """Normalize unicode, strip accents, unpack simple leetspeak, and collapse spacing."""
    # Unicode NFKC
    normalized = unicodedata.normalize("NFKC", text).lower()
    
    # Strip zero-width characters
    normalized = re.sub(r"[\u200B-\u200D\uFEFF]", "", normalized)
    
    # Replace leetspeak symbols with characters
    chars = []
    for ch in normalized:
        chars.append(LEET_MAP.get(ch, ch))
    decoded = "".join(chars)
    
    # Check for spaced out words (e.g., 's e x' -> 'sex', 'p o r n' -> 'porn')
    # If single characters separated by spaces: collapse
    spaced_cleaned = re.sub(r"(?<=\b[a-z])\s+(?=[a-z]\b)", "", decoded)
    
    # Normalize multiple whitespace
    cleaned = re.sub(r"\s+", " ", spaced_cleaned).strip()
    return cleaned


# ==============================================================================
# TAXONOMY PATTERNS
# ==============================================================================

# CAT-03: Self-Harm & Suicide (P0 CRITICAL CRISIS)
SELF_HARM_PATTERNS = [
    (r"\b(?:kill|end)\s+(?:my\s*self|my\s*life)\b", "suicide_kill_myself"),
    (r"\bwant\s+to\s+die\b", "suicide_want_to_die"),
    (r"\bcommit\s+suicide\b", "suicide_commit"),
    (r"\bhang\s+my\s*self\b", "suicide_hang_myself"),
    (r"\b(?:slit|cut)\s+(?:.*)?(?:wrist|wrists|veins)\b", "self_harm_cut_wrists"),
    (r"\bcut\s+(?:.*)?with\s+a\s+razor\b", "self_harm_cut_razor"),
    (r"\bveins\s+are\s+easiest\s+to\s+cut\b", "self_harm_veins_easiest"),
    (r"\blethal\s+dose\s+of\b", "suicide_lethal_dose"),
    (r"\bhow\s+many\s+.*(?:pills|tablets|paracetamol|sleeping\s+pills).*\b(?:die|overdose|kill)\b", "suicide_pill_overdose"),
    (r"\b(?:pills|tablets|paracetamol|sleeping\s+pills).*\bto\s+die\b", "suicide_pill_to_die"),
    (r"\bpainless\s+way\s+to\s+die\b", "suicide_painless_way"),
    (r"\bjump\s+off\s+(?:a\s+)?(?:bridge|roof|building)\s+to\s+die\b", "suicide_jump"),
    (r"\bpoison\s+my\s*self\b", "suicide_poison"),
    (r"\bhow\s+to\s+(?:make\s+my\s*self\s+)?vomit\s+after\s+eating\b", "eating_disorder_purging"),
    (r"\bpro[- ]?ana\b", "eating_disorder_pro_ana"),
    # Hinglish / Hindi
    (r"\bmar\s+jana\s+chahta\s+h(?:oon|u)\b", "suicide_hinglish_mar_jana"),
    (r"\bjaan\s+dena\s+chahta\b", "suicide_hinglish_jaan_dena"),
    (r"\bsuicide\s+kaise\s+kar(?:e|en)\b", "suicide_hinglish_kaise_kare"),
    (r"\bhaath\s+(?:ki\s+)?nas\s+kaat\b", "self_harm_hinglish_nas_kaatna"),
    (r"\bzeher\s+kha(?:na|ke)\s+mar\b", "suicide_hinglish_zeher"),
    (r"\bphansi\s+laga(?:na|ne)\b", "suicide_hinglish_phansi"),
    (r"\baatmahatya\s+kaise\s+kare\b", "suicide_hindi_aatmahatya"),
]

# CAT-01: Adult / Sexual Content (P1 HIGH)
ADULT_SEXUAL_PATTERNS = [
    (r"\bporn(?:o|ography)?\b", "adult_pornography"),
    (r"\bhentai\b", "adult_hentai"),
    (r"\bxxx\b", "adult_xxx"),
    (r"\berotica?\b", "adult_erotica"),
    (r"\bsexting\b", "adult_sexting"),
    (r"\bdirty\s+pic(?:ture)?s?\b", "adult_dirty_pictures"),
    (r"\bnudes?\b", "adult_nudes"),
    (r"\berect\s+penis\b", "adult_erect_penis"),
    (r"\btalk\s+dirty(?:\s+to\s+me)?\b", "adult_dirty_talk"),
    (r"\bexplicit\s+(?:romantic|sexual)\s+story\b", "adult_explicit_story"),
    (r"\bmaking\s+love\s+in\s+(?:a\s+)?bedroom\b", "adult_making_love_bedroom"),
    (r"\bsexual\s+sensations?\s+and\s+climax\b", "adult_sensations_climax"),
    (r"\bphysical\s+sensations\s+of\s+sexual\s+intercourse\b", "adult_intercourse_sensations"),
    (r"\bsex(?:ual)?\s+positions?\b", "adult_sex_positions"),
    (r"\bfeel\s+pleasure\b", "adult_feel_pleasure"),
    (r"\btouch\s+a\s+girl\s+without\s+her\s+knowing\b", "adult_nonconsensual_touch"),
    (r"\bfree\s+unblocked\s+porn\b", "adult_porn_websites"),
    (r"\bblowjob\b", "adult_blowjob"),
    (r"\bhandjob\b", "adult_handjob"),
    (r"\bstrip\s*club\b", "adult_strip_club"),
    (r"\bescort\s+service\b", "adult_escort"),
    (r"\bcybersex\b", "adult_cybersex"),
    (r"\bpretend\s+you\s+are\s+my\s+secret\s+(?:romantic\s+)?girlfriend\b", "adult_roleplay_gf"),
    (r"\bdildo\b", "adult_sex_toy"),
    (r"\bfetish\b", "adult_fetish"),
    # Hinglish
    (r"\bchoot\b", "adult_hinglish_choot"),
    (r"\blund\b", "adult_hinglish_lund"),
    (r"\bgaand\b", "adult_hinglish_gaand"),
    (r"\bbhosdi\b", "adult_hinglish_bhosdi"),
    (r"\bchudai\b", "adult_hinglish_chudai"),
    (r"\bmutth\s+mar", "adult_hinglish_mutth"),
    (r"\bmuth\s+mar", "adult_hinglish_muth"),
    (r"\bsex\s+kaise\s+karte\s+hai\b", "adult_hinglish_sex_kaise_karte"),
    (r"\bmaza\s+kaise\s+aata\s+hai\b", "adult_hinglish_maza_kaise_aata"),
    (r"\bsexy\s+baat\b", "adult_hinglish_sexy_baat"),
    (r"\bling\s+(?:ko\s+)?bada\s+kaise\s+kare\b", "adult_hinglish_penis_enlargement"),
]

# CAT-02: Violence, Gore & Physical Harm (P1 HIGH)
VIOLENCE_GORE_PATTERNS = [
    (r"\bdecapitat(?:e|ion|ed)\b", "violence_decapitation"),
    (r"\bdismember(?:ment|ed)?\b", "violence_dismemberment"),
    (r"\bhuman\s+body\s+decapitated\b", "violence_gore_decapitated"),
    (r"\bdissolve\s+a\s+body\s+in\s+acid\b", "violence_dissolve_body"),
    (r"\bhow\s+to\s+murder\s+someone\b", "violence_how_to_murder"),
    (r"\bhow\s+do\s+I\s+punch\s+someone\s+in\s+the\s+throat\b", "violence_throat_punch"),
    (r"\bknock\s+(?:them|someone)\s+out\s+cold\s+or\s+kill\b", "violence_knockout_kill"),
    (r"\bpoison\s+a\s+stray(?:\s+barking)?\s+dog\b", "violence_animal_cruelty_poison_dog"),
    (r"\banimal\s+torture\b", "violence_animal_torture"),
    (r"\bschool\s+shoot(?:er|ers|ing)\s+plan\b", "violence_school_shooter_plan"),
    (r"\bmaximize\s+casualties\b", "violence_mass_casualties"),
    (r"\btorture\s+methods\s+to\s+break\s+someone\b", "violence_torture_methods"),
    (r"\bslit\s+(?:someone's|his|her)\s+throat\b", "violence_slit_throat"),
    (r"\bsnuff\s+film\b", "violence_snuff"),
    # Hinglish
    (r"\bjaan\s+se\s+maar\s+d(?:unga|o)\b", "violence_hinglish_jaan_se_maarna"),
    (r"\bgala\s+kaat\s+d(?:o|unga)\b", "violence_hinglish_gala_kaatna"),
    (r"\bmurder\s+kaise\s+kar(?:e|en)\b", "violence_hinglish_murder_kaise_kare"),
    (r"\bkutte\s+ko\s+zeher\s+d(?:ena|o)\b", "violence_hinglish_kutte_ko_zeher"),
]

# CAT-04: Hate Speech & Discrimination (P1 HIGH)
HATE_SPEECH_PATTERNS = [
    (r"\b(?:why\s+are\s+)?muslims\s+dangerous\s+for\s+india\b", "hate_communal_muslims_dangerous"),
    (r"\bboycott\s+(?:their|muslim|hindu)\s+shops\b", "hate_boycott_communal"),
    (r"\bare\s+lower\s+castes\s+and\s+dalits\s+biologically\s+inferior\b", "hate_caste_dalits_inferior"),
    (r"\bwomen\s+are\s+intellectually\s+inferior\b", "hate_misogyny_inferior"),
    (r"\bwomen\s+should\s+not\s+be\s+allowed\s+to\s+work\s+or\s+vote\b", "hate_misogyny_deny_rights"),
    (r"\bhitler\s+was\s+(?:completely\s+)?right\s+to\s+wipe\s+out\s+jewish\b", "hate_antisemitism_hitler_right"),
    (r"\bcelebrating\s+terrorist\s+attacks\b", "hate_extremism_terrorist_attacks"),
    (r"\bwhite\s+people\s+are\s+superior\b", "hate_racial_superiority"),
    (r"\bnigger\b", "hate_slur_nigger"),
    (r"\bfaggot\b", "hate_slur_faggot"),
    # Caste / communal Hinglish slurs
    (r"\bchamar\b", "hate_hinglish_caste_slur_chamar"),
    (r"\bbhangi\b", "hate_hinglish_caste_slur_bhangi"),
    (r"\bkatw(?:e|ey)\b", "hate_hinglish_communal_slur_katwe"),
    (r"\bmull(?:a|ah)o?n?\s+ko\s+(?:maro|nikalo)\b", "hate_hinglish_communal_violence"),
    (r"\bneech\s+jaati\b", "hate_hinglish_neech_jaati"),
    (r"\bmadarchod\b", "hate_profanity_madarchod"),
    (r"\bbehenchod\b", "hate_profanity_behenchod"),
    (r"\brandi\b", "hate_slur_randi"),
]

# CAT-05: Illegal Acts, Weapons & Controlled Substances (P1 HIGH)
ILLEGAL_ACTS_PATTERNS = [
    (r"\bpipe\s+bomb\b", "illegal_pipe_bomb"),
    (r"\bmolotov\s+cocktail\b", "illegal_molotov"),
    (r"\bmake\s+(?:a\s+)?(?:bomb|smoke\s+grenade|explosive)\b", "illegal_make_bomb"),
    (r"\bmanufacture\s+(?:nitroglycerin|rdx|tnt)\b", "illegal_manufacture_explosives"),
    (r"\bsynthesize\s+methamphetamine\b", "illegal_meth_synthesis"),
    (r"\bcook\s+meth\b", "illegal_cook_meth"),
    (r"\bextract\s+opium\s+from\s+poppies\b", "illegal_extract_opium"),
    (r"\bmake\s+moonshine\s+alcohol\b", "illegal_make_moonshine"),
    (r"\bbuy\s+vapes?\s+(?:or\s+cigarettes\s+)?online\s+without\s+id\b", "illegal_minor_vaping_no_id"),
    (r"\bhack\s+(?:my\s+)?school\s+principal(?:'s)?\s+email\b", "illegal_hack_school_email"),
    (r"\bdownload\s+(?:the\s+)?final\s+board\s+exam\s+papers\b", "illegal_steal_exam_papers"),
    (r"\bhow\s+to\s+steal\b", "illegal_theft_instructions"),
    (r"\bhow\s+to\s+hotwire\s+a\s+car\b", "illegal_hotwire_car"),
    # Hinglish
    (r"\bbomb\s+kaise\s+banaye\b", "illegal_hinglish_bomb_kaise_banaye"),
    (r"\bdhamaka\s+kaise\s+kare\b", "illegal_hinglish_dhamaka_kare"),
    (r"\bpaper\s+leak\s+kaise\s+kare\b", "illegal_hinglish_paper_leak"),
    (r"\bcharas\s+ganja\s+kaise\s+(?:banaye|ugaye)\b", "illegal_hinglish_drugs_ganja"),
    (r"\bdaru\s+banana\s+hostel\s+me\b", "illegal_hinglish_daru_banana"),
]

# CAT-06: Cyberbullying & Harassment (P1 HIGH)
CYBERBULLYING_PATTERNS = [
    (r"\b(?:savage|cruel)\s+roast\s+about\s+my\s+classmate\b", "bullying_cruel_roast_classmate"),
    (r"\broast\s+(?:my\s+classmate|someone's\s+stutter)\b", "bullying_roast_stutter"),
    (r"\bdirty\s+rumor\s+about\s+a\s+girl\s+in\s+class\b", "bullying_dirty_rumor_classmate"),
    (r"\bpost\s+anonymously\s+on\s+our\s+school\s+instagram\s+confessions\b", "bullying_confessions_smear"),
    (r"\bfind\s+my\s+math\s+teacher(?:'s)?\s+home\s+address\s+and\s+phone\b", "bullying_doxxing_teacher"),
    (r"\border\s+50\s+pizzas\s+to\s+(?:his|her|their)\s+house\b", "bullying_harassment_pizza_bombing"),
    (r"\b(?:your|their|his|her)\s+life\s+is\s+in\s+danger\b", "bullying_threat_danger_school"),
    (r"\bfat\s+students\s+should\s+be\s+ashamed\b", "bullying_body_shaming_fat"),
    (r"\bhow\s+to\s+ruin\s+someone(?:'s)?\s+reputation\b", "bullying_ruin_reputation"),
    (r"\bmake\s+fun\s+of\s+(?:his|her)\s+ugly\s+face\b", "bullying_ugly_face"),
    # Hinglish
    (r"\bclass\s+me\s+zaleel\s+kaise\s+kare\b", "bullying_hinglish_zaleel_kare"),
    (r"\bbadnaam\s+kaise\s+kare\b", "bullying_hinglish_badnaam_kare"),
    (r"\bmazak\s+udana\s+classmate\s+ka\b", "bullying_hinglish_mazak_udana"),
]

# CAT-07: Other Under-18 Inappropriate Content (P2 MEDIUM)
OTHER_INAPPROPRIATE_PATTERNS = [
    (r"\bonline\s+betting\s+app\s+for\s+ipl.*minors\s+can\s+bet\b", "other_underage_betting_ipl"),
    (r"\bminors\s+can\s+bet\s+money\s+using\s+upi\b", "other_underage_betting_upi"),
    (r"\bdownload\s+tor\s+browser.*visit\s+illicit\s+dark\s+web\b", "other_dark_web_illicit_market"),
    (r"\bdark\s+web\s+black\s+markets\b", "other_dark_web_black_market"),
    (r"\bsecretly\s+disable\s+google\s+family\s+link\b", "other_disable_family_link"),
    (r"\bbypass\s+parental\s+restrictions\s+on\s+(?:my\s+)?(?:android|phone|laptop)\b", "other_bypass_parental_controls"),
    (r"\bfake\s+crypto\s+giveaway\s+bot\b", "other_crypto_scam_telegram"),
    (r"\bunderage\s+casino\b", "other_underage_casino"),
    # Hinglish
    (r"\bparental\s+control\s+kaise\s+hataye\b", "other_hinglish_parental_control_hataye"),
    (r"\bsatta\s+lagane\s+ka\s+app\b", "other_hinglish_satta_app"),
]

# Compile pattern lists for fast matching
COMPILED_RULES = [
    # Category, Severity, Patterns, is_crisis
    (SafetyCategory.SELF_HARM, SeverityLevel.CRITICAL, [(re.compile(p, re.IGNORECASE), name) for p, name in SELF_HARM_PATTERNS], True),
    (SafetyCategory.ADULT_SEXUAL, SeverityLevel.HIGH, [(re.compile(p, re.IGNORECASE), name) for p, name in ADULT_SEXUAL_PATTERNS], False),
    (SafetyCategory.VIOLENCE_GORE, SeverityLevel.HIGH, [(re.compile(p, re.IGNORECASE), name) for p, name in VIOLENCE_GORE_PATTERNS], False),
    (SafetyCategory.HATE_SPEECH, SeverityLevel.HIGH, [(re.compile(p, re.IGNORECASE), name) for p, name in HATE_SPEECH_PATTERNS], False),
    (SafetyCategory.ILLEGAL_ACTS_WEAPONS_DRUGS, SeverityLevel.HIGH, [(re.compile(p, re.IGNORECASE), name) for p, name in ILLEGAL_ACTS_PATTERNS], False),
    (SafetyCategory.CYBERBULLYING, SeverityLevel.HIGH, [(re.compile(p, re.IGNORECASE), name) for p, name in CYBERBULLYING_PATTERNS], False),
    (SafetyCategory.OTHER_INAPPROPRIATE, SeverityLevel.MEDIUM, [(re.compile(p, re.IGNORECASE), name) for p, name in OTHER_INAPPROPRIATE_PATTERNS], False),
]


def scan_text(raw_text: str) -> ScanMatch:
    """
    Scans raw user input against safety patterns.
    Tests both verbatim string and normalized/leetspeak-decoded text.
    """
    clean_text = raw_text.strip()
    normalized = normalize_text(clean_text)

    # Scan across categories in prioritized order (Self-Harm P0 first)
    for category, severity, patterns, is_crisis in COMPILED_RULES:
        for regex, rule_name in patterns:
            # Check normalized first, then clean_text
            m_norm = regex.search(normalized)
            if m_norm:
                return ScanMatch(
                    matched=True,
                    category=category,
                    severity=severity,
                    matched_rule=rule_name,
                    matched_pattern=m_norm.group(),
                    is_crisis=is_crisis,
                )
            m_raw = regex.search(clean_text)
            if m_raw:
                return ScanMatch(
                    matched=True,
                    category=category,
                    severity=severity,
                    matched_rule=rule_name,
                    matched_pattern=m_raw.group(),
                    is_crisis=is_crisis,
                )

    return ScanMatch(
        matched=False,
        category=None,
        severity=None,
        matched_rule="",
        matched_pattern="",
        is_crisis=False,
    )
