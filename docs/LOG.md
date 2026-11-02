# Project log

Short, dated notes: what was tried, the numbers measured, and what was kept.
Newest entry first. Numbers always say **when** and **on what data** they were measured.

---

## 2026-10-08 · Step 1: adapter layer (no behaviour change)

**Lesson:** the index has to remember which embedding model built it. Otherwise changing
`EMBED_MODEL` without rebuilding silently ruins search, with no error at all. The app now
refuses to start in that case (`index_info.json` + `read_index_info()`).

**What changed:** `app/models.py` → `app/adapters.py`. Embedder, LLM and vector store are
chosen by `EMBEDDER`, `LLM` and `VECTOR_STORE` in `.env`. Default stays free and local
(Ollama + LlamaIndex's built-in store). OPEA mode adapters (TEI, OPEA, OpenAI-like, Qdrant) are optional.

**Evidence:**
- Tests: 29/29 old tests unchanged and passing; 15 new adapter tests; **44 passed**.
- Qdrant (no-server mode) returns the same pages as the built-in store on the test collection, and applies the class filter itself (`test_qdrant_finds_the_same_pages_as_the_built_in_store`).
- Index rebuilt with the new code: **467 pages → 640 chunks** (the README's older "437 pages / 610 chunks" was from before the Class 5 demo books were added).
- Retrieval eval, 40 questions (`eval/questions.json`), `qwen3-embedding:0.6b`, `TOP_K=4`, `MIN_SCORE=0.53`:

  | | Before (index from before Step 1) | After (rebuilt with Step 1 code) |
  |---|---|---|
  | Hit rate | 100% | **100%** |
  | MRR | 1.00 | **1.00** |
  | On-topic best scores | 0.61 – 0.86 | **0.61 – 0.86** |
  | Off-topic best scores | 0.22 – 0.45 | **0.22 – 0.45** |
  | `MIN_SCORE` 0.53 separates them | yes | **yes** |

  Identical, as expected for a structure-only change. Rebuild time: 1,552 s (~26 min) on the
  laptop CPU (AMD Ryzen 9 6900HS), ~2.4 s per batch of 10 chunks.

**Kept:** the old index as `storage/index_backup_before_step1/` (safe to delete).
