# NCERT Doubt-Solver: Implementation Plan (Hindi + English)

**What this is:** a personal college project based on Intel Unnati Problem Statement 1.
**Scope:** a working demo on a small set of textbook chapters, in Hindi and English.
**Cost:** ₹0. Every tool and model is free and runs on one laptop. No cloud, no API keys.
**Status:** plan. Items marked **(exists)** are already built; everything else is to do.

---

## Contents

1. [Goal and scope](#1-goal-and-scope)
2. [Principles](#2-principles)
3. [Architecture](#3-architecture)
4. [The adapter layer](#4-the-adapter-layer)
5. [Flow 1: building the index](#5-flow-1-building-the-index)
6. [Flow 2: answering a question](#6-flow-2-answering-a-question)
7. [Hindi + English](#7-hindi--english)
8. [Edge cases](#8-edge-cases)
9. [Models (all free)](#9-models-all-free)
10. [Evaluation](#10-evaluation)
11. [Speed: before and after](#11-speed-before-and-after)
12. [Fine-tuning (optional)](#12-fine-tuning-optional)
13. [Files to add or change](#13-files-to-add-or-change)
14. [Build steps](#14-build-steps)
15. [Decisions](#15-decisions)

---

## 1. Goal and scope

A student picks a **class** and **subject** and asks a question in **Hindi, English or Hinglish**.
The app finds the right pages in **that textbook**, writes a short answer **only from those pages**,
and cites each sentence with a link to the PDF page. If the book doesn't cover it, the app says so.

```
 "प्रकाश का अपवर्तन क्या है?"  (Class 10, Science)
        │
        ▼
 detect language → search Class 10 Science (Hindi book) → answer from those pages → check every claim
        │
        ▼
 "जब प्रकाश एक माध्यम से दूसरे माध्यम में जाता है तो उसकी दिशा बदल जाती है [1]।"
  [1] विज्ञान, अध्याय 9, पृष्ठ 148   (click → opens the PDF at that page)
```

### Demo data (small on purpose)

| Class | English | Hindi |
|---|---|---|
| 10 | Science, Social Science, English (exists, 29 chapters) | **3 Science chapters** from the Hindi-medium NCERT book, the same chapters as in English (e.g. Light, Electricity, Life Processes). These need OCR, so they show the OCR pipeline working |
| 5 | Demo books written for the project (exists) | **1 small demo book** written in Hindi (Unicode PDF), like the existing English demo books |

That's enough to show every feature: grade filtering, both languages, OCR, citations and "I don't know".
More books can be added later by dropping PDFs in `data/` and adding them to the catalog.

### In scope / out of scope

| Built | Not built (on purpose) |
|---|---|
| RAG with grade + subject filters, citations, "I don't know" (exists) | Production hardening (auth, rate limits, HTTPS, monitoring) |
| Hindi + English + Hinglish questions | Urdu and other languages (the design allows adding them later) |
| OCR for the Hindi chapters | Large-scale ingestion of all NCERT books |
| Follow-up questions (conversation) | User accounts, saved chat history on the server |
| Feedback 👍/👎 (exists) | Feedback dashboards |
| Small eval set + before/after speed numbers | Paid cloud benchmarks |
| Optional OPEA mode (Docker) | Kubernetes, scaling |
| Optional fine-tuning on a free GPU | — |

---

## 2. Principles

1. **The textbook is the only source.** A sentence the book doesn't support is deleted before the student sees it. **(exists)**
2. **"I don't know" beats a wrong answer.** Weak search results never reach the LLM. **(exists)**
3. **Hindi question → Hindi book first.** Translation is only a fallback.
4. **Plain code decides, the LLM only writes.** Language, filters and checks are normal Python you can unit-test.
5. **Every part can be swapped (adapters).** Changing the LLM, embedding model, vector store or OCR is a setting, not a rewrite.
6. **Measure, don't guess.** Every change is checked with the eval script. **(exists)**

---

## 3. Architecture

There are two ways to run it. **Same code, different settings.**

### Simple mode (default): plain Python + Ollama

What runs today, extended. Nothing to install except Python, Ollama and Tesseract.

```
 Browser (phone or laptop)
      │  streaming answer
      ▼
 ┌──────────────────────────────────────────────────────────┐
 │  FastAPI app  (uvicorn, port 8000)                       │
 │                                                          │
 │  detect language → rewrite follow-up → search → check    │
 │  score → prompt → stream answer → check claims → cite    │
 │                                                          │
 │  ┌──────────── adapter layer (app/adapters.py) ───────┐  │
 │  │ Embedder     VectorStore     LLM        OCR        │  │
 │  └─────┬────────────┬─────────────┬──────────┬────────┘  │
 └────────┼────────────┼─────────────┼──────────┼───────────┘
          ▼            ▼             ▼          ▼
     Ollama        index files    Ollama     Tesseract
   (embedding)    in storage/     (LLM)     (local OCR)
```

### OPEA mode (optional, for showing the OPEA architecture)

The same app, but each model runs as its own microservice in Docker, the way OPEA's
**ChatQnA** example is built. The FastAPI app plays OPEA's **megaservice/gateway** role.

```
 Browser ──► FastAPI app (gateway / megaservice)
                 │          │            │
                 ▼          ▼            ▼
             TEI         Qdrant       Ollama or OPEA LLM service
         (embedding    (vector DB)    (LLM microservice)
          microservice)
            ── all started with: docker compose -f deploy/compose.opea.yaml up ──
```

Switching modes means changing `.env` (Section 4). No code changes. Docker Desktop is free
for personal and education use.

> **RAM check (15 GB laptop):** simple mode uses ~5 GB (LLM ~3.5 GB + embedding ~1 GB).
> OPEA mode adds Docker overhead, so stop other heavy apps and give Docker ~8 GB.

---

## 4. The adapter layer

**Why:** each outside service (embedding model, vector store, LLM, OCR) sits behind one small
interface. The rest of the app never knows which one is plugged in. This is how simple mode and
OPEA mode share all their code, and how the tests run without any models: they plug in fakes
(`WordCountEmbedding`, `FakeLLM` in [tests/conftest.py](../tests/conftest.py)) **(exists)**.

LlamaIndex already defines these interfaces and ships ready-made adapters, so we **choose** an
adapter instead of writing one. All choices live in one file:

| Interface | Setting in `.env` | Simple mode (default) | OPEA mode | Tests |
|---|---|---|---|---|
| **Embedder** | `EMBEDDER=` | `ollama` → `OllamaEmbedding` **(exists)** | `tei` → `TextEmbeddingsInference` or `opea` → `OPEAEmbedding` | `WordCountEmbedding` **(exists)** |
| **LLM** | `LLM=` | `ollama` → `Ollama` **(exists)** | `openai_like` → `OpenAILike` (any OpenAI-style server: OPEA, OpenVINO OVMS, vLLM) or `opea` → `OPEA` | `FakeLLM` **(exists)** |
| **Vector store** | `VECTOR_STORE=` | `simple` → LlamaIndex built-in, files in `storage/` **(exists)** | `qdrant` → `QdrantVectorStore` | in-memory **(exists)** |
| **OCR** (Step 2) | `OCR=` | `tesseract` (our small class) | same | `NoOCR` (returns the text layer) |

```python
# app/adapters.py — the ONLY file that knows which service is used   (built in Step 1)
def make_embed_model():
    if settings.embedder == "ollama": return OllamaEmbedding(model_name=settings.embed_model, base_url=settings.ollama_url, ...)
    if settings.embedder == "tei":    return TextEmbeddingsInference(model_name=settings.embed_model, base_url=settings.embed_url, ...)
    if settings.embedder == "opea":   return OPEAEmbedding(model_name=settings.embed_model, api_base=settings.embed_url)
    raise unknown("EMBEDDER", settings.embedder, EMBEDDERS)   # "Unknown EMBEDDER='x'. Choose one of: ollama, tei, opea"
# make_llm() and make_vector_store() follow the same pattern; make_ocr() comes in Step 2
```

Rules for the adapter layer:
- **One file chooses** (`app/adapters.py`, renamed from today's `app/models.py`). No `if settings.llm == ...` anywhere else.
- **Unknown setting → clear error at startup**, listing the valid options.
- **Extra packages only for the mode you use.** `requirements.txt` stays small; `requirements-opea.txt` adds the TEI, OPEA and Qdrant adapters.
- **The index remembers its embedding model.** The app refuses to start if the configured embedder differs from the one that built the index ("rebuild with `python -m app.ingest`"). Without this check, mixing models silently returns bad search results.

---

## 5. Flow 1: building the index

Run once, and again when PDFs change: `python -m app.ingest` **(exists, extend)**

```
 data/class-10/science/hi/jhsc109.pdf
        │
 ① CATALOG    file name → class, subject, medium (en/hi), book, chapter, title    (exists + add medium)
        │     unknown file → skipped, printed in the summary
        ▼
 ② READ PAGE  take the PDF's text layer                                            (exists)
        │
 ③ CHECK      is it real text in the expected script?
        │       Hindi book:   ≥ 60% of letters are Devanagari
        │       English book: ≥ 80% of letters are Latin
        │     no → ④     yes → ⑤
        ▼
 ④ OCR        render the page as an image (300 DPI) → Tesseract (hin+eng)
        │     save the result in storage/ocr_cache/ so the next run skips OCR
        │     still fails the check → skip the page, list it in the summary
        ▼
 ⑤ CLEAN      remove "Reprint"/"पुनर्मुद्रण" lines, page numbers, broken hyphens;    (exists + Hindi)
        │     Unicode NFC for Hindi
        ▼
 ⑥ CHUNK      ~512 tokens, sentence-aware; Hindi sentences end at "।"              (exists + Hindi)
        ▼
 ⑦ EMBED      through the Embedder adapter                                         (exists)
        ▼
 ⑧ SAVE       build the new index in a temp folder, then replace the old one       (exists)
        ▼
 ⑨ SUMMARY    pages per book · OCR pages · skipped pages + reason · time taken
```

**Why the check in ③:** NCERT's Hindi PDFs use an old non-Unicode font, so their text layer
comes out as junk like `foKku` instead of `विज्ञान`. Scanned pages have no text at all.
One script-ratio check catches both and sends them to OCR.

**Every chunk carries this metadata** (used for filtering and citations):
`grade, subject, medium, book, chapter, chapter_title, page, file, extraction (text|ocr)`.

---

## 6. Flow 2: answering a question

```
 POST /api/ask/stream   { question, grade, subject, history (last ≤ 3 turns), answer_language }
        │
 ① VALIDATE      3–500 characters; class/subject exists                                 (exists)
        ▼
 ② LANGUAGE      count letters by script:  Devanagari → hi | Latin + Hindi words → hinglish
        │                                  Latin → en | other script → "Hindi/English only"
        ▼
 ③ REWRITE       ONLY for follow-ups or Hinglish: one short LLM call turns the question
        │        into a standalone question (Hinglish → Devanagari Hindi).
        │        Empty or odd result → keep the original question
        ▼
 ④ SEARCH        filter: grade AND subject AND medium (question's language first)       (exists + medium)
        │        then double-check the filter in code                                  (exists)
        ▼
 ⑤ SCORE CHECK   keep hits ≥ min_score for this language                               (exists, per language)
        │        none → try the other language's book (cross-lingual)
        │        still none → "I don't know" in the student's language. STOP.
        ▼
 ⑥ PROMPT        rules + numbered excerpts [1] [2] + question;                          (exists)
        │        answer length by class; "write in Hindi (Devanagari)" / "in English"
        ▼
 ⑦ STREAM        LLM writes; text is cut into claims at each citation                   (exists)
        ▼
 ⑧ CHECK CLAIM   a claim is shown only if:
        │          a. it cites an excerpt that exists                                   (exists)
        │          b. its numbers appear in that excerpt                                (new, simple)
        │          c. its words mostly come from the excerpts                           (exists for English; add Hindi)
        │             cross-lingual answer → skip c, rely on a + b (documented limit)
        │          d. first claim only: written in the right language, else retry once
        │        nothing left → "I don't know"
        ▼
 ⑨ DONE          sources with PDF page links + answer_id                                (exists + answer_id)
```

### Follow-up questions, kept simple

- **The browser keeps the chat** and sends the last 3 turns with each question. The server
  stores nothing, so there's no session database.
- History is used **only** for the rewrite in ③. Answers still come only from the retrieved pages.
- Changing class or subject clears the chat.

### Feedback (exists)

👍/👎 saved to `storage/feedback.jsonl`. Add `answer_id` and the detected language so 👎 answers
can become new eval questions.

---

## 7. Hindi + English

### Language detection: simple rules, no model

| Question | Detected | Answer in (auto) | Book searched first |
|---|---|---|---|
| "What is refraction?" | `en` | English | English book |
| "अपवर्तन क्या है?" | `hi` | Hindi | Hindi book |
| "Ohm का नियम क्या है?" (mixed) | `hi` (≥ 30% Devanagari) | Hindi | Hindi book |
| "refraction kya hota hai?" | `hinglish` (Latin + words like *kya, hai, kaise, kyon, batao*) | Hindi | Hindi book |
| Urdu / Tamil script | unsupported | — | Polite message in English and Hindi |

The UI has a toggle **Answer in: Auto / English / हिन्दी** to override.

### Per-language settings: one table, not `if` statements

```python
# app/language.py
LANGUAGES = {
    "en": Language(min_score=0.53, max_new_share=0.40,
                   not_found="Sorry, I couldn't find this in your textbook.",
                   write_in="English"),
    "hi": Language(min_score=None, max_new_share=None,      # set from the Hindi eval
                   not_found="क्षमा करें, यह आपकी पाठ्यपुस्तक में नहीं मिला।",
                   write_in="Hindi, in Devanagari script"),
}
```

This is the same adapter idea applied to languages: adding Urdu later means one new entry plus its books.

### Hindi details

| Topic | What we do |
|---|---|
| Sentence end | Split on `।` too (the claim splitter already handles it) |
| Word check | Devanagari words; drop common words (है, के, की, में, से, और, यह, एक…); trim endings (ों, ें, ाओं) before comparing |
| Digits | Treat ०–९ as 0–9 in the number check |
| Answer length | Hindi uses more LLM tokens per word, so Hindi answers get a slightly lower word limit |

---

## 8. Edge cases

The ones that matter for a demo, each with a simple fix.

### Data

| Case | Handling |
|---|---|
| Hindi PDF text comes out as junk | Script check fails → OCR |
| Scanned page, no text | Script check fails → OCR |
| Blank or picture-only page | Under 50 characters → skipped and counted **(exists)** |
| OCR still unreadable | Page skipped and listed in the summary |
| Formulas and tables | Kept as plain text; known limit |
| Unknown file / contents pages | Skipped and listed **(exists)** |
| Embedding model changed, index not rebuilt | App refuses to start with a clear message |

### Questions

| Case | Handling |
|---|---|
| Too short / too long | Clear error **(exists)** |
| "hi", "नमस्ते", "who are you?" | Fixed friendly reply, no LLM call |
| Unsupported language | "Hindi and English only for now" |
| Hinglish | Rewritten to Hindi first |
| Topic from another class | Search stays inside the chosen class → "I don't know" **(exists)** |
| Typos | Embedding search usually copes; otherwise "I don't know, try the book's words" |
| "Ignore your rules and…" | Every shown sentence must cite the book, so injected text can't get through **(exists)** |
| Maths "solve this" | Shows the book's method; doesn't calculate new answers (known limit) |

### Answers

| Case | Handling |
|---|---|
| No good match | "I don't know" **(exists)** |
| LLM adds facts or numbers not in the book | Claim removed (word check **exists**, number check new) |
| LLM cites an excerpt that doesn't exist | Claim removed **(exists)** |
| No citations at all | Everything removed → "I don't know" **(exists)** |
| Wrong language | Caught on the first claim → one retry |
| Hindi asked about the English-only book | Cross-lingual fallback, answer in Hindi |
| Follow-up "why?" | Rewritten using history |
| Ollama not running / model missing | `/api/health` and error messages say how to fix it **(exists)** |
| Network drops mid-answer | UI keeps the partial answer, shows a retry button |

---

## 9. Models (all free)

| Job | Default | Try if needed | Size |
|---|---|---|---|
| LLM | `qwen3.5:4b` via Ollama **(exists)** | `qwen3.5:2b` (faster), `gemma3:4b` (often better Hindi) | ~3.3 GB |
| Embedding | `qwen3-embedding:0.6b` via Ollama **(exists)**, multilingual | `bge-m3` (also on Ollama) | ~0.6 GB |
| OCR | Tesseract 5 + Hindi language data (free Windows installer) | — | ~50 MB |

Pick by the eval numbers (Section 10), not by guesswork. Keep the current models unless the Hindi eval shows a clear gain.

---

## 10. Evaluation

Small but honest. Two checks, both free.

### Dataset: `eval/questions.json` (40 exist, grows to ~80)

| Type | Count | Example |
|---|---|---|
| English factual | 30 **(exists)** | "Why did Lencho write a letter to God?" |
| English off-topic | 10 **(exists)** | "Who won the World Cup?" |
| Hindi factual | 20 | "विद्युत धारा का SI मात्रक क्या है?" |
| Hindi off-topic | 5 | "आज मौसम कैसा है?" |
| Hinglish | 5 | "ohm ka niyam kya hai" |
| Follow-up pairs | 5 | "What is refraction?" → "Why does it happen?" |
| Cross-lingual | 5 | Hindi question about "A Letter to God" |

### 1. Search quality (automatic): `python -m app.evaluate` **(exists, extend per language)**

| Metric | Today (English) | Target |
|---|---|---|
| Hit rate (right chapter in top 4) | **100%** | ≥ 90% for Hindi |
| MRR | **1.00** | ≥ 0.80 for Hindi |
| "I don't know" for off-topic | **separates perfectly at 0.53** | find the Hindi threshold the same way |

### 2. Answer quality (semi-automatic): `python -m app.evaluate --answers`

For each question the script saves: answer, citations, claims removed, language and time,
into `eval/results/<date>.md`. Then **check 30 answers by hand** with a 3-point rubric:

| Score | Meaning |
|---|---|
| ✅ | Correct, from the book, citation points to the right page |
| ⚠️ | Correct but incomplete, or a weak citation |
| ❌ | Wrong, not in the book, or wrong citation |

**Target (from the problem statement): ≥ 85% ✅.** No paid "LLM judge" is needed at this size.

---

## 11. Speed: before and after

The problem statement asks for 3–5 seconds and "pre/post optimization" numbers. On a laptop CPU
we measure honestly and show the improvement.

The eval script records for each answer: **time to first word** and **total time**.
Results go in `docs/BENCHMARKS.md` as one row per change:

| # | Change | Expected effect |
|---|---|---|
| 0 | **Baseline:** today's setup | Starting numbers |
| 1 | Smaller LLM (`qwen3.5:2b`) | ~2× faster writing, check quality didn't drop |
| 2 | Fewer, shorter excerpts (top 3, cap by tokens) | Faster start |
| 3 | Rewrite step only when needed | Saves one LLM call on first questions |
| 4 | Keep the model loaded (`keep_alive`) **(exists)** | No cold start |
| 5 | *(optional)* OpenVINO INT4 model on an OpenAI-style server via the `openai_like` adapter | Intel's optimization path; free, runs on any x86 CPU |

> This laptop has an AMD CPU, so the numbers are "on a laptop CPU", not "on Intel hardware".
> Say that plainly in the report. It's normal for a personal project.

---

## 12. Fine-tuning (optional)

Only if time allows, and only after the eval works. Everything here is free.

```
 ① DATA     ~300–500 Hindi examples: (question, excerpts, answer with [1] citations)
            written with the help of the local LLM from the Hindi chapters,
            + ~25% examples where the excerpts DON'T answer → exact "not found" sentence.
            Run our own claim check on each one and drop failures. Review 50 by hand.
 ② TRAIN    LoRA on a small model (1.5–3B) on a free Google Colab or Kaggle GPU
 ③ EXPORT   merge → GGUF → import into Ollama (a Modelfile, no code change)
 ④ COMPARE  base vs fine-tuned on the Hindi eval: ✅ rate, language match, "not found" accuracy
```

Split train and test **by chapter**, so the test never contains chapters the model trained on.

---

## 13. Files to add or change

Small changes to today's layout. Nothing moves that doesn't need to.

```
app/
  adapters.py      ← rename of models.py; add make_vector_store(), make_ocr(); settings-driven
  language.py      NEW: detection + LANGUAGES table + Hindi word helpers
  ocr.py           NEW: script check + Tesseract wrapper + cache
  catalog.py       add "medium" (en/hi) + the 3 Hindi chapters + Hindi demo book
  ingest.py        call the script check / OCR; Hindi cleanup; save embed-model name
  rag.py           medium routing, per-language thresholds, number check, rewrite step
  prompts.py       answer language + Hindi "not found"
  main.py          accept history + answer_language; greetings; answer_id
  evaluate.py      per-language numbers, --answers mode, timing
deploy/
  compose.opea.yaml    NEW (optional): TEI + Qdrant + Ollama
frontend/          chat bubbles, history, language toggle, phone-friendly layout
eval/questions.json  + Hindi, Hinglish, follow-up, cross-lingual questions
tests/             + language detection, script check, Hindi word check, number check, adapters
docs/
  IMPLEMENTATION_PLAN.md   this file
  BENCHMARKS.md            before/after speed table
  LOG.md                   short dated notes: what was tried, the numbers, what was kept
requirements.txt          + pytesseract
requirements-opea.txt     NEW (optional): TEI, OPEA, Qdrant LlamaIndex adapters
```

Keep `data/`, `storage/`, `.env` and model files **out of git** (`.gitignore`).

---

## 14. Build steps

Each step ends with something you can **show**.

| Step | Work | Done when |
|---|---|---|
| **1. Adapters** ✅ | Rename `models.py` → `adapters.py`; settings for embedder, LLM, vector store; `index_info.json` + embed-model check. Guide: [steps/STEP-1-adapters.md](steps/STEP-1-adapters.md) | All tests pass; English eval is **unchanged** (100% / 1.00) |
| **2. Hindi data + OCR** | Install Tesseract + Hindi data; OCR adapter; script check; OCR cache; add `medium`; 3 Hindi chapters + Hindi demo book | Ingest summary shows the Hindi pages indexed; OCR text readable on 5 sample pages |
| **3. Hindi answers** | `language.py`; medium routing; Hindi thresholds; Hindi word check; number check; wrong-language retry | Hindi eval meets targets; new unit tests pass |
| **4. Conversation + UI** | History + rewrite; chat UI; language toggle; phone layout | Follow-up questions work in the demo, on a phone screen |
| **5. Evaluate + speed** | `--answers` mode; 30-answer hand check; benchmark rows 0–4 | ≥ 85% ✅; BENCHMARKS.md filled |
| **6. OPEA mode** *(optional)* | `compose.opea.yaml`; `EMBEDDER=tei`, `VECTOR_STORE=qdrant` | Same eval numbers in OPEA mode as in simple mode |
| **7. Fine-tune** *(optional)* | Section 12 | Fine-tuned model beats base on Hindi ✅ rate |
| *Stretch* | Voice input (browser's built-in speech recognition, free), photo of a question → OCR | — |

Step 1 comes first on purpose: it changes structure **without changing behaviour**, and the
existing eval proves that. Every later step then only adds features.

---

## 15. Decisions

| Decision | Instead of | Why |
|---|---|---|
| Ollama + local files by default | Docker microservices by default | Free, already working, light on a 15 GB laptop |
| Keep an adapter layer (LlamaIndex's own adapters) | Hard-coding Ollama | OPEA mode, faster models and test fakes become settings, not rewrites |
| Hindi answers from the Hindi book | Translating the English book | Real Hindi citations, simpler checks |
| Script-count language detection | A language-detection model | Only two languages; exact, instant, easy to test |
| Browser keeps chat history | Server sessions | Nothing to store or lose |
| Tesseract OCR | Large OCR models | Free, small, works offline on CPU |
| Hand-check 30 answers | Paid LLM judge | Free, and more trustworthy at this size |
| Small demo data | All NCERT books | Shows every feature; ingest stays fast on a laptop |

---

### Engineering habits used (from the Evolve skills in `.claude/skills/`)

- **Change structure first, prove nothing broke, then add features** (`legacy-port-migration`): Step 1.
- **Bad pages are skipped and reported, never silently indexed** (`canonical-data-pipeline`): Flow 1, ③–④.
- **Fast tests with fake models, plus the eval for real quality** (`test-gates`): Section 10.
- **Write down numbers with dates** (`engineering-journal`): `docs/LOG.md`, `docs/BENCHMARKS.md`.
- **Code decides, the LLM only writes, honest "I don't know"** (`llm-agent-product`): Principles 1, 2, 4.
- **Data and secrets stay out of git** (`code-data-boundaries`): Section 13.
- **Readable text and big tap targets on phones** (`touch-ui-system`): Step 4.
