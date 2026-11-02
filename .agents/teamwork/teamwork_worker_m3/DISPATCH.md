## 2026-10-31T16:07:11Z

You are a teamwork_worker implementing Milestone 3: Parental Controls Backend & Storage for the NCERT Textbook Assistant.
Your identity: teamwork_worker
Your working directory: e:\WORK\intel rag llamaindex\.agents\teamwork\teamwork_worker_m3\
Parent: teamwork_orchestrator (Conversation ID: f0cdbf9a-9067-430b-91fd-5b4abd94d12d)

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

MANDATORY FIRST STEPS:
1. Read e:\WORK\intel rag llamaindex\.agents\teamwork\ORIGINAL_REQUEST.md.
2. Read e:\WORK\intel rag llamaindex\.agents\teamwork\orchestrator\PROJECT.md.
3. Read the parental controls exploration analysis and handoff:
   - e:\WORK\intel rag llamaindex\.agents\teamwork\teamwork_explorer_parental\analysis.md
   - e:\WORK\intel rag llamaindex\.agents\teamwork\teamwork_explorer_parental\handoff.md
4. Maintain your own BRIEFING.md, DISPATCH.md, and progress.md in your working directory: e:\WORK\intel rag llamaindex\.agents\teamwork\teamwork_worker_m3\.

SCOPE & EXCLUSIVE FILE OWNERSHIP:
You own exclusively:
- `app/parental/` subpackage:
  * `app/parental/__init__.py`
  * `app/parental/auth.py`: Salted PBKDF2-HMAC-SHA256 PIN hashing (16-byte random salt, 100k iterations), progressive brute-force lockout (5 fails = 5-min lockout; 8 fails = 15-min lockout), 15-minute Bearer session tokens.
  * `app/parental/storage.py`: Thread-safe atomic JSON/JSONL manager for `storage/parental_config.json`, `storage/student_chat_history.jsonl`, and `storage/safety_events.jsonl`.
  * `app/parental/schemas.py`: Pydantic request & response models for auth, history, flagged alerts, settings, and overview.
  * `app/parental/service.py`: Business logic for parental controls (PIN setup, verify, change PIN, history search/filtering, flagged query triage & review status transition, config updates, study overview stats).
  * `app/parental/routes.py`: FastAPI router with endpoints:
    - `POST /api/parent/auth/setup` (initial PIN setup)
    - `POST /api/parent/auth/verify` (login, returns session token)
    - `POST /api/parent/auth/change-pin` (authenticated PIN change)
    - `GET /api/parent/auth/status` (checks if PIN is configured, lockout status)
    - `GET /api/parent/overview` (summary metrics: total student chats, safety blocks, unreviewed alerts)
    - `GET /api/parent/history` (view student chat sessions & transcripts with search & filter)
    - `GET /api/parent/flagged` (view blocked/flagged queries log with category & refusal reason)
    - `POST /api/parent/flagged/{event_id}/review` (acknowledge or dismiss alert with parent notes)
    - `GET /api/parent/settings` (fetch category toggles, strictness presets, custom blocked keywords)
    - `PUT /api/parent/settings` (persist updated category toggles and custom blocked keywords)
- `app/main.py`:
  * Mount parental router: `app.include_router(parental_router, prefix="/api/parent", tags=["parental"])`
  * Add student conversation turn logger so completed `/api/ask` and `/api/ask/stream` interactions are logged to `storage/student_chat_history.jsonl` with session_id, timestamp, grade, subject, question, and answer.
  * Pass active parental filtering preferences (category toggles and custom blocked keywords) to `evaluate_content` in `app/safety/`.
- `tests/test_parental.py`:
  * Comprehensive automated test suite covering all 10 test cases:
    - PIN setup & verification with salted PBKDF2
    - 5-attempt brute-force lockout returning HTTP 429
    - Valid Bearer token authentication and expired token rejection
    - Student chat history logging and retrieval via `/api/parent/history`
    - Flagged query review status update via `POST /api/parent/flagged/{id}/review`
    - Category toggles persistence via `PUT /api/parent/settings`
    - Custom blacklisted keyword blocking persistence and enforcement in chat API
    - Overview metrics calculation

TASKS:
1. Implement `app/parental/` modules (`auth.py`, `storage.py`, `schemas.py`, `service.py`, `routes.py`, `__init__.py`).
2. Integrate parental router and chat history logging in `app/main.py`. Connect parental config to safety evaluation so custom blocked keywords and category toggles are respected.
3. Author `tests/test_parental.py` covering all parental operations.
4. Execute tests using `.venv\Scripts\pytest tests/test_parental.py -v` AND full suite `.venv\Scripts\pytest tests/test_rag.py tests/test_safety.py tests/test_security.py tests/test_parental.py -v`. Verify 100% pass.
5. Write handoff report to `e:\WORK\intel rag llamaindex\.agents\teamwork\teamwork_worker_m3\handoff.md` and send completion message back to orchestrator.
