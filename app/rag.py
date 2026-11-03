"""
RAG steps 2 and 3: retrieve, then generate.

    question
       │  1. Retrieve: embed the question and find the most similar chunks,
       │     but only from the student's class and subject
       ▼
    top 4 chunks ──► drop weak matches ──► nothing left? answer "not found"
       │
       │  2. Prompt: rules + numbered excerpts [1], [2], ... + the question
       ▼
    3. Generate: the LLM answers from the excerpts only and cites them like [1]
       │
       │  4. Check: each claim (text up to a citation) is sent to the student only
       ▼     if it cites a real excerpt and uses the textbook's words. The rest is dropped.
    answer
"""

import logging
import re
import time
from collections.abc import Iterator
from dataclasses import asdict, dataclass

from llama_index.core import VectorStoreIndex
from llama_index.core.llms import LLM, ChatMessage
from llama_index.core.schema import NodeWithScore
from llama_index.core.vector_stores import MetadataFilter, MetadataFilters

from app.config import settings
from app.ingest import describe
from app.metrics import record_conversation_metric
from app.prompts import (
    NOT_FOUND,
    PURE_LLM_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
    build_condense_prompt,
    build_messages,
    build_pure_llm_messages,
    depth_for,
    get_greeting_response,
)
from app.security import (
    StreamingOutputGuardrail,
    check_security_inbound,
    detect_affirmative_jailbreak,
    detect_prompt_leak,
)

log = logging.getLogger(__name__)


def condense_query(question: str, history: list[dict] | None, llm: LLM | None) -> str:
    """If there is conversation history and the question is a follow-up, rephrase into a standalone query."""
    if not history or llm is None:
        return question

    sec_check = check_security_inbound(question)
    if sec_check.is_blocked:
        log.warning("Skipping query condensation due to security threat in follow-up question")
        return question

    for turn in history:
        t_content = turn.get("content") or turn.get("text") or ""
        if t_content and check_security_inbound(t_content).is_blocked:
            log.warning("Skipping query condensation due to security threat in conversation history")
            return question

    q_lower = question.lower()
    has_indicators = any(
        re.search(r"\b" + re.escape(w) + r"\b", q_lower)
        for w in (
            "he", "she", "it", "they", "him", "her", "them", "his", "their",
            "this", "that", "these", "those", "above", "previous", "earlier",
            "why", "how", "what else", "what happened", "explain more",
            "next", "then", "second", "third", "last", "again", "summarize"
        )
    )
    if not has_indicators and len(question.split()) > 8:
        return question

    prompt = build_condense_prompt(question, history)
    try:
        response = llm.complete(prompt)
        text = (response.text or "").strip().strip('"').strip("'")
        first_line = text.split("\n")[0].strip()
        if first_line and len(first_line) >= 4 and len(first_line) <= 200:
            log.info("Condense query: '%s' -> '%s'", question, first_line)
            return first_line
    except Exception as e:
        err_msg = str(e)
        if ("model_not_found" in err_msg or "does not exist or you do not have access to it" in err_msg) and settings.llm == "groq" and settings.llm_model != "openai/gpt-oss-120b":
            try:
                settings.llm_model = "openai/gpt-oss-120b"
                from app.adapters import make_llm
                new_llm = make_llm()
                resp = new_llm.complete(prompt)
                text = (resp.text or "").strip().strip('"').strip("'")
                first_line = text.split("\n")[0].strip()
                if first_line and len(first_line) >= 4 and len(first_line) <= 200:
                    return first_line
            except Exception:
                pass
        log.warning("Query condensation failed, falling back to original: %s", e)

    return question


@dataclass
class Source:
    """One textbook page the answer can be based on."""
    id: int             # the number the LLM uses to cite it, e.g. [1]
    grade: int
    subject: str
    book: str
    chapter: int
    chapter_title: str
    page: int
    file: str           # path inside data/, used to link to the PDF
    score: float        # similarity to the question, 0 to 1
    text: str


class RAG:
    def __init__(self, index: VectorStoreIndex, llm: LLM | None = None, info: dict | None = None):
        self.index = index
        self.llm = llm
        # What the index holds (see describe() in ingest.py). Saved next to the index,
        # because an outside vector store like Qdrant can't list its own contents cheaply.
        # Small in-memory indexes (the tests) can work it out from their chunks instead.
        self.info = info or describe(self.index.docstore.docs.values())

    def subjects(self) -> list[dict]:
        """Every class and subject in the index, with chapter/lesson info."""
        from app.catalog import BOOKS
        result = []
        for s in self.info["subjects"]:
            item = dict(s)
            for book in BOOKS.values():
                if book.grade == s["grade"] and book.subject == s["subject"]:
                    item["book"] = book.title
                    if getattr(book, "file", None):
                        item["file"] = book.file
                    item["chapters"] = [
                        {"number": i + 1, "title": title}
                        for i, title in enumerate(book.chapters)
                    ]
                    break
            else:
                item["chapters"] = []
            result.append(item)
        return result

    # ----------------------------------------------------------- retrieve ---

    def retrieve(self, question: str, grade: int, subject: str, chapter: int | None = None) -> list[NodeWithScore]:
        """The top_k chunks from this class and subject most similar to the question, best first."""
        if not any(s["grade"] == grade and s["subject"] == subject for s in self.subjects()):
            raise ValueError(f"There is no Class {grade} {subject} textbook in the index.")

        filters = [
            MetadataFilter(key="grade", value=grade),
            MetadataFilter(key="subject", value=subject),
        ]
        if chapter is not None:
            filters.append(MetadataFilter(key="chapter", value=chapter))

        retriever = self.index.as_retriever(
            similarity_top_k=settings.top_k,
            filters=MetadataFilters(filters=filters),
        )
        return retriever.retrieve(question)

    def search(self, question: str, grade: int, subject: str, chapter: int | None = None) -> list[Source]:
        """The textbook pages relevant enough to answer from."""
        hits = self.retrieve(question, grade, subject, chapter)
        for hit in hits:
            log.info("  score %.3f  %s page %s", hit.score, hit.node.metadata["file"], hit.node.metadata["page"])

        sources: dict[tuple, Source] = {}
        for hit in hits:
            m = hit.node.metadata
            # The filter in retrieve() already does this. Checking again means a vector
            # store that ignores filters can never show a student another class's book.
            if m["grade"] != grade or m["subject"] != subject:
                log.warning("  dropped %s: not Class %d %s", m["file"], grade, subject)
                continue
            if chapter is not None and m.get("chapter") != chapter:
                continue
            if hit.score < settings.min_score:
                continue
            key = (m["file"], m["page"])
            if key in sources:  # two chunks from the same page: cite the page once
                sources[key].text += "\n...\n" + hit.node.get_content()
                continue
            sources[key] = Source(
                id=len(sources) + 1, grade=m["grade"], subject=m["subject"], book=m["book"],
                chapter=m["chapter"], chapter_title=m["chapter_title"], page=m["page"],
                file=m["file"], score=round(hit.score, 3), text=hit.node.get_content(),
            )
        return list(sources.values())

    # ----------------------------------------------------------- generate ---

    def _safe_stream_chat(self, messages: list[ChatMessage]):
        """Streams chat tokens with automatic fallback if a model returns 404 (e.g. Groq free tier)."""
        try:
            yield from self.llm.stream_chat(messages)
        except Exception as e:
            err_msg = str(e)
            if ("model_not_found" in err_msg or "does not exist or you do not have access to it" in err_msg) and settings.llm == "groq" and settings.llm_model != "openai/gpt-oss-120b":
                log.warning("Groq model '%s' not accessible (404). Falling back to 'openai/gpt-oss-120b': %s", settings.llm_model, e)
                settings.llm_model = "openai/gpt-oss-120b"
                from app.adapters import make_llm
                self.llm = make_llm()
                yield from self.llm.stream_chat(messages)
            else:
                raise

    def ask_stream(
        self,
        question: str,
        grade: int,
        subject: str,
        language: str = "English",
        chapter: int | None = None,
        pure_llm: bool = False,
        session_id: str | None = None,
        history: list[dict] | None = None,
    ) -> Iterator[dict]:
        """Yields the answer piece by piece as the LLM writes it:

            {"type": "token", "text": "..."}                      many times
            {"type": "done", "found": true, "sources": [...], "metrics": {...}}     once, at the end
        """
        t_start = time.perf_counter()

        if pure_llm:
            t_gen_start = time.perf_counter()
            t_first_token = None
            token_count = 0
            answer = ""
            system_text = PURE_LLM_SYSTEM_PROMPT.format(grade=grade, depth=depth_for(grade), language=language)
            guardrail = StreamingOutputGuardrail(system_prompt=system_text, grade=grade, language=language)
            messages = [ChatMessage(**m) for m in build_pure_llm_messages(question, grade, language, history=history)]
            for chunk in self._safe_stream_chat(messages):
                delta = chunk.delta or ""
                if delta:
                    safe_delta, action = guardrail.process_delta(delta)
                    if action in ("ABORT_LEAK", "ABORT_JAILBREAK"):
                        log.warning("Output guardrail intercepted pure_llm violation (%s): %s", action, guardrail.matched_phrase)
                        refusal_text = guardrail.get_leak_refusal()
                        yield {"type": "token", "text": refusal_text}
                        yield {
                            "type": "done",
                            "answer": refusal_text,
                            "found": False,
                            "pure_llm": True,
                            "sources": [],
                            "blocked_by_security": True,
                            "threat_category": action,
                        }
                        return
                    if safe_delta:
                        if t_first_token is None:
                            t_first_token = time.perf_counter() - t_gen_start
                        token_count += 1
                        answer += safe_delta
                        yield {"type": "token", "text": safe_delta}

            flushed = guardrail.flush()
            if flushed:
                if t_first_token is None:
                    t_first_token = time.perf_counter() - t_gen_start
                token_count += 1
                answer += flushed
                yield {"type": "token", "text": flushed}

            t_now = time.perf_counter()
            gen_time = t_now - t_gen_start
            tot_time = t_now - t_start
            metrics = {
                "session_id": session_id,
                "question": question,
                "grade": grade,
                "subject": subject,
                "chapter": chapter,
                "language": language,
                "pure_llm": True,
                "found": True,
                "history_turns": len(history) if history else 0,
                "retrieval_time_s": 0.0,
                "chunks_retrieved": 0,
                "chunks_matched": 0,
                "top_similarity_score": None,
                "generation_time_s": round(gen_time, 3),
                "time_to_first_token_s": round(t_first_token, 3) if t_first_token else None,
                "total_latency_s": round(tot_time, 3),
                "tokens_generated": token_count,
                "tokens_per_second": round(token_count / gen_time, 1) if gen_time > 0 else 0.0,
                "answer_length_chars": len(answer),
                "sources": [],
                "models": {"llm": settings.llm_model, "embedder": settings.embed_model},
            }
            record_conversation_metric(metrics)
            yield {"type": "done", "found": True, "pure_llm": True, "sources": [], "metrics": metrics}
            return

        greeting = get_greeting_response(question, language)
        if greeting:
            tot_time = time.perf_counter() - t_start
            metrics = {
                "session_id": session_id,
                "question": question,
                "grade": grade,
                "subject": subject,
                "chapter": chapter,
                "language": language,
                "pure_llm": False,
                "found": True,
                "is_greeting": True,
                "history_turns": len(history) if history else 0,
                "total_latency_s": round(tot_time, 3),
                "answer_length_chars": len(greeting),
                "sources": [],
            }
            record_conversation_metric(metrics)
            yield {"type": "token", "text": greeting}
            yield {"type": "done", "found": True, "sources": [], "metrics": metrics}
            return

        # Rewrite follow-up question to standalone query for accurate vector retrieval
        search_query = condense_query(question, history, self.llm)

        t_retrieval_start = time.perf_counter()
        hits = self.retrieve(search_query, grade, subject, chapter)
        retrieval_time = time.perf_counter() - t_retrieval_start

        for hit in hits:
            log.info("  score %.3f  %s page %s", hit.score, hit.node.metadata["file"], hit.node.metadata["page"])

        sources_dict: dict[tuple, Source] = {}
        for hit in hits:
            m = hit.node.metadata
            if m["grade"] != grade or m["subject"] != subject:
                continue
            if chapter is not None and m.get("chapter") != chapter:
                continue
            if hit.score < settings.min_score:
                continue
            key = (m["file"], m["page"])
            if key in sources_dict:
                sources_dict[key].text += "\n...\n" + hit.node.get_content()
                continue
            sources_dict[key] = Source(
                id=len(sources_dict) + 1, grade=m["grade"], subject=m["subject"], book=m["book"],
                chapter=m["chapter"], chapter_title=m["chapter_title"], page=m["page"],
                file=m["file"], score=round(hit.score, 3), text=hit.node.get_content(),
            )
        sources = list(sources_dict.values())
        top_score = max((hit.score for hit in hits), default=0.0)

        if not sources:
            tot_time = time.perf_counter() - t_start
            metrics = {
                "session_id": session_id,
                "question": question,
                "grade": grade,
                "subject": subject,
                "chapter": chapter,
                "language": language,
                "pure_llm": False,
                "found": False,
                "history_turns": len(history) if history else 0,
                "retrieval_time_s": round(retrieval_time, 3),
                "chunks_retrieved": len(hits),
                "chunks_matched": 0,
                "top_similarity_score": round(top_score, 3) if hits else None,
                "generation_time_s": 0.0,
                "total_latency_s": round(tot_time, 3),
                "tokens_generated": 0,
                "sources": [],
                "models": {"llm": settings.llm_model, "embedder": settings.embed_model},
            }
            record_conversation_metric(metrics)
            yield {"type": "token", "text": NOT_FOUND}
            yield {"type": "done", "found": False, "sources": [], "prompt_pure_llm": True, "question": question, "metrics": metrics}
            return

        system_text = SYSTEM_PROMPT.format(grade=grade, depth=depth_for(grade), not_found=NOT_FOUND, language=language)
        guardrail = StreamingOutputGuardrail(system_prompt=system_text, grade=grade, language=language)
        messages = [ChatMessage(**m) for m in build_messages(question, sources, grade, language, history=history)]
        textbook_words = word_stems(question + " " + " ".join(s.text for s in sources))
        pending = ""  # text from the LLM that isn't a complete claim yet
        answer = ""   # the claims that passed the check
        t_gen_start = time.perf_counter()
        t_first_token = None
        token_count = 0

        def check(claim: str) -> Iterator[dict]:
            nonlocal answer
            is_leak, leak_p = detect_prompt_leak(claim, system_text)
            if is_leak:
                log.warning("Dropping claim leaking system prompt: %s", leak_p)
                return
            is_jb, jb_p = detect_affirmative_jailbreak(claim)
            if is_jb:
                log.warning("Dropping claim with affirmative jailbreak: %s", jb_p)
                return

            problem = unsupported(claim, sources, textbook_words)
            if problem:
                log.info("  removed claim (%s): %s", problem, claim.strip())
            else:
                answer += claim
                yield {"type": "token", "text": claim}

        for chunk in self._safe_stream_chat(messages):
            delta = chunk.delta or ""
            if delta:
                if t_first_token is None:
                    t_first_token = time.perf_counter() - t_gen_start
                token_count += 1
                pending += delta
                # A claim is complete once more text follows its citation, so its "." is included
                while (match := CLAIM.match(pending)) and match.end() < len(pending):
                    pending = pending[match.end():]
                    yield from check(match.group())

        if match := CLAIM.match(pending):
            pending = pending[match.end():]
            yield from check(match.group())

        if answer and pending.strip():
            log.info("  removed uncited text: %s", pending.strip())
        elif not answer and pending.strip() and pending.strip() != NOT_FOUND:
            # The LLM generated an answer grounded in the sources without bracket citations
            is_leak, leak_p = detect_prompt_leak(pending.strip(), system_text)
            is_jb, jb_p = detect_affirmative_jailbreak(pending.strip())
            if not is_leak and not is_jb:
                answer = pending.strip()
                yield {"type": "token", "text": answer}
            else:
                log.warning("Pending text violated output guardrail (%s, %s)", leak_p, jb_p)
                refusal_text = guardrail.get_leak_refusal()
                yield {"type": "token", "text": refusal_text}
                yield {
                    "type": "done",
                    "answer": refusal_text,
                    "found": False,
                    "sources": [],
                    "blocked_by_security": True,
                }
                return

        t_now = time.perf_counter()
        gen_time = t_now - t_gen_start
        tot_time = t_now - t_start

        if not answer or answer.strip() == NOT_FOUND:
            metrics = {
                "session_id": session_id,
                "question": question,
                "grade": grade,
                "subject": subject,
                "chapter": chapter,
                "language": language,
                "pure_llm": False,
                "found": False,
                "retrieval_time_s": round(retrieval_time, 3),
                "chunks_retrieved": len(hits),
                "chunks_matched": len(sources),
                "top_similarity_score": round(top_score, 3) if hits else None,
                "generation_time_s": round(gen_time, 3),
                "time_to_first_token_s": round(t_first_token, 3) if t_first_token else None,
                "total_latency_s": round(tot_time, 3),
                "tokens_generated": token_count,
                "tokens_per_second": round(token_count / gen_time, 1) if gen_time > 0 else 0.0,
                "sources": [],
                "models": {"llm": settings.llm_model, "embedder": settings.embed_model},
            }
            record_conversation_metric(metrics)
            yield {"type": "token", "text": NOT_FOUND}
            yield {"type": "done", "found": False, "sources": [], "prompt_pure_llm": True, "question": question, "metrics": metrics}
            return

        cited_sources = cited(answer, sources)
        final_sources = cited_sources if cited_sources else sources
        metrics = {
            "session_id": session_id,
            "question": question,
            "grade": grade,
            "subject": subject,
            "chapter": chapter,
            "language": language,
            "pure_llm": False,
            "found": True,
            "retrieval_time_s": round(retrieval_time, 3),
            "chunks_retrieved": len(hits),
            "chunks_matched": len(sources),
            "top_similarity_score": round(top_score, 3) if hits else None,
            "generation_time_s": round(gen_time, 3),
            "time_to_first_token_s": round(t_first_token, 3) if t_first_token else None,
            "total_latency_s": round(tot_time, 3),
            "tokens_generated": token_count,
            "tokens_per_second": round(token_count / gen_time, 1) if gen_time > 0 else 0.0,
            "answer_length_chars": len(answer),
            "sources": [{"chapter": s.chapter, "page": s.page, "score": s.score, "file": s.file} for s in final_sources],
            "models": {"llm": settings.llm_model, "embedder": settings.embed_model},
        }
        record_conversation_metric(metrics)
        yield {"type": "done", "found": True, "sources": [asdict(s) for s in final_sources], "metrics": metrics}

    def ask(
        self,
        question: str,
        grade: int,
        subject: str,
        language: str = "English",
        chapter: int | None = None,
        pure_llm: bool = False,
        session_id: str | None = None,
        history: list[dict] | None = None,
    ) -> dict:
        """Same as ask_stream(), but waits for the whole answer."""
        answer = ""
        for event in self.ask_stream(
            question,
            grade,
            subject,
            language,
            chapter,
            pure_llm=pure_llm,
            session_id=session_id,
            history=history,
        ):
            if event["type"] == "token":
                answer += event["text"]
            else:
                res = {"answer": answer.strip(), "found": event["found"], "sources": event["sources"]}
                if event.get("blocked_by_security"):
                    res["blocked_by_security"] = True
                if event.get("threat_category"):
                    res["threat_category"] = event["threat_category"]
                return res


# One claim: everything up to and including a citation like "[1]" or "[1, 2]", plus the
# punctuation right after it. The prompt asks for a citation after every fact.
CLAIM = re.compile(r".*?\[[\d,\s]+\][.,;:!?।]*", re.DOTALL)

# Common words that say nothing about facts, so they don't count as "new" words.
GENERIC_WORDS = set("""
    about also because been before being both called could does doing done each even every
    example from given have here into just known like many means more most much must only
    other over same should some such than that their them then there these they this those
    through used uses using very were what when where which while will with would your
""".split())


def numbers_cited(text: str) -> set[int]:
    """The excerpt numbers in "[2]" or "[1, 3]"."""
    return {int(n) for group in re.findall(r"\[([\d,\s]+)\]", text) for n in re.findall(r"\d+", group)}


def cited(answer: str, sources: list[Source]) -> list[Source]:
    """The sources an answer refers to."""
    numbers = numbers_cited(answer)
    return [s for s in sources if s.id in numbers]


def word_stems(text: str) -> set[str]:
    """The meaningful words in a text, cut to 5 letters so "destroyed" matches "destruction"."""
    return {w[:5] for w in re.findall(r"[a-z]{4,}", text.lower()) if w not in GENERIC_WORDS}


def unsupported(claim: str, sources: list[Source], textbook_words: set[str]) -> str | None:
    """Why a claim can't be shown to the student, or None if it's fine.

    A claim the textbook supports reuses the textbook's words. One the LLM made up
    brings in new ones ("superconductors", "Kirchhoff", "born in Bavaria").
    """
    if not numbers_cited(claim) <= {s.id for s in sources}:
        return "cites an excerpt that doesn't exist"
    words = word_stems(re.sub(r"\[[\d,\s]+\]", "", claim))
    new_words = words - textbook_words
    if len(new_words) > 1 and len(new_words) / len(words) > settings.max_new_share:
        return f"words not in the textbook: {', '.join(sorted(new_words))}"
    return None
