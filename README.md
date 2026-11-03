# Playright-Student Assistant

**Playright-Student Assistant** is an offline-first RAG (Retrieval-Augmented Generation) application for students. Ask questions about your NCERT Class 10 textbooks and get answers that come
**only from the textbook**, with the chapter and page they came from.
Everything runs on your own computer with free, open models. No internet or
API key needed once it's set up.

---

## How it works (RAG in 60 seconds)

An LLM on its own answers from memory, and it can make things up.
**RAG (Retrieval-Augmented Generation)** fixes that: first *look things up*
in your documents, then ask the LLM to answer *using only what was found*.

```
 ONCE: python -m app.ingest                  EVERY QUESTION: the web app
 ──────────────────────────                  ───────────────────────────
 PDFs in data/                               "What is Ohm's law?"  (Class 10 Science)
   │ read each page, clean the text            │ 1. RETRIEVE: turn the question into a vector and
   ▼                                           │    find the 4 most similar chunks, only from
 470 pages                                     │    Class 10 Science
   │ split into ~512-token chunks              ▼
   ▼                                         drop weak matches (score < 0.53)
 856 chunks                                    │    nothing left? → "Sorry, I couldn't find this..."
   │ turn each chunk into a vector             ▼
   ▼   (qwen3-embedding:0.6b)                2. PROMPT: rules + excerpts [1] [2] [3] + question
 storage/qdrant/                                │
   (vectors + chapter/page metadata)            ▼
                                             3. GENERATE: qwen3.5:4b writes the answer, citing [1] [2]
                                               → shown word by word, with links to the exact PDF pages
```

| File | What it does |
|---|---|
| [app/ingest.py](app/ingest.py) | **Step 0.** PDFs → Docling page text → chunks → vectors → `storage/index/` and Qdrant |
| [app/catalog.py](app/catalog.py) | Which book and chapter each PDF is (from NCERT file names like `jesc109.pdf`) |
| [app/rag.py](app/rag.py) | **Steps 1–3.** Retrieve the best chunks, build the prompt, ask the LLM |
| [app/prompts.py](app/prompts.py) | The instructions given to the LLM |
| [app/adapters.py](app/adapters.py) | Picks which service does each job (embedding, LLM, vector store) from `.env` |
| [app/config.py](app/config.py) | Every setting in one place (override any of them in `.env`) |
| [app/main.py](app/main.py) | Web server (FastAPI): the API and the web page |
| [app/evaluate.py](app/evaluate.py) | Measures search quality with [eval/questions.json](eval/questions.json) |
| [frontend/](frontend/) | The web page: plain HTML, CSS and JavaScript, no build step |
| [tests/](tests/) | Automated tests (they run without Ollama) |

---

## Setup (Windows, one time)

**1. Install [Ollama](https://ollama.com/download)** and download the two models:

```powershell
ollama pull qwen3.5:4b             # the LLM that writes answers (3.3 GB)
ollama pull qwen3-embedding:0.6b   # the embedding model used for search (0.6 GB)
```

**2. Create a Python environment** (Python 3.11 or newer) and install the packages:

```powershell
py -3.13 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

**3. Build the Docling/Qdrant search index** from the PDFs in `data/`:

```powershell
python -m app.ingest
```

Docling performs page-aware PDF conversion and may download its parsing models on
the first run. The current local rebuild contains 470 pages and 856 chunks in Qdrant.
Embedding those chunks with Ollama took about 35 minutes on the recorded laptop CPU.
You only do this once (and again when the PDFs change).

## Run

```powershell
.venv\Scripts\activate
uvicorn app.main:app --port 8000
```

Open **http://localhost:8000**, pick a textbook and ask away.
The API docs are at http://localhost:8000/docs.

---

## Everyday tasks

**Check that search works well:** `python -m app.evaluate` runs the 40
questions in `eval/questions.json` and reports how often the right chapter
is found. Run it before and after any change, to see if it helped.

**Run the tests:** `pytest` (a few seconds, no Ollama needed).

**Change a setting:** copy `.env.example` to `.env` and edit it. For example,
`LLM_MODEL=qwen3.5:2b` answers about twice as fast; `qwen3.5:9b` answers
better if you have 10 GB+ of free RAM.

**Add a textbook** (e.g. Class 9 Science, NCERT code `iesc1`):
1. Download its chapter PDFs from https://ncert.nic.in/textbook.php
2. Put them under `data/`, e.g. `data/class-9/science/iesc101.pdf`
3. Add the book and its chapter titles to `BOOKS` in [app/catalog.py](app/catalog.py)
4. Rebuild: `python -m app.ingest`

**Demo books for Class 5:** `data/class-5/` holds three short books (English,
Science, Social Science; 5 chapters, 10 pages each) written for this project.
They are **not NCERT books**. Their topics overlap the Class 10 books (plants'
food, light, electricity, soil, farming...), so you can ask the same question as
a Class 5 and a Class 10 student and see each get an answer from its own book.

**Read student feedback:** every 👍/👎 is saved, one line each, in
`storage/feedback.jsonl`. The 👎 ones show you what to improve.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Status badge says **Problem** | Hover over it, or open http://localhost:8000/api/health, to see what's wrong |
| "index hasn't been built yet" | Run `python -m app.ingest` |
| "Can't reach Ollama" | Start Ollama (it runs in the system tray) |
| "model not found" | Run the `ollama pull` commands from Setup |
| Answers are slow | Normal on a CPU. Close heavy apps (browsers!), or try `LLM_MODEL=qwen3.5:2b` |
| "Couldn't find this" for a real textbook question | Check the right textbook is selected. Try rephrasing with words the book uses |

---

## Production notes

What's already in place:

- **Grounded answers.** The LLM only sees textbook excerpts and is told to say
  "not found" when they don't contain the answer. Weak matches never reach it.
- **Class and subject isolation.** Search is filtered by class and subject, so a
  Class 5 Science question only ever sees the Class 5 Science book, even when a
  Class 10 book covers the same topic. Results are checked again after search.
- **Answer check.** Each claim the LLM writes must cite an excerpt and mostly use
  the textbook's words. Claims that bring in outside facts, or cite nothing, are
  removed before the student sees them (`MAX_NEW_SHARE` in `.env`). If nothing
  is left, the student gets "not found". Limit: it checks words, so it can't
  check Hindi answers, and it misses made-up facts that reuse the page's own words.
- **Citations you can check.** Each source links to the exact page of the PDF.
- **Health check** at `/api/health`: index loaded? Ollama up? models downloaded?
- **Input validation** with clear error messages, and readable errors when Ollama is down.
- **Logs** of every question, the similarity scores found, and the answer time.
- **Feedback** from students, saved for review.
- **Tests** for the pipeline and the API, plus a retrieval **evaluation**.
- **Config through environment variables**, so the same code runs on any machine.

To let other people on your network use it:
`uvicorn app.main:app --host 0.0.0.0 --port 8000`

When you outgrow this setup:

- **Many more books?** The built-in vector store keeps everything in memory,
  which is fine for a few thousand pages. Beyond that, switch to
  [Chroma](https://docs.llamaindex.ai/en/stable/examples/vector_stores/ChromaIndexDemo/)
  or Qdrant; only `ingest.py` and `load_index()` change.
- **Many students at once?** A CPU writes one answer at a time. Run Ollama on a
  machine with a GPU and point `OLLAMA_URL` at it.
- **On the public internet?** Put it behind a reverse proxy (Caddy or Nginx)
  with HTTPS and rate limiting.

---

## About the data

`data/class-10/` holds the **English-medium** NCERT Class 10 books:
English (*First Flight*, 9 chapters), Science (13 chapters) and Social Science
(*Contemporary India II*, 7 chapters).

The Hindi and Urdu PDFs from the earlier version are kept in
`_legacy/llama_index/data/` but are **not indexed**: the Hindi PDFs use an old
font encoding that turns into gibberish when the text is extracted, and the
Urdu PDFs are scanned images with no text in them. Supporting them needs OCR,
which is a project of its own. (You can still choose **Hindi** as the answer
language: the answer is then written in Hindi from the English textbook.)

The previous version of the project (old backend, frontend and scripts) is in
`_legacy/` for reference. It can be deleted once you're happy with this one.
