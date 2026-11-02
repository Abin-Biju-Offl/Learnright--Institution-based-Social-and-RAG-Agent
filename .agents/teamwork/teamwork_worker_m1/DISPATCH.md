## 2026-10-31T12:18:19Z
You are a teamwork_worker implementing Milestone 1: Content Moderation & Taxonomy Engine for the NCERT Textbook Assistant.
Your identity: teamwork_worker
Your working directory: e:\WORK\intel rag llamaindex\.agents\teamwork\teamwork_worker_m1\
Parent: teamwork_orchestrator (Conversation ID: f0cdbf9a-9067-430b-91fd-5b4abd94d12d)

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

MANDATORY FIRST STEPS:
1. Read e:\WORK\intel rag llamaindex\.agents\teamwork\ORIGINAL_REQUEST.md.
2. Read e:\WORK\intel rag llamaindex\.agents\teamwork\orchestrator\PROJECT.md.
3. Read the taxonomy exploration analysis and handoff:
   - e:\WORK\intel rag llamaindex\.agents\teamwork\teamwork_explorer_taxonomy\analysis.md
   - e:\WORK\intel rag llamaindex\.agents\teamwork\teamwork_explorer_taxonomy\handoff.md
4. Maintain your own BRIEFING.md, DISPATCH.md, and progress.md in your working directory: e:\WORK\intel rag llamaindex\.agents\teamwork\teamwork_worker_m1\.

SCOPE & EXCLUSIVE FILE OWNERSHIP:
You own exclusively:
- `app/safety/` subpackage:
  * `app/safety/__init__.py`
  * `app/safety/taxonomy.py`: Enum & definitions for 7 categories (adult_sexual, violence_gore, self_harm, hate_speech, illegal_acts_weapons_drugs, cyberbullying, other_inappropriate), severity levels, crisis flags.
  * `app/safety/scanner.py`: High-speed deterministic regex & keyword scanner with Hinglish/slang and obfuscation support.
  * `app/safety/curriculum.py`: NCERT Class 10 Biology (Chapter 7 Reproduction, Chapter 8 Heredity), English (Apartheid, Holocaust), and Chemistry preservation whitelist to ensure authentic curriculum queries are NEVER falsely blocked.
  * `app/safety/templates.py`: Age-appropriate educational refusal templates and Indian crisis helplines (Tele-MANAS 14416, CHILDLINE 1098, KIRAN 1800-599-0019).
  * `app/safety/logger.py`: Thread-safe append logger for `storage/safety_events.jsonl`.
- `tests/test_safety.py`: Comprehensive test suite testing all 7 categories refusal, crisis helplines, Hinglish queries, and curriculum preservation (Class 10 Biology reproduction/contraception and English apartheid).

TASKS:
1. Implement `app/safety/` fully with robust, production-quality Python code.
2. Integrate safety evaluation into `app/main.py` so `/api/ask` and `/api/ask/stream` evaluate input question through `app.safety` before retrieval or generation:
   - If unsafe, return age-appropriate refusal response with `found=False`, `category`, and log the safety event to `storage/safety_events.jsonl`.
   - If curriculum query (e.g. Class 10 Biology reproduction), allow it through to RAG.
3. Create `tests/test_safety.py` covering:
   - Refusal of adult/sexual content queries.
   - Refusal of violence/gore queries.
   - Refusal of self-harm queries with crisis helpline numbers included in response.
   - Refusal of hate speech and cyberbullying queries.
   - Refusal of illegal acts, weapon crafting, and drug queries.
   - Acceptance of Class 10 Biology queries (testes function, contraception barrier methods, sex determination) with accurate educational answers and NO false blocks.
   - Acceptance of Class 10 English (apartheid) queries.
   - Verify `storage/safety_events.jsonl` receives logged event records with correct schema.
4. Execute tests using `.venv\Scripts\pytest tests/test_safety.py -v` (and existing tests `.venv\Scripts\pytest tests/test_rag.py -v`). Ensure ALL tests pass 100%.
5. Write your handoff report to `e:\WORK\intel rag llamaindex\.agents\teamwork\teamwork_worker_m1\handoff.md` detailing:
   - Observation: Exact files created/modified and test results with command output.
   - Logic Chain: Technical implementation rationale.
   - Caveats: Any edge conditions.
   - Conclusion: Verification summary.
   - Verification Method: Exact commands to reproduce test passes.
6. Send completion message back to parent orchestrator.
