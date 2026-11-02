# Step 1: The adapter layer

> **Goal of this step:** make every outside service (embedding model, LLM, vector store)
> **swappable by changing one line in `.env`**, without changing what students see.
>
> **Status:** ✅ done. 44 tests pass; the search evaluation gives the same score as before
> (see [section 9](#9-proof-that-nothing-broke)).

---

## What you'll learn

- What an **adapter** is, and why almost every real software project uses them
- How the app reads settings from a **`.env` file**
- How the app remembers **which model built the index**, and why that matters
- How **tests with fake models** let you check code without running any AI model
- How to **prove a change broke nothing** (a "parity" check)

You don't need to know any of this already. Every new word is explained the first time it appears.

---

## Contents

1. [The problem](#1-the-problem)
2. [The idea: adapters](#2-the-idea-adapters)
3. [Words you need](#3-words-you-need)
4. [What changed (file by file)](#4-what-changed-file-by-file)
5. [The code, explained](#5-the-code-explained)
6. [How a question flows now](#6-how-a-question-flows-now)
7. [The tests, explained](#7-the-tests-explained)
8. [Try it yourself](#8-try-it-yourself)
9. [Proof that nothing broke](#9-proof-that-nothing-broke)
10. [Common mistakes](#10-common-mistakes)
11. [How to explain this in a viva](#11-how-to-explain-this-in-a-viva)
12. [What's next](#12-whats-next)

---

## 1. The problem

Before this step, the app was **hard-wired to Ollama**. The file `app/models.py` said:

```python
def make_llm() -> Ollama:
    return Ollama(model=..., base_url=...)
```

That works, but suppose you want to:

- show the **OPEA architecture**, where each model runs as its own service in Docker,
- try a **faster LLM server** (for example OpenVINO),
- store vectors in a real **vector database** (Qdrant) instead of files.

You'd have to edit code in several files, and every edit could break something.

## 2. The idea: adapters

Think of a **travel plug adapter**. Your phone charger doesn't change when you travel. The
wall socket is different in each country, so you put an adapter between them. The charger
only knows "I plug into the adapter".

Our app works the same way:

```
          Your app (rag.py, main.py)                 ← never changes
                     │
                     │  "give me an LLM"  /  "give me an embedding model"
                     ▼
          ┌──────────────────────────┐
          │   app/adapters.py        │  ← reads .env, picks the right plug
          └──────────────────────────┘
             │          │          │
             ▼          ▼          ▼
          Ollama      OPEA      OpenVINO / vLLM / …   ← the "sockets"
```

**The key trick:** LlamaIndex (the RAG library we use) already gives every LLM the **same
methods**. `Ollama`, `OPEA` and `OpenAILike` all have `.stream_chat(messages)`. So `rag.py`
can call `self.llm.stream_chat(...)` without knowing which one it got. The same goes for
embedding models (`.get_query_embedding(text)`) and vector stores.

A set of methods that several classes all promise to have is called an **interface**.
Code that only uses the interface works with every class that has it.

## 3. Words you need

| Word | Meaning |
|---|---|
| **Embedding / vector** | A list of numbers (here 1,024 of them) that represents the *meaning* of a text. Texts with similar meaning get similar numbers |
| **Embedding model** | The AI model that turns text into a vector. Ours is `qwen3-embedding:0.6b` |
| **LLM** | Large Language Model: the AI that writes the answer. Ours is `qwen3.5:4b` |
| **Vector store** | Where the vectors are kept, plus a fast way to find the ones closest to a question's vector |
| **Index** | All textbook chunks + their vectors, saved together. Built by `python -m app.ingest` |
| **Service** | A program that runs separately and answers requests over the network (Ollama, a Docker container, …) |
| **Interface** | The methods that several classes all promise to have, so they can replace each other |
| **Adapter** | The code that connects your app to one specific service through the shared interface |
| **`.env` file** | A text file of `NAME=value` lines with your settings. Not in git, so each computer can have its own |
| **Parity** | "The new version behaves exactly like the old one." We check it with tests and the evaluation |

## 4. What changed (file by file)

| File | Change | Why |
|---|---|---|
| `app/models.py` | **Deleted** | Replaced by `adapters.py` |
| `app/adapters.py` | **New** | The only file that decides which service does each job |
| `app/config.py` | Added `embedder`, `llm`, `vector_store` and service URLs | So `.env` can choose the adapters |
| `app/ingest.py` | Builds into the chosen vector store; writes `index_info.json`; checks it on load | The index remembers which model built it |
| `app/rag.py` | Gets the subject list from `index_info.json` | A vector database like Qdrant can't list its contents cheaply |
| `app/main.py` | Clear error messages; health check covers whichever services are in use | Easier to fix problems |
| `app/evaluate.py` | Passes the index info to `RAG` | Same reason as `rag.py` |
| `frontend/app.js` | Status tooltip lists every checked service | Works in both modes |
| `tests/conftest.py` | New helper `build_rag()` that accepts any vector store | So tests can compare stores |
| `tests/test_adapters.py` | **New**, 15 tests | Proves the adapters work and swapping changes nothing |
| `requirements-opea.txt` | **New** | Extra packages, only for OPEA mode |
| `.env.example` | Adapter settings added | Shows the two modes |

## 5. The code, explained

### 5.1 `app/config.py`: where settings come from

```python
class Settings(BaseSettings):
    embedder: str = "ollama"       # ollama | tei | opea
    llm: str = "ollama"            # ollama | openai_like | opea
    vector_store: str = "simple"   # simple | qdrant
    ...
settings = Settings()
```

- `BaseSettings` comes from the `pydantic-settings` package. When `Settings()` runs, it fills each
  field in this order: **environment variable → `.env` file → the default written here**.
- So `LLM=opea` in `.env` makes `settings.llm == "opea"`. Field names are written in lower case
  in Python and in UPPER CASE in `.env`.
- `settings` is created **once, when the program starts**. That's why you restart the server after editing `.env`.

The new URL settings say where each service runs. Only the ones your adapters use matter:

```python
ollama_url: str = "http://localhost:11434"   # Ollama
embed_url:  str = "http://localhost:6006"    # TEI / OPEA embedding service
llm_url:    str = "http://localhost:9000/v1" # OPEA / OpenAI-style LLM server
qdrant_url: str = ""                         # empty = no server, files in storage/qdrant
```

### 5.2 `app/adapters.py`: picking the plug

The embedding part, simplified:

```python
def make_embed_model() -> BaseEmbedding:
    if settings.embedder == "ollama":
        from llama_index.embeddings.ollama import OllamaEmbedding
        return OllamaEmbedding(model_name=settings.embed_model, base_url=settings.ollama_url,
                               query_instruction=QUERY_INSTRUCTION)
    if settings.embedder == "tei":
        TextEmbeddingsInference = optional("llama_index.embeddings.text_embeddings_inference",
                                           "TextEmbeddingsInference")
        return TextEmbeddingsInference(model_name=settings.embed_model, base_url=settings.embed_url,
                                       query_instruction=QUERY_INSTRUCTION, timeout=60)
    if settings.embedder == "opea":
        OPEAEmbedding = optional("llama_index.embeddings.opea", "OPEAEmbedding")
        return OPEAEmbedding(model_name=settings.embed_model, api_base=settings.embed_url)
    raise unknown("EMBEDDER", settings.embedder, EMBEDDERS)
```

Line by line:

1. **`-> BaseEmbedding`**: the function promises to return *some* embedding model. `BaseEmbedding`
   is LlamaIndex's interface; all three classes are built on it.
2. **One `if` per choice**: easy to read, easy to add a fourth option later.
3. **The `import` is inside the `if`**: Python only imports the package when that option is
   chosen. Someone using simple mode doesn't need the OPEA packages installed at all.
4. **`optional(...)`**: a small helper that imports a class, and if the package is missing,
   gives a helpful message instead of a confusing error:
   ```
   ImportError: llama_index.embeddings.opea isn't installed. Run: pip install -r requirements-opea.txt
   ```
5. **`raise unknown(...)`**: if `.env` has a typo like `EMBEDDER=olama`, the app stops at once and says:
   ```
   ValueError: Unknown EMBEDDER='olama' in .env. Choose one of: ollama, tei, opea
   ```
   Failing early with a clear message is far better than failing later with a strange one.

**`QUERY_INSTRUCTION`**: Qwen3-Embedding finds better matches when a *question* starts with a short
description of the task. Textbook chunks are embedded as they are. This was in `models.py`
before; it moved here unchanged.

**`make_llm()`** works the same way. One detail worth noticing:

```python
if settings.llm in ("openai_like", "opea"):
    if settings.llm == "opea":
        ServerLLM = optional("llama_index.llms.opea", "OPEA")
    else:
        ServerLLM = optional("llama_index.llms.openai_like", "OpenAILike")
    return ServerLLM(model=..., api_base=settings.llm_url, api_key="not-needed",
                     temperature=..., max_tokens=MAX_ANSWER_TOKENS, ...)
```

OPEA's LLM service and OpenVINO/vLLM servers all speak the **OpenAI chat API** (a common
standard for "send messages, get a reply"). So both classes take exactly the same settings,
and we write them only once. `api_key="not-needed"`: local servers don't check keys, but the
client library refuses to start without one.

`MAX_ANSWER_TOKENS = 600` is shared by every LLM, so answers have the same length limit whichever server writes them.

**`make_vector_store()`** returns `None` for the simple store:

```python
def make_vector_store():
    if settings.vector_store == "simple":
        return None          # None = "use LlamaIndex's built-in store"
    if settings.vector_store == "qdrant":
        ...
        if settings.qdrant_url:
            client = QdrantClient(url=settings.qdrant_url)                     # a Qdrant server (Docker)
        else:
            client = QdrantClient(path=str(settings.storage_dir / "qdrant"))   # no server, just a folder
        return QdrantVectorStore(collection_name="ncert", client=client)
```

Why `None`? LlamaIndex's `StorageContext.from_defaults(vector_store=None)` already means "use
the built-in store", so passing `None` through needs no extra code anywhere.

Qdrant can run **without a server**: give it a folder and it keeps everything there. That's free
and needs no Docker, so you can try Qdrant on your laptop right away.

### 5.3 `app/ingest.py`: building and loading the index

**Building** now goes through the chosen store:

```python
vector_store = make_vector_store()               # None or a Qdrant store
if vector_store is not None:
    vector_store.clear()                         # empty Qdrant first, so deleted PDFs disappear too
storage = StorageContext.from_defaults(vector_store=vector_store)
index = VectorStoreIndex(chunks, storage_context=storage, embed_model=make_embed_model(), ...)
```

`StorageContext` is LlamaIndex's "where to keep things" object. `VectorStoreIndex(...)` embeds
every chunk and puts it in that storage.

Then a new small file is written: **`storage/index/index_info.json`**. It looks like this:

```json
{
  "embedder": "ollama",
  "embed_model": "qwen3-embedding:0.6b",
  "vector_store": "simple",
  "chunks": 640,
  "subjects": [{"grade": 5, "subject": "English", "book": "Sunshine Reader - demo"}, ...],
  "built_at": "2026-10-08T17:58:39+00:00"
}
```

It records **which settings built the index** and **what's inside it**.

**Why it matters (the most important idea in this step):** suppose you change `EMBED_MODEL`
to another model but forget to rebuild. The textbook was turned into numbers by model A, and now
questions are turned into numbers by model B. Comparing them is like comparing a distance in
kilometres with one in miles: you get a number, but it means nothing. Search would quietly
return bad pages, **with no error at all**.

So `read_index_info()` compares the saved settings with the current ones:

```python
built_with = {k: info[k] for k in ("embedder", "embed_model", "vector_store")}
now = {k: getattr(settings, k) for k in built_with}
if built_with != now:
    raise IndexMismatch("The index was built with other settings (EMBED_MODEL was 'qwen3-embedding:0.6b', "
                        "now 'bge-m3'). Rebuild it with: python -m app.ingest")
```

- `getattr(settings, "embed_model")` is the same as `settings.embed_model`, but the name can be in a variable.
- `IndexMismatch` is our own error type (`class IndexMismatch(RuntimeError)`), so `main.py` can catch exactly this case.

A silent wrong answer becomes a loud, clear message. That's the habit this whole project follows.

**Loading** has two paths, because the two stores keep data in different places:

```python
def load_index(embed_model=None):
    read_index_info()                                  # stop now if there's no index, or it doesn't match .env
    vector_store = make_vector_store()
    if vector_store is None:                           # built-in store: everything is in storage/index/
        storage = StorageContext.from_defaults(persist_dir=str(settings.index_dir))
        return load_index_from_storage(storage, embed_model=embed_model)
    return VectorStoreIndex.from_vector_store(vector_store, embed_model=embed_model)   # Qdrant has the data
```

**`describe(chunks)`** builds the info dictionary. It's a separate function so the tests can use it too.

### 5.4 `app/rag.py`: one small change

```python
def __init__(self, index, llm=None, info=None):
    ...
    self.info = info or describe(self.index.docstore.docs.values())

def subjects(self):
    return self.info["subjects"]
```

Before, `subjects()` looked through every chunk in the index's **docstore** (its list of stored
texts). Qdrant keeps texts inside its own database, so that list would be empty. Now the subject
list comes from `index_info.json`. In tests, where we build a tiny index in memory, `info` isn't
given, so it's worked out from the chunks (`info or ...` means "use `info` if given, otherwise this").

**Nothing else in `rag.py` changed.** Search, the "I don't know" threshold and the claim check are
exactly as before. That's the point of the adapter layer.

### 5.5 `app/main.py`: clearer errors and health

Loading the RAG now catches three kinds of setup problems and shows the message to the user:

```python
try:
    rag = RAG(load_index(), make_llm(), read_index_info())
except FileNotFoundError:
    raise HTTPException(503, "The textbook index hasn't been built yet. Run: python -m app.ingest")
except (IndexMismatch, ValueError, ImportError) as error:   # wrong settings or missing packages
    raise HTTPException(503, str(error))
```

`503` is the HTTP code for "service not available right now".

`/api/health` now checks **only the services your adapters use**:

| Your `.env` | What health checks |
|---|---|
| default (all Ollama) | Ollama is running and both models are downloaded |
| `EMBEDDER=tei` | the embedding server answers at `EMBED_URL` |
| `LLM=opea` | the LLM server answers at `LLM_URL` |
| `VECTOR_STORE=qdrant` + `QDRANT_URL` | the Qdrant server answers |

Example reply in simple mode:

```json
{"status": "ok", "index": "ok (640 chunks)", "ollama": "ok",
 "adapters": {"embedder": "ollama", "llm": "ollama", "vector_store": "simple"}, ...}
```

## 6. How a question flows now

```
 Student asks "What is Ohm's law?"
        │
        ▼
 main.py  ── get_rag() ── first time only: ──► load_index()      (adapters pick store + embedder)
        │                                      make_llm()        (adapters pick LLM)
        │                                      read_index_info() (check the index matches .env)
        ▼
 rag.py   search: embed the question ──► [whichever embedder] ──► [whichever vector store]
          answer: stream from          ──► [whichever LLM]
          check every claim (unchanged)
        ▼
 Student sees the answer + citations (unchanged)
```

## 7. The tests, explained

Run them with:

```powershell
.venv\Scripts\activate
pytest
```

Expected: **44 passed** in about 10 seconds. No Ollama needed.

**How can we test without AI models?** `tests/conftest.py` defines two fakes:

- `WordCountEmbedding`: turns text into a vector by counting words. Texts sharing words get similar vectors. Not smart, but predictable.
- `FakeLLM`: always returns a fixed answer and remembers the prompt it was given.

They plug into the same interface as the real models. **The tests are themselves proof that the
adapter idea works:** the app can't tell the fakes from real models.

The new tests in `tests/test_adapters.py`:

| Test | What it proves |
|---|---|
| `test_default_setup_is_free_and_local` | With no `.env`, the app uses Ollama + the built-in store (free, no Docker) |
| `test_opea_mode_adapters` (4 cases) | Each OPEA-mode setting builds the right class |
| `test_every_llm_gets_the_same_answer_limits` | Server LLMs get the same temperature and length limit as Ollama |
| `test_qdrant_without_a_server_keeps_files_in_storage` | Qdrant works with just a folder |
| `test_a_typo_in_env_names_the_valid_choices` (3 cases) | A typo gives a message listing the valid options |
| **`test_qdrant_finds_the_same_pages_as_the_built_in_store`** | **Swapping the vector store doesn't change what students get.** Also checks that Qdrant itself applies the class filter |
| `test_index_info_is_read_when_it_matches` | A matching index loads |
| `test_changed_embedding_model_needs_a_rebuild` | Changing `EMBED_MODEL` without rebuilding is refused, with the reason |
| `test_changed_vector_store_needs_a_rebuild` | The same for `VECTOR_STORE` |
| `test_describe_lists_what_the_index_holds` | `index_info.json` has the right subjects and counts |

**A detail in the Qdrant test worth understanding:** `rag.search()` double-checks the class
filter in Python. That's good for safety, but it means a test of `search()` would pass even if
Qdrant **ignored** the filter, because the double-check would hide it. So the test also calls
`retrieve()`, which shows Qdrant's raw results, and checks they're all Class 5:

```python
hits = in_qdrant.retrieve("How do plants make their own food using sunlight?", 5, "Science")
assert {hit.node.metadata["grade"] for hit in hits} == {5}
```

Always ask: **"would this test fail if the thing it checks were broken?"** If not, it proves nothing.

Optional tests (OPEA adapters, Qdrant) are **skipped**, not failed, if those packages aren't
installed. That's what `pytest.importorskip(...)` does.

## 8. Try it yourself

Do these in order. Each takes a minute or two and shows one idea from this step.

**1. See a typo caught.** In `.env` write `LLM=olama`, then run:
```powershell
python -c "from app.adapters import make_llm; make_llm()"
```
You'll see `Unknown LLM='olama' in .env. Choose one of: ollama, openai_like, opea`. Remove the line afterwards.

**2. See the index check work.** In `.env` write `EMBED_MODEL=bge-m3`, start the server
(`uvicorn app.main:app --port 8000`) and open http://localhost:8000/api/health. The `index` line
says which setting changed and how to fix it. Remove the line and restart.

**3. Try Qdrant without Docker** (optional, takes ~25 min to rebuild):
```powershell
pip install -r requirements-opea.txt
# in .env:  VECTOR_STORE=qdrant
python -m app.ingest        # builds into storage/qdrant
python -m app.evaluate      # should give the same numbers as section 9
```
Set it back to `simple` and rebuild when you're done. *(Qdrant's no-server mode lets only one
program open the folder at a time, so stop the server before running ingest.)*

**4. Read one test and break the code on purpose.** In `app/ingest.py`, change
`if built_with != now:` to `if False:`, run `pytest`, and watch
`test_changed_embedding_model_needs_a_rebuild` fail. Undo it. Now you've *seen* that the test guards something real.

## 9. Proof that nothing broke

This step was meant to change **structure, not behaviour**. Two checks prove that:

**1. All the old tests still pass, unchanged:** 29 of 29 (plus 15 new ones = 44).

**2. The search evaluation gives the same numbers as before the change.** The index was rebuilt
with the new code, then `python -m app.evaluate` was run on the same 40 questions:

| | Before Step 1 | After Step 1 |
|---|---|---|
| Hit rate (right chapter in top 4) | 100% | **100%** |
| MRR | 1.00 | **1.00** |
| Best scores, on-topic questions | 0.61 – 0.86 | **0.61 – 0.86** |
| Best scores, off-topic questions | 0.22 – 0.45 | **0.22 – 0.45** |
| Off-topic scores below `min_score` (0.53) | all | **all** |

**Identical, down to two decimal places.** The details are in [docs/LOG.md](../LOG.md).

The old index was kept as `storage/index_backup_before_step1/` in case you ever want to compare. You can delete it.

## 10. Common mistakes

| Symptom | Cause | Fix |
|---|---|---|
| Server says "The index was built with other settings" | You changed `EMBEDDER`, `EMBED_MODEL` or `VECTOR_STORE` | `python -m app.ingest`, or undo the change |
| "isn't installed. Run: pip install -r requirements-opea.txt" | You chose an OPEA-mode adapter | Run that command |
| `Unknown LLM=…` | Typo in `.env` | Use one of the names listed in the message |
| Qdrant: "storage folder is already accessed by another instance" | The server and ingest both opened the Qdrant folder | Stop the server, then run ingest |
| Changed `.env` but nothing happened | Settings are read at startup | Restart the server |

## 11. How to explain this in a viva

**Q: What is the adapter layer?**
A: One file, `adapters.py`, that reads `.env` and creates the embedding model, LLM and vector
store. The rest of the app uses them only through LlamaIndex's common interfaces, so any service
can be swapped by changing a setting.

**Q: Why did you need it?**
A: To run the same code in two setups: a free local one with Ollama, and an OPEA one where each
model is a separate microservice. It also makes testing easy: the tests plug in fake models.

**Q: How do you know the refactor didn't break anything?**
A: All 29 earlier tests pass unchanged, and the retrieval evaluation gives the same hit rate and
MRR as before. A new test also checks that Qdrant returns the same pages as the built-in store.

**Q: What is `index_info.json` for?**
A: It records which embedding model built the index. If the settings change without a rebuild,
the app refuses to start, because vectors from two different models can't be compared and search
would silently return wrong pages.

**Q: Why are imports inside the `if` branches?**
A: So the optional OPEA packages are only needed by people who choose OPEA mode.

## 12. What's next

**Step 2: Hindi data + OCR.** You'll add an **OCR adapter** the same way (`OCR=tesseract`), teach
the catalog about Hindi-medium books, and detect when a PDF's text is junk so the page goes to OCR.

Before Step 2 you'll need to install two free things (the Step 2 guide will walk through it):
1. **Tesseract OCR** for Windows, with the Hindi language pack
2. The **3 Hindi-medium Class 10 Science chapters** from ncert.nic.in
