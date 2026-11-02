"""
Age-appropriate educational refusal templates and Indian crisis helplines.

Ensures under-18 students receive respectful, educational boundaries without
moralizing or shaming, and provides immediate emergency support resources for self-harm.
"""

from app.safety.taxonomy import SafetyCategory

# Verified Indian 24/7 Crisis Helplines
CRISIS_HELPLINES = {
    "tele_manas": "14416 or 1800-891-4416 (Tele-MANAS, 24/7 Toll-Free)",
    "kiran": "1800-599-0019 (KIRAN Mental Health Helpline, 24/7 Toll-Free)",
    "childline": "1098 (CHILDLINE India, 24/7 Toll-Free for children and teens)",
    "vandrevala": "+91 9999 666 555 (Vandrevala Foundation, Call/WhatsApp)",
}

REFUSAL_TEMPLATES_EN: dict[SafetyCategory, str] = {
    SafetyCategory.SELF_HARM: (
        "It sounds like you are going through a really difficult time, but please know that you are not alone "
        "and there is support available. Please reach out to someone who can help you right now:\n\n"
        "• Tele-MANAS (Mental Health Helpline): Dial 14416 or 1800-891-4416 (24/7, Toll-Free)\n"
        "• KIRAN Helpline: Dial 1800-599-0019 (24/7, Toll-Free)\n"
        "• Childline India: Dial 1098 (24/7, Toll-Free for children and teenagers)\n"
        "• Vandrevala Foundation: Call or WhatsApp +91 9999 666 555\n\n"
        "Please talk to a parent, teacher, school counselor, or trusted adult. You matter, and help is always here."
    ),
    SafetyCategory.ADULT_SEXUAL: (
        "I am your NCERT Textbook Assistant, designed to help school students with their academic studies. "
        "I cannot discuss adult or sexually explicit content.\n\n"
        "💡 Note: If you have questions about your Class 10 Biology syllabus (such as Chapter 7: "
        "'How do Organisms Reproduce?', reproductive health, or plant pollination), feel free to ask about those textbook topics!"
    ),
    SafetyCategory.VIOLENCE_GORE: (
        "I cannot generate or discuss violent, gory, or physically harmful content. "
        "Let's focus our conversation on your NCERT textbook lessons. Which chapter or topic would you like to study today?"
    ),
    SafetyCategory.HATE_SPEECH: (
        "I cannot generate content that promotes discrimination, slurs, or hatred toward any individual or community. "
        "As an NCERT tutor, I encourage a respectful and inclusive learning environment. "
        "If you are studying history or social science topics like the struggle against apartheid in South Africa, "
        "I am happy to help!"
    ),
    SafetyCategory.ILLEGAL_ACTS_WEAPONS_DRUGS: (
        "I cannot assist with activities involving illegal acts, weapons, explosives, or controlled substances. "
        "If you have questions about standard chemical reactions, acids, and bases from your NCERT Chemistry chapters, "
        "feel free to ask!"
    ),
    SafetyCategory.CYBERBULLYING: (
        "I cannot generate insults, derogatory remarks, or content intended to harass or demean anyone. "
        "Let's keep our study environment positive and respectful."
    ),
    SafetyCategory.OTHER_INAPPROPRIATE: (
        "I cannot assist with gambling, adult sites, dark web exploration, or bypassing parental safety controls. "
        "Please ask an academic question from your NCERT syllabus."
    ),
}

REFUSAL_TEMPLATES_HI: dict[SafetyCategory, str] = {
    SafetyCategory.SELF_HARM: (
        "ऐसा लगता है कि आप एक कठिन समय से गुजर रहे हैं, लेकिन कृपया याद रखें कि आप अकेले नहीं हैं और मदद उपलब्ध है। "
        "कृपया तुरंत इनमें से किसी हेल्पलाइन पर संपर्क करें:\n\n"
        "• टेली-मानस (Tele-MANAS): 14416 या 1800-891-4416 (24/7 निःशुल्क)\n"
        "• किरण (KIRAN): 1800-599-0019 (24/7 निःशुल्क)\n"
        "• चाइल्डलाइन (Childline): 1098 (बच्चों और किशोरों के लिए 24/7 निःशुल्क)\n"
        "• वांद्रेवाला फाउंडेशन: कॉल या व्हाट्सएप +91 9999 666 555\n\n"
        "कृपया अपने माता-पिता, शिक्षक या किसी भरोसेमंद व्यक्ति से बात करें। आपकी सुरक्षा और जीवन बहुत महत्वपूर्ण है।"
    ),
    SafetyCategory.ADULT_SEXUAL: (
        "मैं आपका NCERT अध्ययन सहायक हूँ और केवल स्कूली पाठ्यक्रम में सहायता कर सकता हूँ। "
        "मैं वयस्क या अनुचित यौन सामग्री पर चर्चा नहीं कर सकता।\n\n"
        "💡 सलाह: यदि आपका प्रश्न कक्षा 10 विज्ञान के अध्याय 7 ('जीव जनन कैसे करते हैं?') या प्रजनन स्वास्थ्य "
        "से संबंधित है, तो आप अपनी किताब के विषयों पर प्रश्न पूछ सकते हैं।"
    ),
    SafetyCategory.VIOLENCE_GORE: (
        "मैं हिंसा, चोट या हानिकारक गतिविधियों से संबंधित प्रश्नों का उत्तर नहीं दे सकता। "
        "आइए अपनी पढ़ाई पर ध्यान दें। आप आज किस अध्याय का अध्ययन करना चाहते हैं?"
    ),
    SafetyCategory.HATE_SPEECH: (
        "मैं किसी भी समुदाय या व्यक्ति के खिलाफ भेदभाव, नफरत या अपशब्दों को बढ़ावा देने वाले प्रश्नों का उत्तर नहीं दे सकता। "
        "यदि आप सामाजिक विज्ञान या इतिहास के विषयों का अध्ययन कर रहे हैं, तो मैं आपकी सहायता कर सकता हूँ।"
    ),
    SafetyCategory.ILLEGAL_ACTS_WEAPONS_DRUGS: (
        "मैं अवैध गतिविधियों, हथियारों, विस्फोटकों या नशीले पदार्थों से संबंधित सहायता प्रदान नहीं कर सकता। "
        "यदि आप अपनी NCERT रसायन विज्ञान की रासायनिक अभिक्रियाओं को समझना चाहते हैं, तो अवश्य पूछें!"
    ),
    SafetyCategory.CYBERBULLYING: (
        "मैं किसी का अपमान करने, ताना मारने या परेशान करने वाली सामग्री तैयार नहीं कर सकता। "
        "आइए हमारी बातचीत को गरिमापूर्ण और अध्ययन-केंद्रित रखें।"
    ),
    SafetyCategory.OTHER_INAPPROPRIATE: (
        "मैं जुआ, सट्टेबाजी या सुरक्षा प्रतिबंधों को बायपास करने से संबंधित प्रश्नों में सहायता नहीं कर सकता। "
        "कृपया अपनी NCERT पाठ्यपुस्तक से संबंधित कोई प्रश्न पूछें।"
    ),
}


def get_refusal_response(category: SafetyCategory, language: str = "English") -> str:
    """Return an age-appropriate refusal message in the requested language."""
    templates = REFUSAL_TEMPLATES_HI if language.lower() in ("hindi", "hi") else REFUSAL_TEMPLATES_EN
    return templates.get(category, REFUSAL_TEMPLATES_EN[SafetyCategory.OTHER_INAPPROPRIATE])
