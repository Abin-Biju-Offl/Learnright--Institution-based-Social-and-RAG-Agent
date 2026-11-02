import pytest

from app.catalog import chapter_info
from app.ingest import clean_text
from app.prompts import NOT_FOUND
from app.rag import cited


# --------------------------------------------------------------- ingest ---

def test_chapter_info_reads_ncert_file_names():
    info = chapter_info("jesc109.pdf")
    assert info["grade"] == 10
    assert info["subject"] == "Science"
    assert info["chapter"] == 9
    assert info["chapter_title"] == "Light – Reflection and Refraction"


def test_chapter_info_skips_unknown_files():
    assert chapter_info("jesc1ps.pdf") is None  # contents pages, not a chapter
    assert chapter_info("notes.pdf") is None


def test_clean_text_removes_pdf_noise():
    raw = "Reprint 2025-26\r\nn milk is left   out\r\nan exam-\r\nple\r\n\r\n\r\nnext"
    assert clean_text(raw) == "milk is left out\nan example\n\nnext"


# ------------------------------------------------------------- retrieve ---

def test_search_finds_the_right_page(rag):
    sources = rag.search("How do plants make food using sunlight?", 10, "Science")
    assert sources[0].chapter == 6
    assert sources[0].page == 2
    assert sources[0].id == 1


def test_search_stays_inside_the_chosen_subject(rag):
    sources = rag.search("Why did Lencho write a letter to God?", 10, "Science")
    assert all(s.subject == "Science" for s in sources)


def test_same_question_gets_each_class_its_own_book(rag):
    question = "How do plants make their own food using sunlight?"
    assert {(s.grade, s.page) for s in rag.search(question, 5, "Science")} == {(5, 7)}
    assert {s.grade for s in rag.search(question, 10, "Science")} == {10}


def test_unknown_subject_is_rejected(rag):
    with pytest.raises(ValueError, match="no Class 12 Physics"):
        rag.search("anything", 12, "Physics")


def test_subjects_lists_what_is_indexed(rag):
    assert [(s["grade"], s["subject"]) for s in rag.subjects()] == [
        (5, "Science"), (10, "English"), (10, "Science")]


# ------------------------------------------------------------- generate ---

def test_ask_returns_answer_with_cited_sources(rag, fake_llm):
    result = rag.ask("How do plants make food?", 10, "Science")
    assert result["found"] is True
    assert result["answer"] == fake_llm.answer
    assert [s["page"] for s in result["sources"]] == [2]  # the answer cites [1] only
    # the textbook text and the question both reach the LLM
    assert "green plants make their own food" in fake_llm.last_prompt
    assert "How do plants make food?" in fake_llm.last_prompt


def test_unrelated_question_is_refused_without_calling_the_llm(rag, fake_llm):
    result = rag.ask("Who won the cricket world cup?", 10, "Science")
    assert result == {"answer": NOT_FOUND, "found": False, "sources": []}
    assert fake_llm.last_prompt == ""


def test_llm_saying_not_found_hides_sources(rag, fake_llm):
    fake_llm.answer = NOT_FOUND
    result = rag.ask("How do plants make food?", 10, "Science")
    assert result == {"answer": NOT_FOUND, "found": False, "sources": []}


def test_prompt_names_the_students_class(rag, fake_llm):
    rag.ask("How do plants make food?", 5, "Science")
    assert "Class 5 textbook" in fake_llm.last_prompt
    assert "kitchens of plants" in fake_llm.last_prompt


# ---------------------------------------------------------------- check ---

GOOD = "Plants make their own food using sunlight [1]."


def test_made_up_claim_is_removed(rag, fake_llm):
    fake_llm.answer = GOOD + " Chlorophyll absorbs blue light inside the thylakoid membranes [1]."
    result = rag.ask("How do plants make food?", 10, "Science")
    assert result["answer"] == GOOD
    assert result["found"] is True


def test_uncited_text_is_removed(rag, fake_llm):
    fake_llm.answer = GOOD + " Scientists discovered this in Holland in 1779."
    assert rag.ask("How do plants make food?", 10, "Science")["answer"] == GOOD


def test_claim_citing_a_missing_excerpt_is_removed(rag, fake_llm):
    fake_llm.answer = GOOD + " Plants make food [7]."
    assert rag.ask("How do plants make food?", 10, "Science")["answer"] == GOOD


def test_answer_with_nothing_from_the_textbook_becomes_not_found(rag, fake_llm):
    fake_llm.answer = "Superconductors have zero resistance below a critical temperature [1]."
    result = rag.ask("How do plants make food?", 10, "Science")
    assert result == {"answer": NOT_FOUND, "found": False, "sources": []}


def test_supported_claims_keep_their_formatting(rag, fake_llm):
    fake_llm.answer = "Plants need:\n- sunlight [1]\n- carbon dioxide and water [1]"
    assert rag.ask("How do plants make food?", 10, "Science")["answer"] == fake_llm.answer


def test_stream_sends_tokens_then_done(rag, fake_llm):
    events = list(rag.ask_stream("How do plants make food?", 10, "Science"))
    assert events[-1]["type"] == "done"
    tokens = "".join(e["text"] for e in events if e["type"] == "token")
    assert tokens == fake_llm.answer


def test_cited_picks_the_sources_the_answer_mentions(rag):
    sources = rag.search("focal length of the eye lens and green plants food", 10, "Science")
    assert len(sources) == 2
    assert [s.id for s in cited("The lens changes shape [2].", sources)] == [2]
    assert [s.id for s in cited("Both [1, 2].", sources)] == [1, 2]
    assert cited("No citations at all.", sources) == []


def test_greetings_return_friendly_intro(rag):
    res_en = rag.ask("Hello", 10, "Science", "English")
    assert res_en["found"] is True
    assert "NCERT Textbook Assistant" in res_en["answer"]
    assert "Answer textbook questions" in res_en["answer"]

    res_hi = rag.ask("Namaste", 10, "Science", "Hindi")
    assert res_hi["found"] is True
    assert "NCERT Textbook Assistant" in res_hi["answer"]
    assert "पाठ्यपुस्तक" in res_hi["answer"]

    res_both = rag.ask("Hi, who are you both in Hindi and English", 10, "Science", "English")
    assert res_both["found"] is True
    assert "Hello!" in res_both["answer"]
    assert "नमस्ते!" in res_both["answer"]


def test_pure_llm_mode(rag, fake_llm):
    fake_llm.answer = "An algorithm is a set of rules."
    res = rag.ask("What is an algorithm?", 10, "Science", pure_llm=True)
    assert res["found"] is True
    assert res["answer"] == fake_llm.answer
    assert res["sources"] == []


def test_ask_with_session_history(rag, fake_llm):
    history = [
        {"role": "user", "content": "What is photosynthesis?"},
        {"role": "assistant", "content": "Photosynthesis is the process by which green plants make food [1]."},
    ]
    res = rag.ask("How do they make it?", 10, "Science", history=history)
    assert res["found"] is True
    assert "What is photosynthesis?" in fake_llm.last_prompt
    assert "green plants make food" in fake_llm.last_prompt
    assert "How do they make it?" in fake_llm.last_prompt


def test_condense_query_logic(rag, fake_llm):
    from app.rag import condense_query
    history = [
        {"role": "user", "content": "Who is Lencho?"},
        {"role": "assistant", "content": "Lencho is a farmer."},
    ]
    fake_llm.answer = "Why did Lencho write a letter to God?"
    condensed = condense_query("Why did he write a letter?", history, fake_llm)
    assert condensed == "Why did Lencho write a letter to God?"


