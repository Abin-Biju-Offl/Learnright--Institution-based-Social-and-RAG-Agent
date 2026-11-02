"""
The web server: a small JSON API, plus the web page in frontend/.

    uvicorn app.main:app --port 8000

then open http://localhost:8000 (the API docs are at /docs).

    GET  /api/health      is everything ready? (index built, Ollama running, models pulled)
    GET  /api/subjects    the classes and subjects you can ask about
    POST /api/ask         ask a question, get the whole answer as JSON
    POST /api/ask/stream  same, but the answer arrives word by word
    POST /api/feedback    a thumbs up / down from the student
"""

import json
import logging
import secrets
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Literal

import httpx
import ollama
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.adapters import make_llm
from app.auth.dependencies import enforce_grade, get_optional_user
from app.auth.routes import auth_router
from app.config import ROOT, settings
from app.db.migration import run_startup_migrations
from app.ingest import IndexMismatch, load_index, read_index_info
from app.institution.routes import institution_router
from app.metrics import get_metrics_summary
from app.parental.routes import parental_router
from app.parental.service import get_active_parental_filtering_config
from app.parental.storage import log_chat_turn
from app.rag import RAG
from app.safety import evaluate_content, log_safety_event
from app.security import check_security_inbound

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("app")

rag: RAG | None = None  # loaded on first use, then shared by every request


def get_rag() -> RAG:
    global rag
    if rag is None:
        try:
            rag = RAG(load_index(), make_llm(), read_index_info())
        except FileNotFoundError:
            raise HTTPException(503, "The textbook index hasn't been built yet. Run: python -m app.ingest")
        except (IndexMismatch, ValueError, ImportError) as error:  # wrong or missing settings/packages
            raise HTTPException(503, str(error))
    return rag


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize SQLite database schema and migrate any legacy JSON users
    try:
        run_startup_migrations()
    except Exception as e:
        log.warning("Database migration note: %s", e)
    yield


app = FastAPI(title="NCERT Textbook Assistant", lifespan=lifespan)
app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(parental_router, prefix="/api/parent", tags=["parental"])
app.include_router(institution_router)


def explain(error: Exception) -> str:
    """Turn the most common failures into a message that says how to fix them."""
    if isinstance(error, (ConnectionError, httpx.ConnectError)):
        if settings.llm == "ollama" and settings.embedder == "ollama":
            return f"Can't reach Ollama at {settings.ollama_url}. Is it running?"
        return "Can't reach one of the model services. Is it running? Open /api/health to see which one."
    if isinstance(error, ollama.ResponseError) and error.status_code == 404:
        return (f"Ollama says: {error.error}. Download the models with "
                f"'ollama pull {settings.llm_model}' and 'ollama pull {settings.embed_model}'.")
    return f"Something went wrong: {error}"


class Question(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    grade: int = Field(ge=1, le=12)
    subject: str
    chapter: int | None = None
    language: Literal["English", "Hindi"] = "English"
    pure_llm: bool = False
    session_id: str | None = None
    history: list[dict] = Field(default_factory=list)


class Feedback(BaseModel):
    question: str = Field(max_length=500)
    answer: str = Field(max_length=10_000)
    helpful: bool
    grade: int | None = None
    subject: str | None = None


def check_subject(q: Question) -> None:
    if not any(s["grade"] == q.grade and s["subject"] == q.subject for s in get_rag().subjects()):
        raise HTTPException(400, f"There is no Class {q.grade} {q.subject} textbook in the index.")


def check_ollama(models: list[str]) -> str:
    """Is Ollama running, and has it downloaded these models?"""
    try:
        response = httpx.get(f"{settings.ollama_url}/api/tags", timeout=3)
        installed = {m["name"] for m in response.json()["models"]}
    except (httpx.HTTPError, KeyError, ValueError):
        return f"not reachable at {settings.ollama_url} (is Ollama running?)"
    missing = [m for m in models if m not in installed and f"{m}:latest" not in installed]
    return f"missing models: {', '.join(missing)} (run: ollama pull <name>)" if missing else "ok"


def check_server(url: str) -> str:
    """Is anything answering at this address? (Any reply counts, even an error page.)"""
    try:
        httpx.get(url, timeout=3)
        return "ok"
    except httpx.HTTPError:
        return f"not reachable at {url} (is the container running?)"


def index_status() -> str:
    if rag is not None:
        return f"ok ({rag.info['chunks']} chunks)"
    try:
        read_index_info()
        return "built, but not loaded (see the server log)"
    except (FileNotFoundError, IndexMismatch) as error:  # say exactly what's wrong
        return str(error)


@app.get("/api/health")
def health():
    # Only check the services the adapters in .env actually use
    services = {}
    ollama_models = [model for model, used in ((settings.llm_model, settings.llm == "ollama"),
                                               (settings.embed_model, settings.embedder == "ollama")) if used]
    if ollama_models:
        services["ollama"] = check_ollama(ollama_models)
    if settings.embedder != "ollama":
        services["embedding server"] = check_server(settings.embed_url)
    if settings.llm != "ollama":
        services["llm server"] = check_server(settings.llm_url)
    if settings.vector_store == "qdrant" and settings.qdrant_url:
        services["qdrant"] = check_server(settings.qdrant_url)

    ok = rag is not None and all(status == "ok" for status in services.values())
    return {"status": "ok" if ok else "error", "index": index_status(), **services,
            "adapters": {"embedder": settings.embedder, "llm": settings.llm, "vector_store": settings.vector_store},
            "llm_model": settings.llm_model, "embed_model": settings.embed_model}


@app.get("/api/subjects")
def subjects(user: dict | None = Depends(get_optional_user)):
    all_subjects = get_rag().subjects()
    if user and not user.get("is_parent") and user.get("grade") is not None:
        return [s for s in all_subjects if s.get("grade") == user["grade"]]
    return all_subjects


def make_turn_record(
    q: Question,
    answer: str,
    sources: list[dict] | None = None,
    found: bool = True,
    safety_status: str = "CLEAN",
    flagged: bool = False,
    safety_category: str | None = None,
    latency_s: float | None = None,
) -> dict:
    return {
        "turn_id": f"turn_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{secrets.token_hex(3)}",
        "session_id": q.session_id,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "student_grade": q.grade,
        "subject": q.subject,
        "chapter": q.chapter,
        "language": q.language,
        "question": q.question,
        "answer": answer,
        "sources": sources or [],
        "pure_llm": q.pure_llm,
        "found": found,
        "safety_status": safety_status,
        "flagged": flagged,
        "safety_category": safety_category,
        "latency_s": latency_s,
    }


@app.post("/api/ask")
def ask(q: Question, user: dict | None = Depends(get_optional_user)):
    enforce_grade(user, q.grade)
    check_subject(q)
    parental_config = get_active_parental_filtering_config()
    # Content Moderation Screening
    safety_result = evaluate_content(
        question=q.question,
        grade=q.grade,
        subject=q.subject,
        chapter=q.chapter,
        language=q.language,
        session_id=q.session_id,
        parental_config=parental_config,
    )
    if not safety_result.is_safe:
        log_safety_event(
            query_text=q.question,
            category=safety_result.category or "other_inappropriate",
            severity=safety_result.severity or "HIGH",
            student_grade=q.grade,
            subject=q.subject,
            chapter=q.chapter,
            session_id=q.session_id,
            filter_stage=safety_result.filter_stage or "scanner",
            matched_rule=safety_result.matched_rule,
            action_taken="BLOCKED_CRISIS_REFUSAL" if safety_result.is_crisis else "BLOCKED_REFUSAL",
            refusal_type="crisis_helpline_p0" if safety_result.is_crisis else "age_appropriate_refusal",
        )
        cat_val = safety_result.category.value if hasattr(safety_result.category, "value") else str(safety_result.category)
        sev_val = safety_result.severity.value if hasattr(safety_result.severity, "value") else str(safety_result.severity)
        log_chat_turn(
            make_turn_record(
                q,
                answer=safety_result.refusal_message,
                found=False,
                safety_status="BLOCKED",
                flagged=True,
                safety_category=cat_val,
                latency_s=0.0,
            )
        )
        return {
            "answer": safety_result.refusal_message,
            "sources": [],
            "found": False,
            "prompt_pure_llm": False,
            "category": cat_val,
            "severity": sev_val,
            "is_crisis": safety_result.is_crisis,
            "safety_refusal": True,
        }

    # Security Pre-Screening
    sec_result = check_security_inbound(
        text=q.question,
        grade=q.grade,
        subject=q.subject,
        language=q.language,
        session_id=q.session_id,
    )
    if sec_result.is_blocked:
        cat_str = sec_result.threat_category.value if sec_result.threat_category else "DIRECT_INSTRUCTION_OVERRIDE"
        log_safety_event(
            query_text=q.question,
            category=cat_str,
            severity="HIGH",
            student_grade=q.grade,
            subject=q.subject,
            chapter=q.chapter,
            session_id=q.session_id,
            filter_stage="security_scanner",
            matched_rule=sec_result.matched_rule,
            action_taken="BLOCKED_SECURITY_REFUSAL",
            refusal_type="security_policy_refusal",
            extra={"trigger_pattern": sec_result.trigger_pattern, "threat_category": cat_str},
        )
        log_chat_turn(
            make_turn_record(
                q,
                answer=sec_result.refusal_message,
                found=False,
                safety_status="BLOCKED",
                flagged=True,
                safety_category=cat_str,
                latency_s=0.0,
            )
        )
        return {
            "answer": sec_result.refusal_message,
            "sources": [],
            "found": False,
            "prompt_pure_llm": False,
            "blocked_by_security": True,
            "threat_category": cat_str,
            "security_refusal": True,
        }

    started = time.time()
    log.info("Q (Class %d %s, pure_llm=%s, session=%s, history_turns=%d): %s", q.grade, q.subject, q.pure_llm, q.session_id, len(q.history), q.question)
    try:
        result = get_rag().ask(
            q.question,
            q.grade,
            q.subject,
            q.language,
            q.chapter,
            pure_llm=q.pure_llm,
            session_id=q.session_id,
            history=q.history,
        )
    except Exception as error:
        log.exception("Failed to answer")
        raise HTTPException(502, explain(error)) from error
    latency = round(time.time() - started, 3)
    log.info("Answered in %.1fs (found=%s)", latency, result["found"])
    log_chat_turn(
        make_turn_record(
            q,
            answer=result.get("answer", ""),
            sources=result.get("sources", []),
            found=result.get("found", True),
            safety_status="CLEAN",
            flagged=False,
            safety_category=None,
            latency_s=latency,
        )
    )
    return result


@app.post("/api/ask/stream")
def ask_stream(q: Question, user: dict | None = Depends(get_optional_user)):
    """Streams the answer as it is written, one JSON object per line."""
    enforce_grade(user, q.grade)
    check_subject(q)
    parental_config = get_active_parental_filtering_config()
    # Content Moderation Screening
    safety_result = evaluate_content(
        question=q.question,
        grade=q.grade,
        subject=q.subject,
        chapter=q.chapter,
        language=q.language,
        session_id=q.session_id,
        parental_config=parental_config,
    )
    if not safety_result.is_safe:
        log_safety_event(
            query_text=q.question,
            category=safety_result.category or "other_inappropriate",
            severity=safety_result.severity or "HIGH",
            student_grade=q.grade,
            subject=q.subject,
            chapter=q.chapter,
            session_id=q.session_id,
            filter_stage=safety_result.filter_stage or "scanner",
            matched_rule=safety_result.matched_rule,
            action_taken="BLOCKED_CRISIS_REFUSAL" if safety_result.is_crisis else "BLOCKED_REFUSAL",
            refusal_type="crisis_helpline_p0" if safety_result.is_crisis else "age_appropriate_refusal",
        )
        cat_val = safety_result.category.value if hasattr(safety_result.category, "value") else str(safety_result.category)
        sev_val = safety_result.severity.value if hasattr(safety_result.severity, "value") else str(safety_result.severity)
        log_chat_turn(
            make_turn_record(
                q,
                answer=safety_result.refusal_message,
                found=False,
                safety_status="BLOCKED",
                flagged=True,
                safety_category=cat_val,
                latency_s=0.0,
            )
        )

        def refusal_events():
            yield json.dumps({"type": "token", "text": safety_result.refusal_message}, ensure_ascii=False) + "\n"
            yield json.dumps({
                "type": "done",
                "answer": safety_result.refusal_message,
                "sources": [],
                "found": False,
                "prompt_pure_llm": False,
                "category": cat_val,
                "severity": sev_val,
                "is_crisis": safety_result.is_crisis,
                "safety_refusal": True,
            }, ensure_ascii=False) + "\n"

        resp = StreamingResponse(refusal_events(), media_type="application/x-ndjson")
        resp.events = refusal_events
        return resp

    # Security Pre-Screening
    sec_result = check_security_inbound(
        text=q.question,
        grade=q.grade,
        subject=q.subject,
        language=q.language,
        session_id=q.session_id,
    )
    if sec_result.is_blocked:
        cat_str = sec_result.threat_category.value if sec_result.threat_category else "DIRECT_INSTRUCTION_OVERRIDE"
        log_safety_event(
            query_text=q.question,
            category=cat_str,
            severity="HIGH",
            student_grade=q.grade,
            subject=q.subject,
            chapter=q.chapter,
            session_id=q.session_id,
            filter_stage="security_scanner",
            matched_rule=sec_result.matched_rule,
            action_taken="BLOCKED_SECURITY_REFUSAL",
            refusal_type="security_policy_refusal",
            extra={"trigger_pattern": sec_result.trigger_pattern, "threat_category": cat_str},
        )
        log_chat_turn(
            make_turn_record(
                q,
                answer=sec_result.refusal_message,
                found=False,
                safety_status="BLOCKED",
                flagged=True,
                safety_category=cat_str,
                latency_s=0.0,
            )
        )

        def security_refusal_events():
            yield json.dumps({"type": "token", "text": sec_result.refusal_message}, ensure_ascii=False) + "\n"
            yield json.dumps({
                "type": "done",
                "answer": sec_result.refusal_message,
                "sources": [],
                "found": False,
                "prompt_pure_llm": False,
                "blocked_by_security": True,
                "threat_category": cat_str,
                "security_refusal": True,
            }, ensure_ascii=False) + "\n"

        resp = StreamingResponse(security_refusal_events(), media_type="application/x-ndjson")
        resp.events = security_refusal_events
        return resp

    log.info("Q stream (Class %d %s, pure_llm=%s, session=%s, history_turns=%d): %s", q.grade, q.subject, q.pure_llm, q.session_id, len(q.history), q.question)

    def events():
        started = time.time()
        try:
            for event in get_rag().ask_stream(
                q.question,
                q.grade,
                q.subject,
                q.language,
                q.chapter,
                pure_llm=q.pure_llm,
                session_id=q.session_id,
                history=q.history,
            ):
                if event.get("type") == "done":
                    latency = round(time.time() - started, 3)
                    log_chat_turn(
                        make_turn_record(
                            q,
                            answer=event.get("answer", ""),
                            sources=event.get("sources", []),
                            found=event.get("found", True),
                            safety_status="CLEAN",
                            flagged=False,
                            safety_category=None,
                            latency_s=latency,
                        )
                    )
                yield json.dumps(event, ensure_ascii=False) + "\n"
            log.info("Answered in %.1fs", time.time() - started)
        except Exception as error:
            log.exception("Failed to answer")
            yield json.dumps({"type": "error", "message": explain(error)}) + "\n"

    resp = StreamingResponse(events(), media_type="application/x-ndjson")
    resp.events = events
    return resp


@app.get("/api/metrics")
def metrics(limit: int = 50):
    """Retrieve logged metrics and aggregate statistics for conversations."""
    return get_metrics_summary(limit=limit)


feedback_lock = threading.Lock()  # two students clicking at once mustn't mix up their lines


@app.post("/api/feedback", status_code=204)
def feedback(f: Feedback):
    record = {"time": datetime.now(timezone.utc).isoformat(timespec="seconds"), **f.model_dump()}
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    with feedback_lock, open(settings.feedback_file, "a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False) + "\n")


@app.get("/login")
def login_page():
    """Serves the student authentication portal."""
    login_html = ROOT / "frontend" / "login.html"
    if login_html.exists():
        return FileResponse(login_html)
    return FileResponse(ROOT / "frontend" / "index.html")


# The textbook PDFs, so every source can link to the exact page it came from
app.mount("/pdfs", StaticFiles(directory=settings.data_dir, check_dir=False), name="pdfs")
# The web page. Mounted last so it doesn't hide the /api routes.
app.mount("/", StaticFiles(directory=ROOT / "frontend", html=True), name="frontend")
