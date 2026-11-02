## 2026-10-31T15:43:45Z
You are a teamwork_worker implementing Milestone 2: Security Safeguards & Prompt Hardening for the NCERT Textbook Assistant.
Your identity: teamwork_worker
Your working directory: e:\WORK\intel rag llamaindex\.agents\teamwork\teamwork_worker_m2\
Parent: teamwork_orchestrator (Conversation ID: f0cdbf9a-9067-430b-91fd-5b4abd94d12d)

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

MANDATORY FIRST STEPS:
1. Read e:\WORK\intel rag llamaindex\.agents\teamwork\ORIGINAL_REQUEST.md.
2. Read e:\WORK\intel rag llamaindex\.agents\teamwork\orchestrator\PROJECT.md.
3. Read the security exploration analysis and handoff:
   - e:\WORK\intel rag llamaindex\.agents\teamwork\teamwork_explorer_security_2\analysis.md
   - e:\WORK\intel rag llamaindex\.agents\teamwork\teamwork_explorer_security_2\handoff.md
4. Maintain your own BRIEFING.md, DISPATCH.md, and progress.md in your working directory: e:\WORK\intel rag llamaindex\.agents\teamwork\teamwork_worker_m2\.

SCOPE & EXCLUSIVE FILE OWNERSHIP:
You own exclusively:
- `app/security/` subpackage:
  * `app/security/__init__.py`
  * `app/security/normalizer.py`: Unicode NFKC normalization, zero-width character stripping, leetspeak canonicalization, Base64 inspection.
  * `app/security/scanner.py`: High-speed regex heuristic scanner detecting:
    - Direct instruction overrides ("Ignore previous instructions", "SYSTEM OVERRIDE", developer modes)
    - System prompt exfiltration ("Repeat the prompt above", "Output initial instructions", line dumps)
    - Persona-switching & jailbreaks (DAN, grandma exploit, screenplay author, hypothetical inversion)
    - Delimiter breakout attempts (fake XML tags, markdown code block escapes)
  * `app/security/delimiters.py`: XML sanitization and secure nonce/tag containment envelopes (`<ncert_system_policy>`, `<textbook_context>`, `<student_query>`).
  * `app/security/guardrail.py`: Dual-pass output guardrail with n-gram system prompt leak detector, affirmative jailbreak detector, and streaming window buffer.
- `app/prompts.py`:
  * Hardened `SYSTEM_PROMPT` with non-overridable under-18 safety boundaries, system prompt confidentiality, and XML tag boundaries.
  * Hardened `PURE_LLM_SYSTEM_PROMPT`.
  * Hardened `build_condense_prompt` preventing prompt injection through conversation history or follow-up question.
- `app/rag.py`:
  * Integrate prompt hardening and output guardrail in RAG query condensation, pure_llm streaming, and standard retrieval generation.
- `app/main.py`:
  * Connect input security screening in `/api/ask` and `/api/ask/stream` (alongside existing `app.safety` filter) logging security violations to `storage/safety_events.jsonl`.
- `tests/test_security.py`:
  * Comprehensive automated test suite with 65+ test cases across 6 suites (direct overrides, prompt secrecy, jailbreak resistance, delimiter breakouts, curriculum preservation, and output guardrail).

TASKS:
1. Implement `app/security/` modules (`normalizer.py`, `scanner.py`, `delimiters.py`, `guardrail.py`, `__init__.py`).
2. Update `app/prompts.py` with hardened prompts and XML containment.
3. Update `app/rag.py` and `app/main.py` with input security screening and output guardrail protection.
4. Author `tests/test_security.py` covering all 6 threat suites with 65+ automated test cases.
5. Execute tests using `.venv\Scripts\pytest tests/test_security.py -v` AND `.venv\Scripts\pytest tests/test_safety.py -v`. Verify 100% pass.
6. Write handoff report to `e:\WORK\intel rag llamaindex\.agents\teamwork\teamwork_worker_m2\handoff.md` and send completion message back to orchestrator.
